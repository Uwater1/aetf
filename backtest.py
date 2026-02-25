#!/usr/bin/env python3
"""
Portfolio Backtest with Alpha Model

Alpha Model:
  - Primary signal: Mean-reversion / Value
    → ETFs trading below their long-term MA are "undervalued" → higher weight
    → ETFs trading above their long-term MA are "overvalued" → lower weight
  - Momentum guard:
    → If ETF is shooting up (strong positive momentum), don't sell/reduce
    → If ETF is falling quickly (strong negative momentum), don't buy/increase

Rebalance: Quarterly (first trading day of Feb, May, Aug, Nov)
Benchmark: Equal-weight portfolio (10% each)
"""

import os
import pandas as pd
import numpy as np

# ─── Configuration ───────────────────────────────────────────────────────────
BASE_DIR = '/home/hallo/Documents/aetf'
SELECTED_DIR = os.path.join(BASE_DIR, 'selected2')
RF_FILE = os.path.join(BASE_DIR, 'riskFreeRate.csv')
BENCHMARK_ETF = '沪深300ETF广发_510360'

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

# Alpha model parameters
MA_WINDOW = 120           # Long-term moving average window (trading days)
MOMENTUM_WINDOW = 20      # Short-term momentum lookback (trading days)
MOMENTUM_UP_THRESH = 0.08 # 8% in 20 days = strong rally, don't sell
MOMENTUM_DN_THRESH = -0.08 # -8% in 20 days = strong crash, don't buy
MIN_WEIGHT = 0.03         # 3% minimum weight per ETF
REBALANCE_MONTHS = [2, 5, 8, 11]  # Feb, May, Aug, Nov


def load_all_data(etf_names):
    """Load adj_close for all ETFs into a single DataFrame, aligned by date."""
    series = {}
    for name in etf_names:
        filepath = os.path.join(SELECTED_DIR, f'{name}.csv')
        df = pd.read_csv(filepath)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').set_index('date')
        series[name] = df['adj_close']
    prices = pd.DataFrame(series).dropna()  # only dates where ALL ETFs have data
    return prices


def load_risk_free_rate():
    """Load daily risk-free rate as annualized decimal (e.g., 0.02 = 2%)."""
    rf_df = pd.read_csv(RF_FILE)
    rf_df['date'] = pd.to_datetime(rf_df['time'])
    rf_df = rf_df.sort_values('date').set_index('date')
    # 'close' is annual rate in percent, convert to daily decimal
    rf_daily = rf_df['close'] / (100.0 * 252.0)
    return rf_daily


def get_rebalance_dates(dates, months):
    """Find the first trading day of each rebalance month within the date index."""
    rebalance_dates = []
    for date in dates:
        if date.month in months and date.day <= 10:
            # Check if this is the first trading day we see for this year-month
            ym = (date.year, date.month)
            if not rebalance_dates or (rebalance_dates[-1].year, rebalance_dates[-1].month) != ym:
                rebalance_dates.append(date)
    return rebalance_dates


def compute_alpha_weights(prices, rebalance_date):
    """
    Compute portfolio weights using value-based alpha + momentum guard.
    
    Value signal: MA_WINDOW-day MA / current price  (higher = more undervalued)
    Momentum guard:
      - If 20-day return > +8%, don't reduce weight (keep/boost)
      - If 20-day return < -8%, don't increase weight (keep/reduce)
    """
    idx = prices.index.get_loc(rebalance_date)
    etf_names = prices.columns.tolist()
    n = len(etf_names)
    equal_w = 1.0 / n

    # --- Value signal: how far below the MA ---
    value_scores = {}
    for name in etf_names:
        history = prices[name].iloc[max(0, idx - MA_WINDOW):idx + 1]
        ma = history.mean()
        current = prices[name].iloc[idx]
        # ratio > 1 means price is below MA (undervalued)
        value_scores[name] = ma / current if current > 0 else 1.0

    # --- Momentum signal ---
    momentum = {}
    for name in etf_names:
        mom_start = max(0, idx - MOMENTUM_WINDOW)
        p_start = prices[name].iloc[mom_start]
        p_now = prices[name].iloc[idx]
        momentum[name] = (p_now / p_start - 1) if p_start > 0 else 0.0

    # --- Raw weights from value signal (normalize) ---
    total_val = sum(value_scores.values())
    raw_weights = {name: value_scores[name] / total_val for name in etf_names}

    # --- Apply momentum guard ---
    adjusted = {}
    for name in etf_names:
        w = raw_weights[name]
        mom = momentum[name]

        if mom > MOMENTUM_UP_THRESH:
            # Strong rally: don't reduce below equal weight (keep riding)
            w = max(w, equal_w)
        elif mom < MOMENTUM_DN_THRESH:
            # Strong crash: don't increase above minimum (avoid catching knife)
            w = min(w, MIN_WEIGHT)

        adjusted[name] = w

    # --- Enforce minimum weight and re-normalize ---
    for name in etf_names:
        adjusted[name] = max(adjusted[name], MIN_WEIGHT)
    total = sum(adjusted.values())
    weights = {name: adjusted[name] / total for name in etf_names}

    return weights, value_scores, momentum


def run_backtest(prices, rf_daily, rebalance_dates, override_weights=None):
    """
    Run the backtest:
    - At each rebalance date, compute alpha weights (or use override_weights)
    - Between rebalances, drift with market returns
    - Track portfolio NAV daily
    
    Returns: nav Series, weight_history list
    """
    etf_names = prices.columns.tolist()
    daily_returns = prices.pct_change().fillna(0)

    # Start from the first rebalance date
    start_idx = prices.index.get_loc(rebalance_dates[0])
    nav = 1.0
    nav_history = []
    weight_history = []

    # Current weights
    if override_weights:
        current_weights = override_weights.copy()
    else:
        current_weights, _, _ = compute_alpha_weights(prices, rebalance_dates[0])

    weight_history.append({'date': rebalance_dates[0], 'weights': current_weights.copy()})

    # Holdings: NAV allocated to each ETF
    holdings = {name: nav * current_weights[name] for name in etf_names}

    for i in range(start_idx, len(prices)):
        date = prices.index[i]

        # Check if rebalance day (skip the first one, already initialized)
        if date in rebalance_dates and date != rebalance_dates[0]:
            nav = sum(holdings.values())
            if override_weights:
                current_weights = override_weights.copy()
            else:
                current_weights, _, _ = compute_alpha_weights(prices, date)
            holdings = {name: nav * current_weights[name] for name in etf_names}
            weight_history.append({'date': date, 'weights': current_weights.copy()})

        # Apply daily returns to holdings
        if i > start_idx:  # skip first day (entry day)
            for name in etf_names:
                ret = daily_returns[name].iloc[i]
                holdings[name] *= (1 + ret)

        nav = sum(holdings.values())
        nav_history.append({'date': date, 'nav': nav})

    nav_df = pd.DataFrame(nav_history).set_index('date')
    return nav_df['nav'], weight_history


def compute_metrics(nav_series, rf_daily):
    """Compute performance metrics: total return, CAGR, Sharpe, Sortino, MaxDD, Calmar."""
    total_ret = nav_series.iloc[-1] / nav_series.iloc[0] - 1
    n_days = len(nav_series)
    cagr = (nav_series.iloc[-1] / nav_series.iloc[0]) ** (252 / n_days) - 1

    daily_ret = nav_series.pct_change().dropna()

    # Align risk-free rate
    rf_aligned = rf_daily.reindex(daily_ret.index).ffill().bfill().fillna(0)
    excess = daily_ret - rf_aligned
    sharpe = excess.mean() / excess.std() * np.sqrt(252) if excess.std() > 0 else 0

    # Sortino (downside deviation only)
    downside = excess[excess < 0]
    downside_std = downside.std()
    sortino = excess.mean() / downside_std * np.sqrt(252) if downside_std > 0 else 0

    # Max drawdown
    cummax = nav_series.cummax()
    drawdown = (nav_series - cummax) / cummax
    max_dd = drawdown.min()

    calmar = cagr / abs(max_dd) if max_dd != 0 else 0

    # Volatility
    ann_vol = daily_ret.std() * np.sqrt(252)

    return {
        'Total Return': f'{total_ret:.2%}',
        'CAGR': f'{cagr:.2%}',
        'Sharpe': f'{sharpe:.3f}',
        'Sortino': f'{sortino:.3f}',
        'Volatility': f'{ann_vol:.2%}',
        'Max Drawdown': f'{max_dd:.2%}',
        'Calmar': f'{calmar:.3f}',
        'Trading Days': n_days,
    }


def print_results(alpha_nav, equal_nav, bench_nav, weight_history, rf_daily):
    """Print performance comparison and weight history."""
    alpha_m = compute_metrics(alpha_nav, rf_daily)
    equal_m = compute_metrics(equal_nav, rf_daily)
    bench_m = compute_metrics(bench_nav, rf_daily)

    print("\n" + "=" * 70)
    print("  PERFORMANCE COMPARISON")
    print("=" * 70)
    print(f"\n{'Metric':<20} {'Alpha Model':>15} {'Equal Weight':>15} {'CSI300 BM':>15}")
    print("-" * 65)
    for key in alpha_m:
        print(f"{key:<20} {alpha_m[key]:>15} {equal_m[key]:>15} {bench_m[key]:>15}")

    # Compact weight history: one line per rebalance, show top 3 and bottom 3
    print("\n" + "=" * 70)
    print("  WEIGHT ALLOCATION AT EACH REBALANCE")
    print("=" * 70)
    etf_short = {n: n.split('_')[0][:6] for n in PORTFOLIO_ETFS}
    for entry in weight_history:
        date = entry['date']
        weights = entry['weights']
        sorted_w = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        top3 = ', '.join(f'{etf_short[n]}={w:.0%}' for n, w in sorted_w[:3])
        bot3 = ', '.join(f'{etf_short[n]}={w:.0%}' for n, w in sorted_w[-3:])
        spread = sorted_w[0][1] - sorted_w[-1][1]
        print(f"  {date.date()} | Top: {top3} | Bot: {bot3} | Spread: {spread:.1%}")

    # Save NAV comparison to CSV
    nav_compare = pd.DataFrame({
        'alpha_nav': alpha_nav,
        'equal_nav': equal_nav,
        'benchmark_nav': bench_nav,
    })
    output_path = os.path.join(BASE_DIR, 'backtest_results.csv')
    nav_compare.to_csv(output_path)
    print(f"\nDaily NAV saved to: {output_path}")


def load_benchmark(dates):
    """Load benchmark ETF (沪深300) and normalize to NAV=1.0 at start."""
    filepath = os.path.join(SELECTED_DIR, f'{BENCHMARK_ETF}.csv')
    df = pd.read_csv(filepath)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').set_index('date')
    bench = df['adj_close'].reindex(dates).ffill()
    bench_nav = bench / bench.iloc[0]  # normalize to 1.0
    return bench_nav


def main():
    print("  Portfolio Backtest — Value Alpha + Momentum Guard")

    # 1. Load data
    print("\n[1] Loading ETF data...")
    prices = load_all_data(PORTFOLIO_ETFS)
    rf_daily = load_risk_free_rate()
    print(f"    Price data: {prices.index[0].date()} → {prices.index[-1].date()}, {len(prices)} days")
    print(f"    ETFs: {len(prices.columns)}")

    # 2. Find rebalance dates
    rebalance_dates = get_rebalance_dates(prices.index, REBALANCE_MONTHS)
#    print(f"\n[2] Rebalance dates ({len(rebalance_dates)}):")
#    for d in rebalance_dates:
#        print(f"    {d.date()}")

    # 3. Run alpha backtest
#    print("\n[3] Running alpha model backtest...")
    alpha_nav, weight_history = run_backtest(prices, rf_daily, rebalance_dates)

    # 4. Run equal-weight benchmark
#    print("\n[4] Running equal-weight benchmark...")
    equal_weights = {name: 1.0 / len(PORTFOLIO_ETFS) for name in PORTFOLIO_ETFS}
    equal_nav, _ = run_backtest(prices, rf_daily, rebalance_dates, 
                                override_weights=equal_weights)

    # 5. Load CSI300 benchmark
#    print("\n[5] Loading CSI300 benchmark (沪深300ETF易方达)...")
    bench_nav = load_benchmark(alpha_nav.index)

    # 6. Print results
    print_results(alpha_nav, equal_nav, bench_nav, weight_history, rf_daily)


if __name__ == "__main__":
    main()
