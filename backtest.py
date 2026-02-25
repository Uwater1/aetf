#!/usr/bin/env python3
"""
Portfolio Backtest with Alpha Model

Alpha Model:
  - Primary signal: Z-score mean-reversion across multiple MA timeframes
    → Blended Z-score from 50/120/200-day MAs (positive = undervalued)
  - Volatility scaling: Inverse-vol weighting equalizes risk contribution
  - Adaptive momentum guard:
    → Per-ETF threshold = k × rolling σ (self-calibrating to each ETF's vol)
    → Strong rally: don't reduce below equal weight
    → Strong crash: don't increase above minimum weight

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
MA_WINDOWS = [40, 80, 120]         # Multi-timeframe moving average windows
MA_BLEND_WEIGHTS = [0.3, 0.4, 0.3]  # Blend weights for each MA timeframe
MOMENTUM_WINDOW = 20                # Short-term momentum lookback (trading days)
MOMENTUM_K = 1.3                    # Momentum threshold = k × rolling_std
MIN_WEIGHT = 0.03                   # 3% minimum weight per ETF
VOL_LOOKBACK = 60                   # Rolling window for volatility scaling
SIGNAL_STRENGTH = 0.4               # Blend: 0=equal weight, 1=full alpha model
REBALANCE_MONTHS = [2, 5, 8, 11]    # Feb, May, Aug, Nov

# Alt weights: proportional to AdjustedSharpe from etf_evaluation.csv, normalized to sum=1.
# Higher Sharpe → larger allocation. Range: ~7.5% (lowest) to ~12.3% (highest).
_ADJ_SHARPE = {
    '矿业ETF_561330':          1.2548,
    '浙商之江凤凰ETF_512190':  1.1718,
    '工程机械ETF_560280':      1.1620,
    '电信ETF易方达_563010':    1.1351,
    '半导体设备ETF_561980':    1.0942,
    '中证2000ETF华夏_562660':  1.0520,
    '石油ETF_561360':          0.8943,
    '银行ETF华夏_515020':      0.8776,
    '沪港深500ETF富国_517100': 0.8129,
    '中证500ETF国联_515550':   0.7624,
}
_total_sharpe = sum(_ADJ_SHARPE.values())
ALT_WEIGHTS = {name: v / _total_sharpe for name, v in _ADJ_SHARPE.items()}


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


def compute_alpha_weights(prices, rebalance_date, base_weights=None):
    """
    Compute portfolio weights using:
      1. Multi-timeframe Z-score value signal (blended 50/120/200-day MAs)
      2. Inverse-volatility scaling (risk parity adjustment)
      3. Adaptive momentum guard (per-ETF, k × rolling_std threshold)

    base_weights: dict of {etf_name: weight} to use as the blend anchor and
                  momentum guard reference. Defaults to equal weight when None.
    """
    idx = prices.index.get_loc(rebalance_date)
    etf_names = prices.columns.tolist()
    n = len(etf_names)

    # Use provided base weights or fall back to equal weight
    if base_weights is None:
        base_w = {name: 1.0 / n for name in etf_names}
    else:
        base_w = base_weights

    # --- Blended Z-score value signal across multiple MA timeframes ---
    value_scores = {}
    for name in etf_names:
        current = prices[name].iloc[idx]
        blended_z = 0.0
        for ma_win, blend_w in zip(MA_WINDOWS, MA_BLEND_WEIGHTS):
            history = prices[name].iloc[max(0, idx - ma_win):idx + 1]
            ma = history.mean()
            rolling_std = history.std()
            # Z-score: positive = price below MA (undervalued)
            z = (ma - current) / rolling_std if rolling_std > 0 else 0.0
            blended_z += blend_w * z
        value_scores[name] = blended_z

    # --- Momentum signal ---
    momentum = {}
    for name in etf_names:
        mom_start = max(0, idx - MOMENTUM_WINDOW)
        p_start = prices[name].iloc[mom_start]
        p_now = prices[name].iloc[idx]
        momentum[name] = (p_now / p_start - 1) if p_start > 0 else 0.0

    # --- Shift Z-scores so all are positive before weighting ---
    min_z = min(value_scores.values())
    shifted = {name: value_scores[name] - min_z + 0.1 for name in etf_names}

    # --- Apply inverse-volatility scaling ---
    inv_vol = {}
    for name in etf_names:
        vol_history = prices[name].iloc[max(0, idx - VOL_LOOKBACK):idx + 1]
        vol = vol_history.pct_change().std() * np.sqrt(252)
        inv_vol[name] = 1.0 / vol if vol > 0 else 1.0

    # Combine: alpha_score × inverse_vol
    combined = {name: shifted[name] * inv_vol[name] for name in etf_names}
    total_combined = sum(combined.values())
    alpha_weights = {name: combined[name] / total_combined for name in etf_names}

    # --- Blend alpha weights with base weights (controls conviction) ---
    raw_weights = {
        name: SIGNAL_STRENGTH * alpha_weights[name] + (1 - SIGNAL_STRENGTH) * base_w[name]
        for name in etf_names
    }

    # --- Adaptive momentum guard (per-ETF, k × σ threshold) ---
    adjusted = {}
    for name in etf_names:
        w = raw_weights[name]
        mom = momentum[name]

        # Compute per-ETF adaptive threshold from rolling return volatility
        ret_history = prices[name].pct_change().iloc[max(0, idx - VOL_LOOKBACK):idx + 1]
        ret_std = ret_history.std() * np.sqrt(MOMENTUM_WINDOW)
        up_thresh = MOMENTUM_K * ret_std
        dn_thresh = -MOMENTUM_K * ret_std

        if mom > up_thresh:
            # Strong rally (relative to this ETF's vol): keep riding, at least base weight
            w = max(w, base_w[name])
        elif mom < dn_thresh:
            # Strong crash (relative to this ETF's vol): avoid catching knife
            w = min(w, MIN_WEIGHT)

        adjusted[name] = w

    # --- Enforce minimum weight and re-normalize ---
    for name in etf_names:
        adjusted[name] = max(adjusted[name], MIN_WEIGHT)
    total = sum(adjusted.values())
    weights = {name: adjusted[name] / total for name in etf_names}

    return weights, value_scores, momentum


def run_backtest(prices, rf_daily, rebalance_dates, override_weights=None, base_weights=None):
    """
    Run the backtest:
    - At each rebalance date, compute alpha weights (or use override_weights)
    - Between rebalances, drift with market returns
    - Track portfolio NAV daily

    override_weights: if set, skip alpha model and use this fixed weight dict every rebalance.
    base_weights: if set (and override_weights is None), use as base for alpha model blending.

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
        current_weights, _, _ = compute_alpha_weights(prices, rebalance_dates[0], base_weights)

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
                current_weights, _, _ = compute_alpha_weights(prices, date, base_weights)
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


def print_results(equalw_nav, alpha_nav, altw_nav, altw_alpha_nav, bench_nav,
                  alpha_wh, altw_alpha_wh, rf_daily):
    """Print 4-strategy performance comparison and weight history."""
    eq_m  = compute_metrics(equalw_nav,     rf_daily)
    al_m  = compute_metrics(alpha_nav,      rf_daily)
    aw_m  = compute_metrics(altw_nav,       rf_daily)
    aa_m  = compute_metrics(altw_alpha_nav, rf_daily)
    bn_m  = compute_metrics(bench_nav,      rf_daily)

    COL = 13
    print("\n" + "=" * 80)
    print("  PERFORMANCE COMPARISON  (4 strategies + CSI300 benchmark)")
    print("=" * 80)
    print(f"\n{'Metric':<20} {'EqualW':>{COL}} {'EqualW+Alpha':>{COL}} {'AltW':>{COL}} {'AltW+Alpha':>{COL}} {'CSI300':>{COL}}")
    print("-" * 80)
    for key in eq_m:
        print(f"{key:<20} {eq_m[key]:>{COL}} {al_m[key]:>{COL}} {aw_m[key]:>{COL}} {aa_m[key]:>{COL}} {bn_m[key]:>{COL}}")

    # Compact weight history for alpha strategies
    etf_short = {n: n.split('_')[0][:6] for n in PORTFOLIO_ETFS}
    for label, wh in [('EqualW+Alpha', alpha_wh), ('AltW+Alpha', altw_alpha_wh)]:
        print(f"\n{'=' * 80}")
        print(f"  WEIGHT ALLOCATION — {label}")
        print("=" * 80)
        for entry in wh:
            date = entry['date']
            weights = entry['weights']
            sorted_w = sorted(weights.items(), key=lambda x: x[1], reverse=True)
            top3 = ', '.join(f'{etf_short[n]}={w:.0%}' for n, w in sorted_w[:3])
            bot3 = ', '.join(f'{etf_short[n]}={w:.0%}' for n, w in sorted_w[-3:])
            spread = sorted_w[0][1] - sorted_w[-1][1]
            print(f"  {date.date()} | Top: {top3} | Bot: {bot3} | Spread: {spread:.1%}")

    # Save all 4 NAV series to CSV
    nav_compare = pd.DataFrame({
        'equalw_nav':      equalw_nav,
        'equalw_alpha_nav': alpha_nav,
        'altw_nav':        altw_nav,
        'altw_alpha_nav':  altw_alpha_nav,
        'benchmark_nav':   bench_nav,
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
    print("  Portfolio Backtest — 4 Strategies")

    # 1. Load data
    print("\n[1] Loading ETF data...")
    prices = load_all_data(PORTFOLIO_ETFS)
    rf_daily = load_risk_free_rate()
    print(f"    Price data: {prices.index[0].date()} → {prices.index[-1].date()}, {len(prices)} days")
    print(f"    ETFs: {len(prices.columns)}")

    # 2. Find rebalance dates
    rebalance_dates = get_rebalance_dates(prices.index, REBALANCE_MONTHS)

    # 3. Strategy 1: Equal weight (static, no alpha rebalance)
    equal_weights = {name: 1.0 / len(PORTFOLIO_ETFS) for name in PORTFOLIO_ETFS}
    equalw_nav, _ = run_backtest(prices, rf_daily, rebalance_dates,
                                 override_weights=equal_weights)

    # 4. Strategy 2: Equal weight + alpha rebalance
    alpha_nav, alpha_wh = run_backtest(prices, rf_daily, rebalance_dates)

    # 5. Strategy 3: Alt weight (static AdjustedSharpe-proportional, no alpha rebalance)
    altw_nav, _ = run_backtest(prices, rf_daily, rebalance_dates,
                               override_weights=ALT_WEIGHTS)

    # 6. Strategy 4: Alt weight + alpha rebalance
    altw_alpha_nav, altw_alpha_wh = run_backtest(prices, rf_daily, rebalance_dates,
                                                  base_weights=ALT_WEIGHTS)

    # 7. Load CSI300 benchmark
    bench_nav = load_benchmark(equalw_nav.index)

    # 8. Print results
    print_results(equalw_nav, alpha_nav, altw_nav, altw_alpha_nav, bench_nav,
                  alpha_wh, altw_alpha_wh, rf_daily)


if __name__ == "__main__":
    main()

