import os
import pandas as pd
import numpy as np
import glob
from datetime import datetime

# Constants
BASE_DIR = '/home/hallo/Documents/aetf'
SELECTED_DIR = os.path.join(BASE_DIR, 'selected')
RF_FILE = os.path.join(BASE_DIR, 'riskFreeRate.csv')
OUTPUT_FILE = os.path.join(BASE_DIR, 'etf_evaluation.csv')

def calculate_drawdown_metrics(series):
    roll_max = series.cummax()
    drawdown = (series - roll_max) / roll_max
    max_drawdown = drawdown.min()
    
    # Calculate Max Drawdown Duration
    is_drawdown = drawdown < 0
    # Create groups of consecutive drawdowns
    drawdown_groups = (is_drawdown != is_drawdown.shift()).cumsum()
    # Mask to only keep drawdown periods
    drawdown_periods = drawdown_groups[is_drawdown]
    
    if drawdown_periods.empty:
        max_duration = 0
    else:
        # Count duration in each group
        durations = drawdown_periods.value_counts()
        max_duration = durations.max()
        
    return max_drawdown, int(max_duration)

def format_pct(val):
    if pd.isna(val):
        return ""
    return f"{round(val * 100, 4)}%"

def format_num(val):
    if pd.isna(val):
        return ""
    return round(val, 4)

def evaluate_etf():
    print(f"Loading risk free rate from {RF_FILE}...")
    if not os.path.exists(RF_FILE):
        print(f"Error: {RF_FILE} not found.")
        return

    # Load Risk Free Rate
    rf_df = pd.read_csv(RF_FILE)
    rf_df['date'] = pd.to_datetime(rf_df['time'])
    rf_df = rf_df.sort_values('date')
    rf_df = rf_df.set_index('date')
    rf_daily = rf_df['close'] / (100.0 * 252.0)

    results = []
    
    files = glob.glob(os.path.join(SELECTED_DIR, "*.csv"))
    print(f"Found {len(files)} ETF files in {SELECTED_DIR}")
    
    for i, file_path in enumerate(files):
        filename = os.path.basename(file_path)
        name = filename.replace('.csv', '')
        
        if (i + 1) % 50 == 0:
            print(f"Processing... {i+1}/{len(files)}")
            
        try:
            df = pd.read_csv(file_path)
            if df.empty:
                continue
                
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            df = df.set_index('date')
            
            df['return'] = df['adj_close'].pct_change()
            
            df = df.join(rf_daily.rename('rf_daily'), how='left')
            df['rf_daily'] = df['rf_daily'].ffill().bfill() 
            
            last_date = df.index[-1]
            
            def get_period_return(years):
                target_date = last_date - pd.DateOffset(years=years)
                idx = df.index.asof(target_date)
                if pd.isna(idx):
                    return np.nan
                start_price = df.loc[idx, 'adj_close']
                end_price = df.loc[last_date, 'adj_close']
                if start_price == 0 or pd.isna(start_price):
                    return np.nan
                return (end_price - start_price) / start_price

            ret_1y = get_period_return(1)
            ret_3y = get_period_return(3)
            ret_5y = get_period_return(5)
            
            # Use recent 600 lines for metrics to avoid historical bias (e.g. A-share historical drops)
            df_recent = df.tail(600).copy()
            
            df_recent['excess_return'] = df_recent['return'] - df_recent['rf_daily']
            
            mean_excess_daily = df_recent['excess_return'].mean()
            std_excess_daily = df_recent['excess_return'].std()
            
            if std_excess_daily > 0 and not pd.isna(mean_excess_daily):
                adjusted_sharp = (mean_excess_daily / std_excess_daily) * np.sqrt(252)
            else:
                adjusted_sharp = np.nan
                
            mean_ret_daily = df_recent['return'].mean()
            std_ret_daily = df_recent['return'].std()
            if std_ret_daily > 0 and not pd.isna(mean_ret_daily):
                sharp = (mean_ret_daily / std_ret_daily) * np.sqrt(252)
            else:
                sharp = np.nan
            
            # Annualized Return using CAGR formula on recent data: (Final/Start)^(252/n) - 1
            if len(df_recent) > 1:
                start_p = df_recent['adj_close'].iloc[0]
                end_p = df_recent['adj_close'].iloc[-1]
                if start_p > 0:
                    ann_return = (end_p / start_p) ** (252 / len(df_recent)) - 1
                else:
                    ann_return = np.nan
            else:
                ann_return = np.nan

            ann_vol = std_ret_daily * np.sqrt(252) if not pd.isna(std_ret_daily) else np.nan
            
            max_dd, max_dd_duration = calculate_drawdown_metrics(df_recent['adj_close'])
            
            calmar = (ann_return / abs(max_dd)) if (not pd.isna(ann_return) and max_dd != 0) else np.nan

            downside_returns = df_recent[df_recent['return'] < 0]['return']
            downside_std = downside_returns.std()
            if downside_std > 0 and not pd.isna(mean_ret_daily):
                sortino = (mean_ret_daily / downside_std) * np.sqrt(252)
            else:
                sortino = np.nan
            
            results.append({
                'name': name,
                '1yReturn': format_pct(ret_1y),
                '3yReturn': format_pct(ret_3y),
                '5yReturn': format_pct(ret_5y),
                'Sharp': format_num(sharp),
                'AdjustedSharp': format_num(adjusted_sharp),
                'Sortino': format_num(sortino),
                'Calmar': format_num(calmar),
                'AnnualizedReturn': format_pct(ann_return),
                'Volatility': format_pct(ann_vol),
                'MaxDrawdown': format_pct(max_dd),
                'MaxDrawdownDuration': max_dd_duration,
                'TotalDays': len(df),
                'StartDate': df.index[0].strftime('%Y-%m-%d'),
                'EndDate': df.index[-1].strftime('%Y-%m-%d')
            })
            
        except Exception as e:
            print(f"Error processing {name}: {e}")
            
    if not results:
        print("No results to save.")
        return
        
    # Save to CSV
    res_df = pd.DataFrame(results)
    
    # Sort by AdjustedSharp descending for better readability
    res_df = res_df.sort_values('AdjustedSharp', ascending=False)
    
    res_df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nEvaluation complete.")
    print(f"Top 5 ETFs by AdjustedSharp:")
    print(res_df[['name', 'AdjustedSharp', '1yReturn', 'AnnualizedReturn']].head(5))
    print(f"\nFull results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    evaluate_etf()
