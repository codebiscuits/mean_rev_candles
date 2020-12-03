from main import get_pairs, backtest_one
from pathlib import Path
import pandas as pd


p = []
pnl = []
t = '1D'
ma = 100
pct = 0.1
mat = 'hma'
vt = 'bbw'


for pair in get_pairs('BTC'):
    ohlcpath = Path(f'V:/ohlc_data/{pair}-1m-data.csv')
    if ohlcpath.exists():
        count = 0
        results = {}
        try:
            res, signals = backtest_one(pair, t, ma, pct, mat, vt)
        except TypeError:
            continue
        if 0 in res:
            m_pnl = res[0].get('mean pnl') + 1
            t_y = res[0].get('trades/day') * 360
            pnl_y = ((m_pnl ** t_y) - 1) * 100
            p.append(pair)
            pnl.append(m_pnl)
            if pnl_y > 100:
                print(f'{pair} long annual PnL: {pnl_y:.3}%')
pnl_df = pd.DataFrame({'pair': p, 'mean pnl': pnl})
res_path = Path(f'V:/results/mean_rev_candles/same-params_all-pairs/')
res_file = Path(f't{t}_ma{ma}{mat}_pct{pct}_{vt}.csv')
res_path.mkdir(parents=True, exist_ok=True)
pnl_df.to_csv(res_path / res_file)