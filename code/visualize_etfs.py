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
try:
    if os.path.exists(FONT_PATH):
        fm.fontManager.addfont(FONT_PATH)
        prop = fm.FontProperties(fname=FONT_PATH)
        plt.rcParams['font.sans-serif'] = [prop.get_name(), 'sans-serif']
    else:
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Droid Sans Fallback', 'WenQuanYi Micro Hei', 'SimHei']
    plt.rcParams['axes.unicode_minus'] = False
except Exception as e:
    print(f"Font loading error: {e}")

def format_name(full_name):
    """Remove the _###### suffix for cleaner labels."""
    if '_' in full_name:
        return full_name.split('_')[0]
    return full_name

def load_and_normalize():
    all_data = {}
    etfs_to_load = PORTFOLIO_ETFS + [BENCHMARK_ETF]
    
    for etf in etfs_to_load:
        file_path = os.path.join(SELECTED_DIR, f"{etf}.csv")
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').set_index('date')
            all_data[format_name(etf)] = df['adj_close']
        else:
            print(f"Warning: File for {etf} not found.")

    prices = pd.DataFrame(all_data).dropna()
    normalized = prices / prices.iloc[0]
    return normalized

def plot_movements(df):
    plt.figure(figsize=(20, 10))
    
    formatted_etfs = [format_name(e) for e in PORTFOLIO_ETFS]
    formatted_bench = format_name(BENCHMARK_ETF)

    # Plot portfolio ETFs with thinner lines
    for etf in formatted_etfs:
        if etf in df.columns:
            plt.plot(df.index, df[etf], label=etf, alpha=0.8, linewidth=1.5)
    
    # Plot benchmark with a thicker, distinct line
    if formatted_bench in df.columns:
        plt.plot(df.index, df[formatted_bench], label=f"Benchmark: {formatted_bench}", 
                 color='black', linewidth=3.5, linestyle='--', zorder=10)
    
    plt.title('ETF Portfolio Price Performance (Relative to Start)', fontsize=18, fontweight='bold', pad=20)
    plt.xlabel('Date', fontsize=14)
    plt.ylabel('Normalized NAV (Start = 1.0)', fontsize=14)
    
    # Move legend to top left corner inside the plot
    plt.legend(loc='upper left', fontsize=11, frameon=True, framealpha=0.9, shadow=True)
    
    plt.grid(True, which='both', linestyle=':', alpha=0.6)
    plt.xticks(fontsize=12)
    plt.yticks(fontsize=12)
    plt.tight_layout()
    
    output_image = os.path.join(BASE_DIR, 'etf_movements.png')
    plt.savefig(output_image, dpi=300)
    print(f"Wide high-resolution plot saved to {output_image}")

def print_summary(df):
    print("\n" + "="*50)
    print(f"{'ETF Name':<25} | {'Total Return':>12}")
    print("-" * 50)
    
    formatted_bench = format_name(BENCHMARK_ETF)
    results = []
    for etf in df.columns:
        total_return = (df[etf].iloc[-1] / df[etf].iloc[0] - 1) * 100
        results.append((etf, total_return))
    
    # Sort by return
    results.sort(key=lambda x: x[1], reverse=True)
    
    for etf, ret in results:
        suffix = " (Bench)" if etf == formatted_bench else ""
        print(f"{etf + suffix:<25} | {ret:>11.2f}%")
    print("="*50)

if __name__ == "__main__":
    df = load_and_normalize()
    if not df.empty:
        plot_movements(df)
        print_summary(df)
    else:
        print("No data found to plot.")
