import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# Configuration
BASE_DIR = '/home/hallo/Documents/aetf'
SELECTED_DIR = os.path.join(BASE_DIR, 'selected2')
FONT_PATH = os.path.join(BASE_DIR, 'SimHei.ttf')

PORTFOLIO_ETFS = [
    '矿业ETF_561330',
    '浙商之江凤凰ETF_512190',
    '工程机械ETF_560280',
    '电信ETF易方达_563010',
    '半导体设备ETF_561980',
    '中证2000ETF华夏_562660',
    '石油ETF_561360',
    '银行ETF华夏_515020',
    '沪港深500ETF富国_517100',
    '中证500ETF国联_515550',
]
BENCHMARK_ETF = '沪深300ETF广发_510360'

# Setup Font
if os.path.exists(FONT_PATH):
    prop = fm.FontProperties(fname=FONT_PATH)
    plt.rcParams['font.sans-serif'] = [prop.get_name()]
    plt.rcParams['axes.unicode_minus'] = False
else:
    print(f"Warning: Font file {FONT_PATH} not found. Chinese characters might not display correctly.")

def load_and_normalize():
    all_data = {}
    etfs_to_load = PORTFOLIO_ETFS + [BENCHMARK_ETF]
    
    for etf in etfs_to_load:
        file_path = os.path.join(SELECTED_DIR, f"{etf}.csv")
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').set_index('date')
            # Normalize: start at 1.0
            # We want to align them to the start date where all have data
            all_data[etf] = df['adj_close']
        else:
            print(f"Warning: File for {etf} not found.")

    prices = pd.DataFrame(all_data).dropna()
    normalized = prices / prices.iloc[0]
    return normalized

def plot_movements(df):
    plt.figure(figsize=(12, 7))
    
    # Plot portfolio ETFs with thinner lines
    for etf in PORTFOLIO_ETFS:
        if etf in df.columns:
            plt.plot(df.index, df[etf], label=etf, alpha=0.7, linewidth=1.5)
    
    # Plot benchmark with a thicker, distinct line
    if BENCHMARK_ETF in df.columns:
        plt.plot(df.index, df[BENCHMARK_ETF], label=f"Benchmark: {BENCHMARK_ETF}", 
                 color='black', linewidth=3, linestyle='--')
    
    plt.title('ETF Price Movement (Normalized to 1.0)', fontsize=14)
    plt.xlabel('Date')
    plt.ylabel('Cumulative Return')
    plt.legend(loc='upper left', bbox_to_anchor=(1, 1), fontsize=8)
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.tight_layout()
    
    output_image = os.path.join(BASE_DIR, 'etf_movements.png')
    plt.savefig(output_image)
    print(f"Plot saved to {output_image}")

def print_summary(df):
    print("\n" + "="*50)
    print(f"{'ETF Name':<30} | {'Total Return':>12}")
    print("-" * 50)
    
    results = []
    for etf in df.columns:
        total_return = (df[etf].iloc[-1] / df[etf].iloc[0] - 1) * 100
        results.append((etf, total_return))
    
    # Sort by return
    results.sort(key=lambda x: x[1], reverse=True)
    
    for etf, ret in results:
        is_bench = " (Bench)" if etf == BENCHMARK_ETF else ""
        print(f"{etf + is_bench:<30} | {ret:>11.2f}%")
    print("="*50)

if __name__ == "__main__":
    df = load_and_normalize()
    if not df.empty:
        plot_movements(df)
        print_summary(df)
    else:
        print("No data found to plot.")
