import pandas as pd
import os

selected_dir = "/home/hallo/Documents/aetf/selected2"
benchmark_file = os.path.join(selected_dir, "沪深300ETF广发_510360.csv")

etfs = [
    "矿业ETF_561330.csv",
    "浙商之江凤凰ETF_512190.csv",
    "工程机械ETF_560280.csv",
    "电信ETF易方达_563010.csv",
    "半导体设备ETF_561980.csv",
    "中证2000ETF华夏_562660.csv",
    "石油ETF_561360.csv",
    "银行ETF华夏_515020.csv",
    "沪港深500ETF富国_517100.csv",
    "中证500ETF国联_515550.csv"
]

def main():
    print(f"Loading benchmark: {os.path.basename(benchmark_file)}")
    bm_df = pd.read_csv(benchmark_file)
    bm_df['date'] = pd.to_datetime(bm_df['date'])
    bm_df.set_index('date', inplace=True)
    
    # Only take the recent 800 days
    bm_df = bm_df.iloc[-800:]
    
    bm_df['return'] = bm_df['adj_close'].pct_change()
    
    # "fall by more than 0.4%"
    drop_days = bm_df[bm_df['return'] < -0.004].index
    print(f"Found {len(drop_days)} days where benchmark fell by more than 0.4% (in the last 800 days)")

    results = []
    
    for etf_file in etfs:
        path = os.path.join(selected_dir, etf_file)
        if not os.path.exists(path):
            print(f"Warning: {etf_file} not found in {selected_dir}")
            continue
            
        df = pd.read_csv(path)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df['return'] = df['adj_close'].pct_change()
        
        valid_days = drop_days.intersection(df.index)
        
        if len(valid_days) > 1:
            etf_rets = df.loc[valid_days, 'return']
            bm_rets = bm_df.loc[valid_days, 'return']
            
            avg_return_on_drop_days = etf_rets.mean()
            win_rate = (etf_rets > bm_rets).mean()
            positive_rate = (etf_rets > 0).mean()
            corr = etf_rets.corr(bm_rets)
            
            name = etf_file.replace('.csv', '')
            results.append({
                'ETF': name,
                'Avg_Drop_Return(%)': avg_return_on_drop_days * 100,
                'Beat_BM_Rate(%)': win_rate * 100,
                'Positive_Rate(%)': positive_rate * 100,
                'Corr_to_BM': corr,
                'Days_Count': len(valid_days)
            })
            
    if results:
        results_df = pd.DataFrame(results)
        results_df.sort_values('Avg_Drop_Return(%)', ascending=False, inplace=True)
        
        print("\nDefensiveness Evaluation (Ordered by best performance on down days):")
        print("-" * 80)
        print(results_df.round(2).to_string(index=False))
    else:
        print("No results to display.")

if __name__ == "__main__":
    main()
