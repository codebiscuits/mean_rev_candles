import pandas as pd
from pathlib import Path
import statistics
import keys
from binance.client import Client
import time
from finta import TA
import matplotlib.pyplot as plt
from config import count, results


s = time.perf_counter()

client = Client(api_key=keys.Pkey, api_secret=keys.Skey)

fees = 0.075 * 2 # round-trip trading fees as a percentage
min_trades = 30
roc_p = 1



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

def prep_data(data_1m, t, ma, ma_type, vol_type):
    data = resample(data_1m, t)
    # limit data to latest 10,500 periods for indicator calculations
    data = data[-10500:]

    if ma_type == 'sma':
        data['ma'] = data['close'].rolling(window=ma).mean()
    elif ma_type == 'hma':
        data['ma'] = TA.HMA(data, ma)

    data['roc'] = data['close'].pct_change(periods=roc_p)
    data['ma_roc'] = data['ma'].pct_change()  # is the ma higher or lower than previous period

    if vol_type == 'roc':
        data['vol'] = data['roc']
    if vol_type == 'bbw':
        data['bbw'] = TA.BBWIDTH(data, ma, data['ma'])
        # print('roc', data['roc'].tail())
        # print('atr', data['bbw'].tail())
        data['vol'] = data['roc'] / data['bbw']
        # print('vol min', data['vol'].min(), 'vol max', data['vol'].max())
    elif vol_type == 'atr':
        data['atr'] = TA.ATR(data, 9)
        # print('roc', data['roc'].tail())
        # print('atr', data['atr'].tail())
        data['vol'] = (data['roc'] / data['atr']) * data['close'] # dividing by close price makes it proportional
        # print(t, 'vol min', data['vol'].min(), 'vol max', data['vol'].max())

    # limit data to latest 10,000 periods to trim off NaNs and focus on recent data
    data = data[-10000:]

    return data

def mean_rev_bt(pair, data, t, ma, trig_vol):
    global count

    days_calc = {'5MIN': 0.003472, '15MIN': 0.0104167, '1H': 0.041667, '4H': 0.166667, '12H': 0.5, '1D': 1, '3D': 3, '1W': 7}

    num_days = len(data) * days_calc.get(t)

    # calculate mean % change of all periods to use as a baseline comparison
    all_mean = data['roc'].mean()

    # create signals column and enter 'long' or 'short' on each row that satisfies the conditions
    # print(f'Testing vol:{trig_vol}')
    data.loc[(data['vol'] < (0 - trig_vol)) & (data['ma_roc'] > 0), 'signals'] = 'long'
    data.loc[(data['vol'] > trig_vol) & (data['ma_roc'] < 0), 'signals'] = 'short'
    # shift the signals down 1 row to line up with the actual candles they apply to
    data['signals'] = data['signals'].shift(1)
    # create long_moves  and short_moves columns to record all price moves adjusted for trading fees
    data.loc[data['signals'] == 'long', 'long_moves'] = (data.loc[data['signals'] == 'long', 'roc'] * 100) - fees
    data.loc[data['signals'] == 'short', 'short_moves'] = (data.loc[data['signals'] == 'short', 'roc'] * 100) + fees
    pnl_long = list(data['long_moves'].dropna())
    pnl_short = list(data['short_moves'].dropna())
    pnl_short = [0 - p for p in pnl_short] # invert values in list to represent profits/losses from down moves

    # record the open and close prices
    data.loc[data['signals'] == 'long', 'open_long'] = (data.loc[data['signals'] == 'long', 'open'])
    data.loc[data['signals'] == 'long', 'close_long'] = (data.loc[data['signals'] == 'long', 'close'])
    data.loc[data['signals'] == 'short', 'open_short'] = (data.loc[data['signals'] == 'short', 'open'])
    data.loc[data['signals'] == 'short', 'close_short'] = (data.loc[data['signals'] == 'short', 'close'])

    # record the % adverse price moves during trade candles (how low is the low compared to the open)
    data.loc[data['signals'] == 'long', 'adv_move_l'] = (100 * (data.loc[data['signals'] == 'long', 'low'] -
                                                          data.loc[data['signals'] == 'long', 'open']) /
                                                         data.loc[data['signals'] == 'long', 'open'])
    mean_adv_move_l = round(data['adv_move_l'].dropna().mean(), 3)
    std_adv_move_l = round(data['adv_move_l'].dropna().std(), 3)
    data.loc[data['signals'] == 'short', 'adv_move_s'] = (100 * (data.loc[data['signals'] == 'short', 'high'] -
                                                          data.loc[data['signals'] == 'short', 'open']) /
                                                         data.loc[data['signals'] == 'short', 'open'])
    mean_adv_move_s = round(data['adv_move_s'].dropna().mean(), 3)
    std_adv_move_s = round(data['adv_move_s'].dropna().std(), 3)
    # # record the % adverse price moves only during WINNING trade candles
    # long_win = data['signals'] == 'long' & data['roc'] > 0
    # short_win = data['signals'] == 'short' & data['roc'] < 0
    # data.loc[long_win, 'adv_move_lw'] = (100 * (data.loc[long_win, 'low'] - data.loc[long_win, 'open']) /
    #                                     data.loc[long_win, 'open'])
    # mean_adv_move_lw = round(data['adv_move_lw'].dropna().mean(), 3)
    # std_adv_move_lw = round(data['adv_move_lw'].dropna().std(), 3)
    # data.loc[short_win, 'adv_move_sw'] = (100 * (data.loc[short_win, 'high'] - data.loc[short_win, 'open']) /
    #                                       data.loc[short_win, 'open'])
    # mean_adv_move_sw = round(data['adv_move_sw'].dropna().mean(), 3)
    # std_adv_move_sw = round(data['adv_move_sw'].dropna().std(), 3)

    # filter out results with too few trades for statistical validity
    if len(pnl_long) > min_trades:
        winrate_long = len(data[data['long_moves'] > 0]) / len(data['long_moves'].dropna())
        # append the percent drop filter value and the mean next move (minus total mean move) to the means list
        results[count] = {'pair': pair,
                          'timeframe': t,
                          'direction': 'long',
                          'ma': ma,
                          'trigger': trig_vol,
                          'mean pnl': round(statistics.mean(pnl_long) - all_mean, 3),
                          'trades': len(pnl_long),
                          'trades/day': round(len(pnl_long) / num_days, 3),
                          'winrate': round(winrate_long, 3),
                          'mean_adv_move': mean_adv_move_l,
                          'std_adv_move': std_adv_move_l,
                          # 'mean_adv_move_w': mean_adv_move_lw,
                          # 'std_adv_move_w': std_adv_move_lw,
                          }
        # if statistics.mean(pnl_long) - all_mean >= 2:
        #     print(results[count])
        count += 1
    if len(pnl_short) > min_trades:
        winrate_short = len(data[data['short_moves'] > 0]) / len(data['short_moves'].dropna())
        # append the percent drop filter value and the mean next move (minus total mean move) to the means list
        results[count] = {'pair': pair,
                          'timeframe': t,
                          'direction': 'short',
                          'ma': ma,
                          'trigger': trig_vol,
                          'mean pnl': round(statistics.mean(pnl_short) - all_mean, 3),
                          'trades': len(pnl_short),
                          'trades/day': round(len(pnl_short) / num_days, 3),
                          'winrate': round(winrate_short, 3),
                          'mean_adv_move': mean_adv_move_s,
                          'std_adv_move': std_adv_move_s,
                          # 'mean_adv_move_w': mean_adv_move_sw,
                          # 'std_adv_move_w': std_adv_move_sw
                          }
        # if statistics.mean(pnl_short) - all_mean >= 2:
        #     print(results[count])
        count += 1

    open_long = data['open_long']
    open_short = data['open_short']

    # clear the results columns for the next percentage test
    data.drop(['signals', 'long_moves', 'short_moves', 'open_long', 'close_long',
               'open_short', 'close_short', 'adv_move_l', 'adv_move_s'], axis=1, inplace=True)

    # return dictionary of stats on results, number of results, and the two lists of actual results (for single backtests)
    # return results, len(pnl_long) + len(pnl_short), (long_indices, pnl_long, short_indices, pnl_short)
    return results, len(pnl_long) + len(pnl_short), (open_long, pnl_long, open_short, pnl_short)

def backtest_all(ma_type, vol_type):
    pairs = get_pairs('BTC')
    # pairs = ['ETHBTC']
    ma_lengths = [9
        , 25, 50, 100, 200
                  ]
    timescales = ['5MIN', '15MIN', '1H', '4H', '12H', '1D', '3D', '1W']

    print(f'Running {ma_type}/{vol_type} tests on {len(pairs)} pairs - '
          f'{time.ctime()[:3]} {time.ctime()[9]} at {time.ctime()[11:-8]}')
    # print(pairs)
    for n, pair in enumerate(pairs):
        if n%10 == 0:
            print(f'Testing pair {n} of {len(pairs)}')
        try:
            filepath = Path(f'V:/ohlc_data/{pair}-1m-data.csv')
            data_1m = pd.read_csv(filepath, index_col=0)
            data_1m.index = pd.to_datetime(data_1m.index)
        except FileNotFoundError:
            continue
        for ma in ma_lengths:
            for t in timescales:
                # print(f'------------------------------------ Testing {t} ------------------------------------')
                data = prep_data(data_1m, t, ma, ma_type, vol_type)

                # filter out datasets that don't have enough periods
                if len(data) < (ma + roc_p + min_trades):
                    continue
                #  filter out datasets that contain low satoshi prices (impossible to trade)
                if data['close'].min() < 0.000001:
                    continue


                # cycle through all 100 percentages to test a price drop of any size
                vol_std = data['vol'].std()
                for vol in range(100):
                    # print(f'Testing range {vol}')
                    if vol_type == 'roc':
                        vol *= (vol_std / 6) # scale the 100 values to appropriate range to test
                    elif vol_type == 'bbw':
                        vol *= (vol_std / 8)
                    elif vol_type == 'atr':
                        vol *= (vol_std / 8)

                    results, keep_going, _ = mean_rev_bt(pair, data, t, ma, vol)

                    # number of results decreases with each percentage, so stop when number reaches 0
                    if not keep_going:
                        break

    # for k, v in results.items():
    #     print(k, v)

    if results:
        df = pd.DataFrame(results)
        df = df.transpose()
        save_path = Path(f'V:/results/mean_rev_candles/')
        save_file = f'{ma_type}_{vol_type}.csv' # incorporate trigger choice in the filename when they are options
        save_path.mkdir(parents=True, exist_ok=True)
        df.to_csv(save_path / save_file)

def backtest_one(pair, t, ma, pct, ma_type, vol_type):
    filepath = Path(f'V:/ohlc_data/{pair}-1m-data.csv')
    data_1m = pd.read_csv(filepath, index_col=0)
    data_1m.index = pd.to_datetime(data_1m.index)
    data = prep_data(data_1m, t, ma, ma_type, vol_type)
    #  filter out datasets that contain low satoshi prices (impossible to trade)
    if data['close'].min() < 0.000001:
        print(f'{pair} satoshi price too low for profitable trading')
    else:
        # print(data['vol'].head(20))
        results, _, signals = mean_rev_bt(pair, data, t, ma, pct)
        # for k, i in results.items():
        #     print(k, f"Average profitablility {i.get('direction')}: {i.get('mean pnl')}, "
        #           f"num trades: {i.get('trades')}, trades/day: {i.get('trades/day')}, winrate: {i.get('winrate')}")

        return results, signals

def multi_line_plot():
    # example code for line plot with multiple lines and legend
    # line 1 points
    x1 = [10, 20, 30]
    y1 = [20, 40, 10]
    # plotting the line 1 points
    plt.plot(x1, y1, label="line 1")
    # line 2 points
    x2 = [10, 20, 30]
    y2 = [40, 10, 30]
    # plotting the line 2 points
    plt.plot(x2, y2, label="line 2")
    plt.xlabel('x - axis')
    # Set the y axis label of the current axis.
    plt.ylabel('y - axis')
    # Set a title of the current axes.
    plt.title('Two or more lines on same plot with suitable legends ')
    # show a legend on the plot
    plt.legend()
    # Display a figure.
    plt.show()



# ma_types = ['sma', 'hma']
# vol_types = ['roc', 'bbw', 'atr']
# # ma_types = ['sma']
# # vol_types = ['atr']
#
# for ma_type in ma_types:
#     for vol_type in vol_types:
#         s1 = time.perf_counter()
#         count = 0
#         results = {}
#         backtest_all(ma_type, vol_type)
#         e1 = time.perf_counter()
#         t1 = e1-s1
#         if t1 < 60:
#             print(f'time taken: {t1:.3}s')
#         elif t1 < 3600:
#             print(f'time taken:{int(t1 / 60)}m {round(t1 % 60)}s')
#         else:
#             print(f'time taken:{int(t1 / 3600)}h {(int(t1 / 60)) % 60}m {round(t1 % 60)}s')


# count = 0
# results = {}
# try:
#     data, signals = backtest_one('HOTBTC', '1D', 100, 0, 'hma', 'bbw')
# except TypeError:
#     pass
# plt.hist(data['trigger'], 100, label='vol', color='#00990099')
# plt.legend()
# plt.show()


# data = data[-100:]
# plt.scatter(data.index, data['open'], marker='_')
# plt.scatter(data.index, data['close'], marker='_')
# # plt.scatter(signals[0], data.loc[signals[0], 'open'], marker=10)
# plt.show()



if __name__ == '__main__':
    print(f'All done! - {time.ctime()[:3]} {time.ctime()[9]} at {time.ctime()[11:-8]}')
    e = time.perf_counter()
    total = round(e-s, 3)
    if total < 60:
        print(f'Total time taken: {total:.3}s')
    elif total < 3600:
        print(f'Total time taken:{int(total / 60)}m {round(total % 60)}s')
    else:
        print(f'Total time taken:{int(total / 3600)}h {(int(total / 60)) % 60}m {round(total % 60)}s')
