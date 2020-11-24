# This is a whole new strategy which doesn't necessarily need to be backtested in the traditional way,
# but i could plot a moving average of the profitability to see how consistent it is over time

# TODO 2 test and fix the count of data points for validating average metrics
# TODO 3 get some kind of multithreading/multiprocessing going or work out a pandas native way to speed things up
# TODO 4 set up a way of saving the results to a file
# TODO 5 get it on the machine upstairs
# TODO 6 try making the trigger move a scalar of atr or some other volatility metricpipenv install python-binance


import pandas as pd
from pathlib import Path
import statistics
import keys
from binance.client import Client
import time


client = Client(api_key=keys.Pkey, api_secret=keys.Skey)


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

def mean_rev(pair, ma_len, pair_num, roc_p):
    try:
        filepath = Path(f'V:/ohlc_data/{pair}-1m-data.csv')
        data_1m = pd.read_csv(filepath, index_col=0)
        data_1m.index = pd.to_datetime(data_1m.index)
        timescales = ['5MIN', '15MIN', '1H', '4H', '12H', '1D', '3D', '1W']
        fees = 0.075 * 2 # round-trip trading fees as a percentage

        for t in timescales:
            data = resample(data_1m, t)
            # limit data to latest 10,000 periods
            data = data[-10000:]
            min_price = data['close'].min()

            # filter out datasets that don't have enough periods or contain low satoshi prices (impossible to trade)
            if len(data) < ma_len or min_price < 0.000001:
                continue


            data['roc'] = data['close'].pct_change(periods=roc_p)
            data['sma'] = data['close'].rolling(window=ma_len).mean()

            all_mean = data['roc'].mean()

            means_long = []
            means_short = []

            # cycle through all 100 percentages to test a price drop of any size
            for pct in range(100):
                next_moves_long = []
                next_moves_short = []

                # cycle through each period in the data
                for i in range(len(data) - 1):
                    # long condition
                    # if price dropped more than the test % this period and the sma is trending up
                    if data.iloc[i, 5] < (0 - (pct / 100)) and data.iloc[i, 6] > data.iloc[i - 1, 6]:
                        # append the following period's price move minus fees to next_moves_long
                        next_move_long = (data.iloc[i + 1, 5]) * 100
                        next_moves_long.append(next_move_long - fees)
                    # short condition
                    # if price rose more than the test % this period and the sma is trending down
                    if data.iloc[i, 5] > (pct / 100) and data.iloc[i, 6] < data.iloc[i - 1, 6]:
                        # append the following period's price move minus (plus) fees to next_moves_short
                        next_move_short = (data.iloc[i + 1, 5] - all_mean) * 100
                        next_moves_short.append(next_move_short + fees)

                # filter out results with too few trades for statistical validity
                if len(next_moves_long) > 25:
                    # append the percent drop filter value and the mean next move (minus total mean move) to the means list
                    means_long.append((pct, statistics.mean(next_moves_long) - all_mean))
                if len(next_moves_short) > 25:
                    # append the percent drop filter value and the mean next move (minus total mean move) to the means list
                    means_short.append((pct, statistics.mean(next_moves_short) - all_mean))

            if means_long:
                # sort the means lists and return the entry with the best mean
                best_pct_long = sorted(means_long, key=lambda x: x[1])[-1][0]
                best_mean_long = sorted(means_long, key=lambda x: x[1])[-1][1]
                if best_mean_long > 2:
                    print(f'{pair_num}: {pair} {t}, {ma_len}sma - '
                        f'best: {best_pct_long}% drop -> {best_mean_long:.3}% avg move '
                        f'({len(means_long)} data points)')
            if means_short:
                best_pct_short = sorted(means_short, key=lambda x: x[1])[0][0]
                best_mean_short = sorted(means_short, key=lambda x: x[1])[0][1]
                # filter out results with poor means
                if best_mean_short < -2:
                    print(f'{pair_num}: {pair} {t}, {ma_len}sma - '
                        f'{best_pct_short}% rise -> {best_mean_short:.3}% avg move '
                        # f'({len(means_short)} data points)'
                          )
    except FileNotFoundError:
        pass




pairs = get_pairs('BTC')
pairs = pairs[::-1]
print(f'{len(pairs)} pairs to test - {time.ctime()[:3]} {time.ctime()[9]} at {time.ctime()[11:-8]}')

ma_lengths = [9, 25, 50, 100, 200]

for a in range(len(pairs)):
    for ma in ma_lengths:
        mean_rev(pairs[a], ma, a, 1)

print(f'All done! - {time.ctime()[:3]} {time.ctime()[9]} at {time.ctime()[11:-8]}')
