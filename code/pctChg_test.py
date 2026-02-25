import pandas as pd
import numpy as np

def test_pctChg():
    df = pd.read_csv('/home/hallo/Documents/aetf/selected/ZZHL_000922_XSHG.csv')
    
    # 1. today open/close
    # (today close / today open - 1) * 100
    df['test1'] = (df['close'] / df['open'] - 1) * 100
    
    # 2. yestoday close/ today close
    # Here we can use `close` shifted by 1 or `preclose`
    # (today close / yesterday close(shifted) - 1) * 100
    df['test2'] = (df['close'] / df['close'].shift(1) - 1) * 100
    
    # 3. preclose / today close
    # `preclose` usually means yesterday's close adjusted for dividends.
    # (today close / preclose - 1) * 100
    df['test3'] = (df['close'] / df['preclose'] - 1) * 100

    print("Mean Absolute Differences vs pctChg (excluding NaNs):")
    print(f"1. (Today Close / Today Open - 1) * 100:           {(df['test1'] - df['pctChg']).abs().mean():.6f}")
    print(f"2. (Today Close / Yesterday Close - 1) * 100:      {(df['test2'] - df['pctChg']).abs().mean():.6f}")
    print(f"3. (Today Close / Preclose - 1) * 100:             {(df['test3'] - df['pctChg']).abs().mean():.6f}")
    
    # Let's find rows where yesterday's close != today's preclose (e.g. dividends/splits)
    df['yesterday_close'] = df['close'].shift(1)
    diff_mask = (df['yesterday_close'].round(4) != df['preclose'].round(4)) & df['yesterday_close'].notnull()
    
    print("\nDates where Preclose != Yesterday's Close (Dividend/Split days):")
    cols_to_show = ['date', 'yesterday_close', 'preclose', 'close', 'pctChg', 'test2', 'test3']
    print(df[diff_mask][cols_to_show].head(10))

if __name__ == '__main__':
    test_pctChg()
