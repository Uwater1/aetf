import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os

# Font setup for Chinese characters
import matplotlib as mpl
import matplotlib.font_manager as fm
try:
    if os.path.exists('SimHei.ttf'):
        fm.fontManager.addfont('SimHei.ttf')
        prop = fm.FontProperties(fname='SimHei.ttf')
        mpl.rcParams['font.sans-serif'] = [prop.get_name(), 'sans-serif']
    else:
        mpl.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Droid Sans Fallback', 'WenQuanYi Micro Hei', 'SimHei']
    mpl.rcParams['axes.unicode_minus'] = False
except Exception as e:
    print(f"Font loading error: {e}")

# Read the CSV
df = pd.read_csv('portfolio_correlation.csv', index_col=0)

# Strip spaces from index and columns
df.index = df.index.str.strip()
df.columns = df.columns.str.strip()

# Ignore specified ETF
ignore_etf = '中证1000ETF广发_560010'
if ignore_etf in df.index:
    df = df.drop(index=ignore_etf)
if ignore_etf in df.columns:
    df = df.drop(columns=ignore_etf)
# The loaded data might have spaces in values or missing strings like ""
# If we read properly, pandas might read empty cells as NaN
df = df.apply(pd.to_numeric, errors='coerce')

plt.figure(figsize=(14, 12))
sns.heatmap(df, annot=True, cmap='coolwarm', fmt=".2f", linewidths=.5, cbar_kws={"shrink": .8})
plt.title('ETF Portfolio Correlation Matrix')
plt.xticks(rotation=45, ha='right')
plt.yticks(rotation=0)
plt.tight_layout()
plt.savefig('correlation_graph.png', dpi=300)
print("Graph saved successfully as correlation_graph.png")
