import os
import pandas as pd

SOURCE_DIR = '/home/hallo/Documents/aetf/selected'
TARGET_DIR = '/home/hallo/Documents/aetf/selected3'
os.makedirs(TARGET_DIR, exist_ok=True)

groups = {
    '中证500.csv': [
        ('中证500ETF广发_510510.csv', 3),
        ('中证500ETF_510500.csv', 1),
        ('中证500增强ETF易方达_563030.csv', 4)
    ],
    '银行.csv': [
        ('银行ETF华夏_515020.csv', 2),
        ('银行ETF天弘_515290.csv', 1),
        ('银行ETF鹏华_512730.csv', 1)
    ],
    '有色矿业.csv': [
        ('有色金属ETF_512400.csv', 1),
        ('矿业ETF_561330.csv', 3)
    ],
    '浙商凤凰.csv': [
        ('浙商之江凤凰ETF_512190.csv', 1)
    ],
    '沪港深500.csv': [
        ('沪港深500ETF_517000.csv', 1),
        ('沪港深500ETF富国_517100.csv', 1)
    ],
    '电信.csv': [
        ('电信ETF易方达_563010.csv', 1)
    ],
    '芯片.csv': [
        ('科创芯片ETF_588200.csv', 1),
        ('半导体设备ETF_561980.csv', 2),
        ('半导体设备ETF华夏_562590.csv', 1)
    ],
    '工程机械.csv': [
        ('工程机械ETF_560280.csv', 1)
    ],
    '中证2000.csv': [
        ('中证2000ETF华夏_562660.csv', 1)
    ],
    '石油.csv': [
        ('石油ETF_561360.csv', 1)
    ],
    '沪深300.csv': [
        ('沪深300ETF华夏_510330.csv', 1),
        ('沪深300ETF华泰柏瑞_510300.csv', 1),
        ('沪深300ETF工银_510350.csv', 1),
        ('沪深300ETF广发_510360.csv', 1)
    ]
}

columns_to_merge = ['open', 'high', 'low', 'close', 'adj_close', 'volume', 'dividend']

def combine_group(target_name, members):
    price_dfs = []
    
    for filename, weight in members:
        path = os.path.join(SOURCE_DIR, filename)
        if not os.path.exists(path):
            print(f"Warning: {path} not found")
            continue
        df = pd.read_csv(path)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').set_index('date')
        
        # Multiply all relevant columns by weight
        # We follow the formula: sum(col_i * weight_i)
        available_cols = [c for c in columns_to_merge if c in df.columns]
        weighted_df = df[available_cols] * weight
        price_dfs.append(weighted_df)
    
    if not price_dfs:
        return
    
    # Inner join to ensure we have data for all members in the group
    combined = pd.concat(price_dfs, axis=1, join='inner')
    
    # Sum values across identical column names
    # Using transpose + groupby to avoid axis=1 deprecation
    final_df = combined.T.groupby(level=0).sum().T
    
    # Ensure correct column order and round to 4 decimal places
    final_cols = [c for c in columns_to_merge if c in final_df.columns]
    final_df = final_df[final_cols].round(4)
    
    final_df = final_df.reset_index()
    
    target_path = os.path.join(TARGET_DIR, target_name)
    final_df.to_csv(target_path, index=False)
    print(f"Created {target_path} (4 d.p.)")

# Combine groups
for target, members in groups.items():
    combine_group(target, members)
