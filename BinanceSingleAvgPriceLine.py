import logging
import time

import ccxt
import datetime

logger = logging.getLogger('operation_log')
logger.setLevel(logging.INFO)
operation_log = logging.FileHandler(
    f"单均线策略_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.txt ", 'a',
    encoding='UTF-8')  # 按照年月日小时生成日志文件，如果存在则追加内容，不存在则创建文件
console_handler = logging.StreamHandler()  # 输出到控制台
console_handler.setLevel('INFO')  # info以上才输出到控制台

formatter = logging.Formatter(
    ' %(message)s ')
operation_log.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(operation_log)
logger.addHandler(console_handler)
binance = ccxt.binance({
    'timeout': 30000,
    'verbose': True,  # 启用调试模式
    'https_proxy': 'http://127.0.0.1:33210'
})


def get_current_price(symbol: str):
    # 获取交易对的最新市场数据
    ticker = binance.fetch_ticker(symbol)
    # 提取当前价格
    current_price = ticker['last']
    return current_price


def get_yesterday_last_price(symbol: str, time_limit):
    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    yesterday_str = yesterday.strftime('%Y-%m-%d')
    try:
        # 获取K线数据，时间周期为日线 ('1d')
        candles = binance.fetch_ohlcv(symbol, time_limit)
        # 从K线数据中筛选昨天的收盘价
        for candle in candles:
            timestamp = candle[0] // 1000  # 转换为秒级时间戳
            date = datetime.datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d')
            if date == yesterday_str:
                close_price = candle[4]  # 收盘价在K线数据中的索引为4
                logger.info(f"昨天({yesterday_str})的收盘价为：{close_price:.2f} USDT")
                return close_price
        else:
            logger.info(f"未找到昨天({yesterday_str})的收盘价数据")
            return None

    except ccxt.NetworkError as e:
        logger.info(f"网络连接出错：{e}")
    except ccxt.ExchangeError as e:
        logger.info(f"交易所错误：{e}")
    except Exception as e:
        logger.info(f"其他错误：{e}")


def calculate_ma(data, period):
    close_prices = [float(entry[4]) for entry in data]
    ma = sum(close_prices[-period:]) / period
    return ma


def get_MA(symbol: str, time_limit, period: int):
    kline_data = binance.fetch_ohlcv(symbol, time_limit)
    ma_price = calculate_ma(kline_data, period)
    return ma_price


def single_avg_price_line(symbol: str, time_limit: str, period: int):
    # 1 获取当前价格
    current_price = get_current_price(symbol)
    # 获取昨天的十五日均线
    maprice = get_MA(symbol, time_limit, period)

    percent = ((current_price - maprice) / current_price) * 100
    percent_format = round(percent, 2)
    # logger.info(symbol)
    if current_price >= maprice:
        # 如果符合条件，给我发通知
        logger.info(
            f"!!!!!!{symbol}, Prev:{current_price}, MA{period}:, {maprice}, {time_limit}, {percent_format}%\n")
        return symbol
    else:
        logger.info(
            f"{symbol}, Prev:{current_price}, MA{period}:, {maprice} , {time_limit}, {percent_format}% \n")
    return None


def get_date_close_price_dict(symbol: str, time_limit: str):
    candles = binance.fetch_ohlcv(symbol, time_limit)
    # 从K线数据中筛选昨天的收盘价
    date_price_dict = {}
    for candle in candles:
        timestamp = candle[0] // 1000  # 转换为秒级时间戳
        temp_date = datetime.datetime.utcfromtimestamp(timestamp).strftime('%Y%m%d')
        close_price = candle[4]  # 收盘价在K线数据中的索引为4
        date_price_dict[temp_date] = close_price

    return date_price_dict


def get_MA_price_by_date(datestr, period, date_price_dict):
    # 往前数period天，然后，分别获取
    sum_price = 0.00
    for n in range(1, period + 1):
        date = datetime.datetime.strptime(datestr, '%Y%m%d')
        temp_date = date - datetime.timedelta(days=n)
        temp_date_str = temp_date.strftime('%Y%m%d')
        close_price = date_price_dict[temp_date_str]
        sum_price += close_price
        # logger.info(f" temp_date_str={temp_date_str} , close_price={close_price}")

    return sum_price / period


def build_date_list(start_date, end_date):
    # 20230101-20230801
    date_list = []
    start_date = datetime.datetime.strptime(start_date, '%Y%m%d')
    end_date = datetime.datetime.strptime(end_date, '%Y%m%d')
    temp_date = start_date
    while temp_date <= end_date:
        date_list.append(temp_date.strftime('%Y%m%d'))
        temp_date = temp_date + datetime.timedelta(days=1)
    return date_list


def check_date_price(period, date_price_dict, date_list):
    trade_flag = 0  # 0 空仓，1 持仓
    btc_amount = 0.00  # 持有的币种数量
    usdt_amount = 1000.00  # 金额
    init_amount = 1000.00  # 初始金额

    trade_count = 0
    last_price = 0.00
    for date in date_list:
        ma_price = get_MA_price_by_date(date, period, date_price_dict)
        current_price = date_price_dict[date]
        last_price = current_price
        if current_price > ma_price:
            if trade_flag == 0 and usdt_amount > 0.00:
                btc_amount = usdt_amount / current_price
                trade_count += 1
                logger.info(
                    f" 当前日期={date} , 收线价格={current_price}, ma{period} 价格={ma_price} 涨破均线价格,并且当前空仓，买入 {usdt_amount} u, 持有数量 {btc_amount} ")
                usdt_amount = 0.00  # 买入BTC,现金余额为0
                trade_flag = 1
            else:
                logger.info(
                    f" 当前日期={date} , 收线价格={current_price}, ma{period} 价格={ma_price} 维持阳线，且满仓，不操作")
        else:
            if trade_flag == 1 and btc_amount > 0.00:
                usdt_amount = btc_amount * current_price
                logger.info(
                    f" 当前日期={date} , 收线价格={current_price}, ma{period} 价格={ma_price} 跌破均线价格,并且当前满仓，卖出数量 {btc_amount}, 现金余额 {usdt_amount} ")
                btc_amount = 0.00  # 卖出所有btc,btc数量为0
                trade_count += 1
                trade_flag = 0
            else:
                logger.info(
                    f" 当前日期={date} , 收线价格={current_price}, ma{period} 价格={ma_price} 维持阴线价格,并且当前空仓，不操作")

    total_asset_usdt = usdt_amount + btc_amount * last_price
    profit = total_asset_usdt - init_amount
    logger.info(f" 交易次数={trade_count}, 初始金额={init_amount}, 最终金额={total_asset_usdt}, 盈利={profit}")


def get_usdt_pairs():
    try:
        # 加载交易所的所有交易对信息
        markets = binance.load_markets()
        target_pairs = []
        for symbol in markets:
            pairs = markets[symbol]
            if pairs['type'] == 'spot' and pairs['base'] != 'BUSD' and pairs['base'] != 'USDC' and pairs[
                'base'] != 'TUSD' and pairs['base'] != 'USDP' and pairs['base'] != 'FDUSD' and pairs[
                'quote'] == 'USDT' and pairs['active'] == True:
                target_pairs.append(str(symbol).replace("/", ""))
        logger.info(f"当前共计币种={len(target_pairs)}")
        return target_pairs
    except ccxt.NetworkError as e:
        logger.info(f"网络连接出错：{e}")
    except ccxt.ExchangeError as e:
        logger.info(f"交易所错误：{e}")
    except Exception as e:
        logger.info(f"其他错误：{e}")


IGNORE_PAIRS = ['BTCUPUSDT', 'BTCDOWNUSDT', 'ETHUPUSDT', 'ETHDOWNUSDT', 'ADAUPUSDT', 'ADADOWNUSDT', 'LINKUPUSDT',
                'LINKDOWNUSDT', 'BNBUPUSDT', 'BNBDOWNUSDT', 'XTZUPUSDT',
                'XTZDOWNUSDT', 'EOSUPUSDT', 'EOSDOWNUSDT', 'TRXUPUSDT', 'TRXDOWNUSDT', 'XRPUPUSDT', 'XRPDOWNUSDT',
                'DOTUPUSDT', 'DOTDOWNUSDT', 'LTCUPUSDT', 'LTCDOWNUSDT', 'UNIUPUSDT',
                'UNIDOWNUSDT', 'SXPUPUSDT', 'SXPDOWNUSDT', 'FILUPUSDT', 'FILDOWNUSDT', 'YFIUPUSDT', 'YFIDOWNUSDT',
                'BCHUPUSDT', 'BCHDOWNUSDT', 'AAVEUPUSDT', 'AAVEDOWNUSDT',
                'SUSHIUPUSDT', '1INCHUPUSDT',
                '1INCHDOWNUSDT'
                'SUSHIDOWNUSDT',
                'XLMUPUSDT',
                'XLMDOWNUSDT']


def run_single_avg_pirce_line():
    usdt_pairs = get_usdt_pairs()
    time_limit = "1d"  # 12h为 12小时级别，1d为日线级别 其他以此类推
    period = 30  # 30日均线
    logger.info("当前交易对, 当前价格, 周期, 均线价格, 均线级别, 比例 ")
    for pair in usdt_pairs:
        if pair in IGNORE_PAIRS:
            continue
        single_avg_price_line(pair, time_limit, period)
        time.sleep(1)


def run_test_back(start_date, end_date, symbol):
    date_list = build_date_list(start_date, end_date)
    date_close_price_dict = get_date_close_price_dict(symbol, "1d")
    logger.info(f"当前交易对={symbol}, 开始日期={start_date}, 结束日期={end_date}，执行单均线回测")
    check_date_price(30, date_close_price_dict, date_list)


# 单均线策略
# run_single_avg_pirce_line()

start_date = "20230101"
end_date = "20230801"
symbol = "COMPUSDT"
# 执行回测代码
# run_test_back(start_date, end_date,symbol)
