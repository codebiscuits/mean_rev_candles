# analysis
# TODO calculate mean/max dd per trade AND mean/max dd per winning trade - if there is a significant
#  difference, it might identify a good stoploss placement (this might work best in the volatility adjusted version)
# TODO group results by timescale and get summary stats like avg profitability, range of profitable %s, most profitable %
# TODO maybe find out if groupby output can be plotted as a set of overlayed charts
# TODO plot profitability over time to see if it is random or if there are trends in profitability which could be anticipated
# TODO plot pairs along x axis and avg profit of each other param on y axis to see if newer pairs are less efficient in any way
# TODO how many signals are generated per % per timeframe? would the lower timeframes benefit from finer % gradations?
# TODO i could plot a moving average of the profitability to see how consistent it is over time

# TODO i can use the statistics on adverse moves to work out what kind of adverse move usually ends up turning around
#  and coming good vs what usually ends up being a big loss. by working out the optimum threshold for setting a stoploss
#  and the average profitable move any given asset makes, it should be possible to calculate an expected R/R

# TODO the adverse move could be measured as a percentage of the difference between open and close on the same candle,
#  or as a percentage of the volatility at that period, or it could be measured as it compares to the low of the signal
#  candle that preceded it

# TODO when the volatility measures are all working and everything is backtested, it might be worth seeing if there is
#  any correlation between volatility scores of a pair and the effectiveness of this strategy for that pair


import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path

pd.set_option("display.precision", 3) # Use 3 decimal places in output display
pd.set_option("display.expand_frame_repr", False) # Don't wrap repr(DataFrame) across additional lines
pd.set_option("display.max_rows", 25) # Set max rows displayed in output to 25

# ma_types = ['sma', 'hma']
# vol_types = ['roc', 'bbw', 'atr']
#
# for ma in ma_types:
#     for vol in vol_types:
#         filepath = Path(f'V:/results/mean_rev_candles/{ma}_{vol}.csv')
#         data = pd.read_csv(filepath, index_col=0)
#         print(f"Total mean {ma}/{vol}: {round(data['mean pnl'].mean(), 3)}")


filepath = Path(f'V:/results/mean_rev_candles/hma_bbw.csv')
data = pd.read_csv(filepath, index_col=0)

print(data.columns)

data_long = data[data['direction'] == 'long']

g_pair = data_long.groupby(['pair'])['mean pnl'].mean()
g_pair = g_pair[g_pair > 0.2]

g_time = data_long.groupby(['timeframe'])['mean pnl'].mean()
g_time = g_time[g_time > 0]

g_ma = data_long.groupby(['ma'])['mean pnl'].mean()
# g_ma = g_ma[g_ma > 0]

g_trig = data_long.groupby(['trigger'])['mean pnl'].mean()
g_trig = g_trig[g_trig > 3]

print('long', g_pair, '\n')
print('long', g_time, '\n')
print('long', g_ma, '\n')
print('long', g_trig, '\n')

# TODO i want a multi-line plot where x is trigger value, y is mean pnl, and each line is a different pair.
#  so i think i would need to groupby pair and trigger, and then plot mean pnl against trigger in a for-loop that loops
#  through assets
plt.plot(g_trig)
plt.show()