#!/usr/bin/env python3
"""
Portfolio ETF Selection Script

Selects ETFs that form a diversified portfolio with:
1. Relatively high AdjustedSharpe ratio
2. Low pairwise correlation among selected ETFs

Algorithm:
- Pre-filter ETFs with AdjustedSharpe >= threshold
- Build pairwise correlation matrix from last 600 days of daily returns
- Greedy selection: pick highest AdjustedSharpe first, then iteratively add
  ETFs that have correlation < max_corr with ALL already-selected ETFs
"""

import os
import glob
import pandas as pd
import numpy as np

# ─── Configuration ───────────────────────────────────────────────────────────
BASE_DIR = '/home/hallo/Documents/aetf'
SELECTED_DIR = os.path.join(BASE_DIR, 'selected2')
EVAL_FILE = os.path.join(BASE_DIR, 'etf_evaluation.csv')
OUTPUT_CORR = os.path.join(BASE_DIR, 'portfolio_correlation.csv')

MIN_ADJUSTED_SHARPE = 0.7      # Pre-filter threshold
MAX_CORRELATION = 0.70          # Max allowed pairwise correlation
RECENT_DAYS = 600               # Use last N trading days for correlation
TARGET_MIN = 10                 # Minimum ETFs to select
TARGET_MAX = 20                 # Maximum ETFs to select


def load_evaluation():
    """Load ETF evaluation data and filter by AdjustedSharpe."""
    df = pd.read_csv(EVAL_FILE)
    # Parse AdjustedSharp as float
    df['AdjSharp_val'] = pd.to_numeric(df['AdjustedSharp'], errors='coerce')
    df = df.dropna(subset=['AdjSharp_val'])
    df = df[df['AdjSharp_val'] >= MIN_ADJUSTED_SHARPE]
    df = df.sort_values('AdjSharp_val', ascending=False).reset_index(drop=True)
    print(f"Pre-filtered: {len(df)} ETFs with AdjustedSharpe >= {MIN_ADJUSTED_SHARPE}")
    return df


def load_returns(names_set):
    """Load daily returns from selected2/ for the given ETF names."""
    returns_dict = {}
    for filepath in glob.glob(os.path.join(SELECTED_DIR, "*.csv")):
        name = os.path.basename(filepath).replace('.csv', '')
        if name not in names_set:
            continue
        try:
            df = pd.read_csv(filepath)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').set_index('date')
            # Use last RECENT_DAYS rows
            df = df.tail(RECENT_DAYS)
            ret = df['adj_close'].pct_change().dropna()
            if len(ret) >= 100:
                returns_dict[name] = ret
        except Exception as e:
            print(f"  Error loading {name}: {e}")
    print(f"Loaded returns for {len(returns_dict)} ETFs")
    return returns_dict


def build_correlation_matrix(returns_dict):
    """Build pairwise correlation matrix from daily returns."""
    combined = pd.DataFrame(returns_dict)
    corr = combined.corr(min_periods=100)
    print(f"Correlation matrix shape: {corr.shape}")
    return corr


def greedy_select(eval_df, corr_matrix, max_corr, target_max):
    """Greedy selection: pick ETFs with highest AdjustedSharpe that are
    low-correlated with all already-selected ETFs."""
    available = list(eval_df['name'])
    # Only consider ETFs present in the correlation matrix
    available = [n for n in available if n in corr_matrix.index]

    selected = []
    for candidate in available:
        if len(selected) >= target_max:
            break

        if len(selected) == 0:
            selected.append(candidate)
            continue

        # Check correlation with ALL selected ETFs
        corr_values = [
            abs(corr_matrix.loc[candidate, s])
            for s in selected
            if not pd.isna(corr_matrix.loc[candidate, s])
        ]

        if not corr_values:
            # No valid correlation data, treat as uncorrelated
            max_corr_with_selected = 0
        else:
            max_corr_with_selected = max(corr_values)

        if max_corr_with_selected < max_corr:
            selected.append(candidate)

    return selected


def main():
    print("=" * 70)
    print("  ETF Portfolio Selection")
    print("=" * 70)

    # 1. Load evaluation and pre-filter
    eval_df = load_evaluation()

    # 2. Load returns
    names_set = set(eval_df['name'])
    returns_dict = load_returns(names_set)

    # 3. Build correlation matrix
    corr_matrix = build_correlation_matrix(returns_dict)

    # 4. Greedy selection
    selected = greedy_select(eval_df, corr_matrix, MAX_CORRELATION, TARGET_MAX)
    print(f"\nSelected {len(selected)} ETFs (max_corr={MAX_CORRELATION})")

    # If too few, try relaxing the threshold
    if len(selected) < TARGET_MIN:
        relaxed_corr = 0.75
        print(f"\nToo few ETFs ({len(selected)}), relaxing correlation to {relaxed_corr}...")
        selected = greedy_select(eval_df, corr_matrix, relaxed_corr, TARGET_MAX)
        print(f"Selected {len(selected)} ETFs with relaxed threshold")

    # 5. Print results
    print("\n" + "=" * 70)
    print("  SELECTED PORTFOLIO ETFs")
    print("=" * 70)

    # Merge with evaluation data
    sel_df = eval_df[eval_df['name'].isin(selected)].copy()
    sel_df['rank'] = sel_df['name'].map({n: i+1 for i, n in enumerate(selected)})
    sel_df = sel_df.sort_values('rank')

    # Calculate avg correlation with other selected ETFs
    avg_corrs = []
    for name in sel_df['name']:
        corrs_with_others = [
            abs(corr_matrix.loc[name, other])
            for other in selected
            if other != name and not pd.isna(corr_matrix.loc[name, other])
        ]
        avg_corrs.append(np.mean(corrs_with_others) if corrs_with_others else 0)
    sel_df['AvgCorrWithSelected'] = avg_corrs

    # Print table
    print(f"\n{'#':<3} {'Name':<40} {'AdjSharp':>9} {'1yRet':>10} {'AnnRet':>10} {'Vol':>10} {'MaxDD':>10} {'AvgCorr':>8}")
    print("-" * 100)
    for _, row in sel_df.iterrows():
        print(f"{int(row['rank']):<3} {row['name']:<40} {row['AdjustedSharp']:>9} {row['1yReturn']:>10} "
              f"{row['AnnualizedReturn']:>10} {row['Volatility']:>10} {row['MaxDrawdown']:>10} {row['AvgCorrWithSelected']:>8.3f}")

    # 6. Save sub-correlation matrix for selected ETFs
    sel_corr = corr_matrix.loc[selected, selected]
    sel_corr.to_csv(OUTPUT_CORR)
    print(f"\nCorrelation matrix of selected ETFs saved to: {OUTPUT_CORR}")

    # 7. Print pairwise correlation summary
    print("\n" + "=" * 70)
    print("  PAIRWISE CORRELATION AMONG SELECTED ETFs (|corr| > 0.5)")
    print("=" * 70)
    for i in range(len(selected)):
        for j in range(i + 1, len(selected)):
            c = corr_matrix.loc[selected[i], selected[j]]
            if abs(c) > 0.5:
                print(f"  {selected[i]:<35} <-> {selected[j]:<35} corr={c:.4f}")

    # 8. Category diversity summary
    print("\n" + "=" * 70)
    print("  SECTOR / CATEGORY BREAKDOWN")
    print("=" * 70)
    for name in selected:
        print(f"  - {name}")


if __name__ == "__main__":
    main()
