# This is a whole new strategy which doesn't necessarily need to be backtested in the traditional way,
# but i could plot a moving average of the profitability to see how consistent it is over time

# TODO 6 try making the trigger move a scalar of atr or bb width or some other volatility metric
# TODO 9 swap the sma for a hma to see if the results improve
# TODO 10 calculate mean/max drawdown per trade using period low to work out how much leverage could be safely used
#  *** maybe even calculate mean/max dd per trade AND mean/max dd per winning trade - if there is a significant
#  difference, it might identify a good stoploss placement (this might work best in the volatility adjusted version)

# analysis
# TODO group results by timescale and get summary stats like avg profitability, range of profitable %s, most profitable %
# TODO maybe find out if groupby output can be plotted as a set of overlayed charts
# TODO plot profitability over time to see if it is random or if there are trends in profitability which could be anticipated
# TODO plot pairs along x axis and avg profit of each other param on y axis to see if newer pairs are less efficient in any way



import pandas as pd
from pathlib import Path
import statistics
import keys
from binance.client import Client
import time
from finta import TA
import matplotlib.pyplot as plt


s = time.perf_counter()

client = Client(api_key=keys.Pkey, api_secret=keys.Skey)

fees = 0.075 * 2 # round-trip trading fees as a percentage
min_trades = 30
roc_p = 1

count = 0
results = {}

def get_pairs(quote):

    info = client.get_exchange_info()
    symbols = info['symbols']
    length = len(quote)
    pairs_list = []
    blacklist = ['DAIBTC', 'PAXUSDT', 'USDSBUSDT', 'BSVUSDT', 'BCHSVUSDT', 'BCHABCUSDT', 'VENUSDT',
                 'TUSDUSDT', 'USDCUSDT', 'USDSUSDT', 'BUSDUSDT', 'EURUSDT', 'BCCUSDT',
                 'IOTAUSDT', 'BSVBTC', 'BCHBTC', 'VENBTC', 'BCCBTC', 'IOTABTC']

    for item in symbols:
        if item['symbol'][-length:] == quote:
            if not (item['symbol'] in blacklist):
                pairs_list.append(item['symbol'])

    return pairs_list

def resample(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    """Resample DataFrame by <interval>."""

    d = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}

    return df.resample(interval).agg(d)

def mean_rev_bt(pair, data, t, ma, pct):
    global count

    days_calc = {'5MIN': 0.003472, '15MIN': 0.0104167, '1H': 0.041667, '4H': 0.166667, '12H': 0.5, '1D': 1, '3D': 3, '1W': 7}

    num_days = len(data) * days_calc.get(t)

    # calculate mean % change of all periods to use as a baseline comparison
    all_mean = data['roc'].mean()

    # create signals column and enter 'long' or 'short' on each row that satisfies the conditions
    data.loc[(data['roc'] < (0 - (pct / 100))) & (data['ma_roc'] > 0), 'signals'] = 'long'
    data.loc[(data['roc'] > (pct / 100)) & (data['ma_roc'] < 0), 'signals'] = 'short'
    # shift the signals down 1 row to line up with the actual candles they apply to
    data['signals'] = data['signals'].shift(1)
    # create long_moves  and short_moves columns to record all price moves adjusted for trading fees
    data.loc[data['signals'] == 'long', 'long_moves'] = (data.loc[data['signals'] == 'long', 'roc'] * 100) - fees
    data.loc[data['signals'] == 'short', 'short_moves'] = (data.loc[data['signals'] == 'short', 'roc'] * 100) + fees
    next_moves_long = list(data['long_moves'].dropna())
    long_indices = list(data['long_moves'].dropna().index)
    next_moves_short = list(data['short_moves'].dropna())
    short_indices = list(data['short_moves'].dropna().index)
    data.loc[data['signals'] == 'long', 'open_long'] = (data.loc[data['signals'] == 'long', 'open'])
    data.loc[data['signals'] == 'long', 'close_long'] = (data.loc[data['signals'] == 'long', 'close'])
    data.loc[data['signals'] == 'short', 'open_short'] = (data.loc[data['signals'] == 'short', 'open'])
    data.loc[data['signals'] == 'short', 'close_short'] = (data.loc[data['signals'] == 'short', 'close'])

    # filter out results with too few trades for statistical validity
    if len(next_moves_long) > min_trades:
        winrate_long = len(data[data['long_moves'] > 0]) / len(data['long_moves'].dropna())
        # append the percent drop filter value and the mean next move (minus total mean move) to the means list
        results[count] = {'pair': pair,
                          'timeframe': t,
                          'direction': 'long',
                          'ma': ma,
                          'percent': pct,
                          'mean': round(statistics.mean(next_moves_long) - all_mean, 3),
                          'trades': len(next_moves_long),
                          'trades/day': round(len(next_moves_long)/num_days, 3),
                          'winrate': round(winrate_long, 3)
                          }
        if statistics.mean(next_moves_long) - all_mean >= 2:
            print(results[count])
        count += 1
    if len(next_moves_short) > min_trades:
        winrate_short = len(data[data['short_moves'] > 0]) / len(data['short_moves'].dropna())
        # append the percent drop filter value and the mean next move (minus total mean move) to the means list
        results[count] = {'pair': pair,
                          'timeframe': t,
                          'direction': 'short',
                          'ma': ma,
                          'percent': pct,
                          'mean': round(statistics.mean(next_moves_short) - all_mean, 3),
                          'trades': len(next_moves_short),
                          'trades/day': round(len(next_moves_short)/num_days, 3),
                          'winrate': round(winrate_short, 3)
                          }
        if statistics.mean(next_moves_short) - all_mean >= 2:
            print(results[count])
        count += 1

    open_long = data['open_long']
    open_short = data['open_short']

    print(open_long.tail(100))

    # clear the results columns for the next percentage test
    data.drop(['signals', 'long_moves', 'short_moves', 'open_long', 'close_long', 'open_short', 'close_short'], axis=1, inplace=True)

    # return dictionary of stats on results, number of results, and the two lists of actual results (for single backtests)
    # return results, len(next_moves_long) + len(next_moves_short), (long_indices, next_moves_long, short_indices, next_moves_short)
    return results, len(next_moves_long) + len(next_moves_short), (open_long, next_moves_long, open_short, next_moves_short)




def prep_data_sma(data_1m, t, ma):
    data = resample(data_1m, t)
    # limit data to latest 10,500 periods for indicator calculations
    data = data[-10500:]

    data['roc'] = data['close'].pct_change(periods=roc_p)
    data['ma'] = data['close'].rolling(window=ma).mean()
    data['ma_roc'] = data['ma'].pct_change()  # is the sma higher or lower than previous period

    # limit data to latest 10,000 periods to trim off NaNs and focus on recent data
    data = data[-10000:]

    return data

def prep_data_hma(data_1m, t, ma):
    data = resample(data_1m, t)
    # limit data to latest 10,500 periods for indicator calculations
    data = data[-10500:]

    data['roc'] = data['close'].pct_change(periods=roc_p)
    data['ma'] = TA.HMA(data, ma)
    data['ma_roc'] = data['ma'].pct_change()  # is the sma higher or lower than previous period

    # limit data to latest 10,000 periods to trim off NaNs and focus on recent data
    data = data[-10000:]

    return data

def backtest_all(ma_type):
    pairs = get_pairs('BTC')
    pairs = pairs[-10:]
    ma_lengths = [9 , 25, 50, 100, 200]
    timescales = ['5MIN', '15MIN', '1H', '4H', '12H', '1D', '3D', '1W']

    print(f'{len(pairs)} pairs to test - {time.ctime()[:3]} {time.ctime()[9]} at {time.ctime()[11:-8]}')
    print(pairs)
    for n, pair in enumerate(pairs):
        # if n%5 == 0:
        #     print(f'Testing pair {n} of {len(pairs)}')
        try:
            filepath = Path(f'V:/ohlc_data/{pair}-1m-data.csv')
            data_1m = pd.read_csv(filepath, index_col=0)
            data_1m.index = pd.to_datetime(data_1m.index)
        except FileNotFoundError:
            continue
        for ma in ma_lengths:
            for t in timescales:
                if ma_type == 'hma':
                    data = prep_data_hma(data_1m, t, ma)
                elif ma_type == 'sma':
                    data = prep_data_sma(data_1m, t, ma)

                # filter out datasets that don't have enough periods
                if len(data) < (ma + roc_p + min_trades):
                    continue
                #  filter out datasets that contain low satoshi prices (impossible to trade)
                if data['close'].min() < 0.000001:
                    continue

                # cycle through all 100 percentages to test a price drop of any size
                for pct in range(100): # change this back to 100
                    results, keep_going, _ = mean_rev_bt(pair, data, t, ma, pct)

                    # number of results decreases with each percentage, so stop when number reaches 0
                    if not keep_going:
                        break

    # for k, v in results.items():
    #     print(k, v)

    if results:
        df = pd.DataFrame(results)
        df = df.transpose()
        save_path = Path(f'V:/results/mean_rev_candles/')
        if ma_type == 'sma':
            save_file = f'roc_{roc_p}_sma.csv' # incorporate trigger choice in the filename when they are options
        if ma_type == 'hma':
            save_file = f'roc_{roc_p}_hma.csv' # incorporate trigger choice in the filename when they are options
        save_path.mkdir(parents=True, exist_ok=True)
        df.to_csv(save_path / save_file)

def backtest_one(pair, t, ma, pct, ma_type):
    filepath = Path(f'V:/ohlc_data/{pair}-1m-data.csv')
    data_1m = pd.read_csv(filepath, index_col=0)
    data_1m.index = pd.to_datetime(data_1m.index)
    if ma_type == 'hma':
        data = prep_data_hma(data_1m, t, ma)
    elif ma_type == 'sma':
        data = prep_data_sma(data_1m, t, ma)
    results, _, signals = mean_rev_bt(pair, data, t, ma, pct)
    for i in results.values():
        print(f"Average profitablility {i.get('direction')}: {i.get('mean')}, "
              f"num trades: {i.get('trades')}, longs/day: {i.get('longs/day')}, shorts/day: {i.get('shorts/day')}, "
              f"winrate: {i.get('winrate')}")

    return data, signals




backtest_all('sma')

backtest_all('hma')




# data, signals = backtest_one('ROSEBTC', '1H', 50, 2, 'sma')
# plt.plot(data['close'])
# plt.plot(data['ma'])
# plt.show()



# data = data[-100:]
# plt.scatter(data.index, data['open'], marker='_')
# plt.scatter(data.index, data['close'], marker='_')
# # plt.scatter(signals[0], data.loc[signals[0], 'open'], marker=10)
# plt.show()




e = time.perf_counter()
total = round(e-s, 3)
if total < 60:
    print(f'time taken: {total:.3}s')
elif total < 3600:
    print(f'time taken:{int(total / 60)}m, {round(total % 60)}s')
else:
    print(f'time taken:{int(total / 3600)}h, {(int(total / 60)) % 60}m, {round(total % 60)}s')
print(f'All done! - {time.ctime()[:3]} {time.ctime()[9]} at {time.ctime()[11:-8]}')
