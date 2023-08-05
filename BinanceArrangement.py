import logging
import time

import ccxt
import datetime

# 初始化日志配置
logger = logging.getLogger('operation_log')
logger.setLevel(logging.INFO)
operation_log = logging.FileHandler(
    f"多均线策略_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.txt ", 'a',
    encoding='UTF-8')  # 按照年月日小时生成日志文件，如果存在则追加内容，不存在则创建文件
console_handler = logging.StreamHandler()  # 输出到控制台
console_handler.setLevel('INFO')  # info以上才输出到控制台

formatter = logging.Formatter(
    '%(asctime)s %(message)s ')
operation_log.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(operation_log)
logger.addHandler(console_handler)

# 初始化交易所，由于binance访问需要科学上网工具， 33210是你用的科学上网工具端口号，需要根据自己实际情况修改，否则无法链接上网
exchange = ccxt.binance({
    'timeout': 30000,
    'verbose': True,  # 启用调试模式
    'https_proxy': 'http://127.0.0.1:33210'
})


def get_current_price(symbol: str):
    # 获取交易对的最新市场数据
    ticker = exchange.fetch_ticker(symbol)
    # 提取当前价格
    current_price = ticker['last']
    return current_price


def calculate_ma(data, period):
    close_prices = [float(entry[4]) for entry in data]
    ma = sum(close_prices[-period:]) / period
    return ma


def multi_avg_price_line(symbol: str, time_limit: str, first, second, third):
    """
    多头排列基本逻辑是，选三根均线，短期均线在中期均线和长期均线之上，中期均线在长期均线之上，是为多头排列，同时增加一个判断，就是当前价格在短期均线之上
    即当前价格上破了短期，中期，长期均线，是为多头排列
    :param symbol: 
    :param time_limit: 1d
    :param first: 短期时间
    :param second: 中期时间
    :param third: 长期时间
    :return: 
    """
    # 获取收盘价
    current_price = get_current_price(symbol)
    # 0. 获取某币中的k线数据
    kline_data = exchange.fetch_ohlcv(symbol, time_limit)
    # 1. 获取短期均线价格
    mafirst = calculate_ma(kline_data, first)
    # 2 获取中期均线价格
    masecond = calculate_ma(kline_data, second)
    # 3. 获取长期均线均线价格
    mathird = calculate_ma(kline_data, third)
    message_dict = {}
    if current_price > mafirst >= masecond >= mathird:
        message = f"多头排练：交易对={symbol}, 均线粒度={time_limit}, 当前价格 ={current_price}, MA{first}= {round(mafirst, 4)}, MA{second}={round(masecond, 4)} , MA{third} = {round(mathird, 4)}"
        message_dict[symbol] = message
        logger.info(message)
    return message_dict


def get_usdt_pairs():
    """
    获取币安交易所的所有USDT交易对，并过滤部分不满足条件的交易对
    只取现货USDT交易对，并过滤USDC BUSD USDP等稳定币交易对，
    :return: 
    """

    try:
        # 加载交易所的所有交易对信息
        markets = exchange.load_markets()
        target_pairs = []
        for symbol in markets:
            pairs = markets[symbol]
            # 只取现货USDT交易对，并过滤USDC BUSD USDP等稳定币交易对，
            if pairs['type'] == 'spot' and pairs['base'] != 'BUSD' and pairs['base'] != 'USDC' and pairs[
                'base'] != 'TUSD' and pairs['base'] != 'USDP' and pairs['base'] != 'FDUSD' and pairs[
                'quote'] == 'USDT' and pairs['active'] == True:
                target_pairs.append(str(symbol).replace("/", ""))
        logger.info(f"币安多头排列筛选中，当前共计币种={len(target_pairs)}")
        return target_pairs
    except ccxt.NetworkError as e:
        logger.info(f"网络连接出错：{e}")
    except ccxt.ExchangeError as e:
        logger.info(f"交易所错误：{e}")
    except Exception as e:
        logger.info(f"其他错误：{e}")


# 过滤up down等杠杠交易对
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

usdt_pairs = get_usdt_pairs()
time_limit = "1d"  # 1d为日线级别，4h为4小时级别，其他以此类推
count = 0
short = 10  # 短期时间，5为5日均线，10为十日均线，以此类推
middle = 30  # 中期时间，60为60日均线，30为30日均线，以此类推
long = 120  # 长期时间，120为120日均线，100为100日均线，以此类推
for pair in usdt_pairs:
    if not pair:
        continue
    count = count + 1
    if pair in IGNORE_PAIRS:
        continue
    message_dict = multi_avg_price_line(pair, time_limit, short, middle, long)  # 多均线策略
    time.sleep(1)  # 执行间隔时间，防止被访问频率限制
