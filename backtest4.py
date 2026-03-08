#!/usr/bin/env python3
"""
Portfolio Backtest with Dynamic Regime-Switching Alpha Model

Alpha Model:
  - Convex Soft Rank Momentum: all ETFs tilted by power-law ranking multiplier
    → mult = 1 + α·scale·sign(norm)·|norm|^RANK_POWER  where norm ∈ [−1,+1]
    → RANK_POWER < 1 concentrates signal at extremes (convex curve)
    → Normal: scale=1.0, Aggressive (3+ non-weak days): scale=1.5
  - Defensive tilt: 3 proven ETFs get priority when market is weak
    → Weak market: CSI300 < EMA60 AND Volume MA5 < Volume MA60
  - Dynamic rebalancing: trade only when max weight deviation > threshold

Benchmark: Equal-weight portfolio (10% each)
"""

import os
import warnings
import pandas as pd
import numpy as np
import pandas_ta as ta
from numba import njit

warnings.filterwarnings('ignore', category=RuntimeWarning, message='invalid value encountered')
warnings.filterwarnings('ignore', category=FutureWarning, message='Downcasting object dtype')


def safe_pct_change(df):
    """Compute pct_change that is safe for pre-launch ETFs.

    When prices are forward-filled and then NaN-filled with 0, the first real
    price produces an inf return (0 → positive).  This helper replaces any
    inf / -inf values with 0 so downstream EWMA and Sharpe calculations stay
    finite.
    """
    ret = df.pct_change()
    ret = ret.replace([np.inf, -np.inf], np.nan).fillna(0)
    return ret


# ─── Configuration ───────────────────────────────────────────────────────────
BASE_DIR = '.'
SELECTED_DIR = os.path.join(BASE_DIR, 'selected3')
BENCHMARK_ETF = '沪深300'
VOLUME_FILE = os.path.join(BASE_DIR, 'volume.csv')
ANNUAL_RF = 0.0 # Use the old Sharpe ratio
RF_DAILY = ANNUAL_RF / 252.0
SHARPE_SPAN = 60                     # Lookback span for dynamic Sharpe weights (EWMA)
SHARPE_MIN_PERIODS = 20              # Warm-up days before EWMA Sharpe is considered stable

PORTFOLIO_ETFS = [ # A combination of mutiple ETF, to maximize liquidity
    '中证500',
    '银行',
    '有色矿业',
    '浙商凤凰',
    '沪港深500',
    '电信',
    '芯片',
    '工程机械',
    '中证2000',
    '石油',
]

# Defensive ETFs: proven resilient in downturns
DEFENSIVE_ETFS = ['银行', '浙商凤凰', '石油']
ALPHA_STRENGTH = 0.5                 # Multiplier offset for Surge/Cut/Defensive

# Alpha model parameters (V2)
EMA60_WINDOW = 60                    # Absolute trend filter moving average
MOMENTUM_WINDOW = 20                 # Short-term momentum lookback (trading days)
MIN_WEIGHT = 0.03                    # 3% minimum weight per ETF
STAMP_DUTY = 0.001                   # 0.1% stamp duty on sold value at each rebalance
REBALANCE_THRESHOLD = 0.10           # Rebalance when max weight deviation > 10%
MIN_HOLD_DAYS = 5                    # Minimum days between rebalances (cooldown)
RANK_POWER = 0.4                     # Convex soft ranking power: <1 concentrates at extremes, 1.0=linear
EXTREME_BOOST = 3                    # Extra multiplier for defensive ETFs in weak markets, notice its x1.5
CASH_YIELD = 0.02                    # Annualized risk-free return for cash holdings



def load_all_data(etf_names, warmup_days=60):
    """Load adj_close for all ETFs.

    Returns:
      prices_full : DataFrame indexed by date, NaN where an ETF has not launched yet.
                    Starts `warmup_days` trading days before the first date all ETFs are available.
      trade_start : first date when all ETFs have valid prices (the actual backtest start).
    """
    series = {}
    for name in etf_names:
        filepath = os.path.join(SELECTED_DIR, f'{name}.csv')
        df = pd.read_csv(filepath)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').set_index('date')
        series[name] = df['adj_close']

    # Union of all dates (each ETF keeps its own history; NaN where not yet launched)
    prices_union = pd.DataFrame(series)

    # First date ALL ETFs have data
    trade_start = prices_union.dropna().index[0]

    # Go back `warmup_days` rows before that date
    all_dates = prices_union.index[prices_union.index <= trade_start]
    warmup_start = all_dates[-min(warmup_days + 1, len(all_dates))]
    prices_full = prices_union.loc[warmup_start:]

    return prices_full, trade_start


def precompute_trailing_sharpe_weights(prices, bench_prices, min_periods=SHARPE_MIN_PERIODS, span=SHARPE_SPAN):
    """
    Compute dynamic base weights using an EWMA trailing Sharpe ratio approach.
    Shifted by 1 day so weights for day t only use data up to day t-1 to prevent lookahead bias.

    During the warm-up period (first min_periods days), NaN Sharpe values are pre-filled
    using each ETF's historical Sharpe differential vs. the peer+benchmark average.
    This involves a small, bounded lookahead that only affects the first ~20 days.
    """
    daily_returns = safe_pct_change(prices)
    excess_returns = daily_returns - RF_DAILY

    # ── Step 1: Full-period Sharpe per ETF (used only for pre-fill differential) ──
    full_sharpe = (excess_returns.mean() / excess_returns.std() * np.sqrt(252)).clip(lower=0)

    # ── Step 2: Benchmark full-period Sharpe ──
    bench_aligned = bench_prices.reindex(prices.index).ffill()
    bench_ret = bench_aligned.pct_change().fillna(0) - RF_DAILY
    bench_sharpe = float(np.clip(bench_ret.mean() / bench_ret.std() * np.sqrt(252), 0, None))

    # ── Step 3: Per-ETF relative differential vs. (peer_avg + benchmark) / 2 ──
    n = len(prices.columns)
    sharpe_diff = {}
    for etf in prices.columns:
        peer_avg = full_sharpe.drop(index=etf).mean()
        combined_avg = (peer_avg + bench_sharpe) / 2.0
        if combined_avg > 0:
            diff = (float(full_sharpe[etf]) - combined_avg) / combined_avg
        else:
            diff = 0.0
        sharpe_diff[etf] = float(np.clip(diff, -0.5, 0.5))

    # ── Step 4: EWMA Sharpe (with NaN during warm-up) ──
    ewma_mean = excess_returns.ewm(span=span, min_periods=min_periods).mean() * 252
    ewma_vol  = excess_returns.ewm(span=span, min_periods=min_periods).std()  * np.sqrt(252)
    ewma_sharpe = ewma_mean / ewma_vol   # NaN where < min_periods data

    # ── Step 5: Pre-fill NaN cells using daily group mean × (1 + diff_i) ──
    # For each day that has at least one non-NaN ETF, compute the daily mean
    # of those ETFs and use each ETF's differential to fill its NaN.
    # When ALL ETFs are NaN (early warm-up before any ETF reaches min_periods),
    # daily_group_mean is also NaN.  Fall back to full_sharpe.mean() so the
    # initial weights reflect relative historical performance instead of
    # defaulting to blind equal weight.
    daily_group_mean = ewma_sharpe.mean(axis=1)   # mean of non-NaN columns per row
    full_sharpe_mean = float(full_sharpe.mean())   # fallback for all-NaN rows
    for etf in prices.columns:
        nan_mask = ewma_sharpe[etf].isna()
        if nan_mask.any():
            group_mean_filled = daily_group_mean[nan_mask].fillna(full_sharpe_mean)
            prefill = group_mean_filled * (1.0 + sharpe_diff[etf])
            ewma_sharpe.loc[nan_mask, etf] = prefill.clip(lower=0)

    # ── Step 6: Clip negatives, normalize to weights ──
    ewma_sharpe = ewma_sharpe.fillna(0).clip(lower=0)
    sum_sharpes = ewma_sharpe.sum(axis=1)
    equal_weight = 1.0 / n
    weights = ewma_sharpe.div(sum_sharpes, axis=0).fillna(equal_weight)

    # Shift by 1: allocation for day t uses only data up to day t-1
    shifted_weights = weights.shift(1).fillna(equal_weight)
    return shifted_weights

# Trailing Shape Weights will be precomputed at runtime in main()




def load_market_data():
    """Load CSI300 prices + volume data, precompute regime indicators via pandas_ta.

    Returns a DataFrame indexed by date with columns:
      - csi300_close: CSI300 adj_close price
      - csi300_ema60: EMA(60) of CSI300 close
      - vol_ma5: 5-day SMA of market volume
      - vol_ma60: 60-day SMA of market volume
      - weak_market: bool, True when CSI300 < EMA60 AND vol_ma5 < vol_ma60
    """
    # CSI300 prices
    bench_path = os.path.join(SELECTED_DIR, f'{BENCHMARK_ETF}.csv')
    bench_df = pd.read_csv(bench_path)
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    bench_df = bench_df.sort_values('date').set_index('date')

    csi300 = bench_df[['adj_close']].rename(columns={'adj_close': 'csi300_close'})
    csi300['csi300_ema60'] = ta.ema(csi300['csi300_close'], length=60)

    # Volume data
    vol_df = pd.read_csv(VOLUME_FILE)
    vol_df['date'] = pd.to_datetime(vol_df['date'])
    vol_df = vol_df.sort_values('date').set_index('date')

    vol_df['vol_ma5'] = ta.sma(vol_df['volume_k'], length=5)
    vol_df['vol_ma60'] = ta.sma(vol_df['volume_k'], length=60)

    # Merge on date
    market = csi300.join(vol_df[['vol_ma5', 'vol_ma60']], how='left')
    market['vol_ma5'] = market['vol_ma5'].ffill()
    market['vol_ma60'] = market['vol_ma60'].ffill()

    # Weak market: just use price trend
    market['weak_market'] = (
        market['csi300_close'] < market['csi300_ema60']
    )
    # Extreme weak market
    market['extreme_weak_market'] = (
        market['csi300_close'] < market['csi300_ema60'] * 0.95
    )
    return market


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


def precompute_indicators(prices):
    """Precompute per-ETF EMA60 for the absolute trend filter.

    Returns:
      - indicators_arr: float64 array of shape (n_etfs, n_days)
        Each cell is the 60-day EMA for that ETF on that day (0 if not yet available).
    """
    n_days = len(prices)
    n_etfs = len(prices.columns)
    indicators_arr = np.zeros((n_etfs, n_days))

    for i, name in enumerate(prices.columns):
        s = prices[name]
        indicators_arr[i, :] = ta.ema(s, length=EMA60_WINDOW).fillna(0).values

    return indicators_arr


@njit
def jit_backtest_core(
    prices_arr, daily_returns_arr, weak_market_arr, extreme_weak_market_arr, ma60_arr,
    defensive_mask, n_days, n_etfs, min_weight, rebalance_threshold, min_hold_days,
    stamp_duty, momentum_window, alpha_strength, rank_power, extreme_boost,
    base_weights_arr, override_weights_arr=None, use_regime=True, trade_start_idx=0
):
    """
    V2 Backtest Core Loop (Numba @njit):
      - Convex Soft Rank Momentum: power-law tilt across all ETFs by rank
        → norm = 2*rank/(N-1) - 1  ∈ [-1, +1]
        → convex = sign(norm) * |norm|^rank_power   (rank_power<1 → extreme-focused)
        → multiplier[k] = 1 + alpha * scale * convex
        → scale=1.0 (normal), scale=1.5 (aggressive: 3+ consecutive non-weak days)
      - Trend Filter: if price < MA60, penalize by (1-alpha)
      - Weak Market: disable momentum tilt, enable Defensive tilt (1+alpha) on 3 defensive ETFs
    """
    nav_history = np.zeros(n_days)
    weight_history_vals = np.zeros((n_days, n_etfs))
    cash_history = np.zeros(n_days)
    rebalance_flags = np.zeros(n_days, dtype=np.bool_)

    nav = 1.0
    nav_history[0] = nav
    cash_holding = 0.0

    # ── helper inline: compute V2 target weights at row t ──────────────────
    def compute_v2_weights(t, is_weak, is_aggressive):
        weights = base_weights_arr[t].copy()

        # 1. Relative momentum: 20-day returns, ranked cross-sectionally
        mom_start = max(0, t - momentum_window)
        mom_ret = np.zeros(n_etfs)
        for i in range(n_etfs):
            p0 = prices_arr[mom_start, i]
            mom_ret[i] = (prices_arr[t, i] / p0 - 1.0) if p0 > 0 else 0.0

        # Argsort ascending => rank 0 = worst momentum, rank N-1 = best
        order = np.argsort(mom_ret)   # ascending

        if is_weak:
            # Weak market: disable momentum tilt; only defensive tilt active
            for i in range(n_etfs):
                if defensive_mask[i]:
                    weights[i] *= (1.0 + alpha_strength)
        else:
            # Convex soft ranking: power-law curve concentrates signal at extremes
            # norm = 2*rank/(N-1) - 1  ∈ [-1, +1]
            # convex = sign(norm) * |norm|^rank_power  (rank_power<1 → top/bottom heavier)
            # mult = 1 + alpha * scale * convex
            scale = 1.5 if is_aggressive else 1.0
            denom = float(n_etfs - 1)
            for rank_pos in range(n_etfs):
                etf_idx = order[rank_pos]
                normalized = 2.0 * rank_pos / denom - 1.0   # in [-1, +1]
                if normalized >= 0.0:
                    convex = normalized ** rank_power
                else:
                    convex = -((-normalized) ** rank_power)
                mult = 1.0 + alpha_strength * scale * convex
                weights[etf_idx] *= mult

        # 2. Absolute trend filter: price < EMA60 → penalize
        for i in range(n_etfs):
            ma60_val = ma60_arr[i, t]
            if ma60_val > 0 and prices_arr[t, i] < ma60_val:
                weights[i] *= (1.0 - alpha_strength)

        # 3. Normalize with MIN_WEIGHT floor
        floored = np.maximum(weights, min_weight)
        total = np.sum(floored)
        return floored / total

    # ── init day 0 ─────────────────────────────────────────────────────────
    # During the pre-period (t < trade_start_idx): hold NAV=1, skip trading.
    # Init weights to equal so holding array is valid before trading starts.
    eq_w = np.full(n_etfs, 1.0 / n_etfs)
    if override_weights_arr is not None:
        current_weights = override_weights_arr.copy()
    elif trade_start_idx == 0:
        current_weights = compute_v2_weights(0, bool(weak_market_arr[0]), False)
    else:
        current_weights = eq_w.copy()

    weight_history_vals[0] = current_weights
    holdings = nav * current_weights
    cash_holding = 0.0
    n_trades = 0
    days_since_rebalance = min_hold_days
    consecutive_non_weak = 0  # tracks streak of non-weak days for aggressive mode

    # ── main loop ──────────────────────────────────────────────────────────
    for t in range(1, n_days):
        # ── Pre-period: no trading, NAV held at 1.0 ─────────────────────
        if t < trade_start_idx:
            nav_history[t] = 1.0
            weight_history_vals[t] = eq_w
            cash_history[t] = 0.0
            continue

        # First day of trading: reset holdings to trade_start weights
        if t == trade_start_idx:
            nav = 1.0
            if override_weights_arr is not None:
                current_weights = override_weights_arr.copy()
            else:
                current_weights = compute_v2_weights(t, bool(weak_market_arr[t]), False)

            target_cash = 0.5 if use_regime and extreme_weak_market_arr[t] else 0.0
            current_weights = current_weights * (1.0 - target_cash)
            holdings = nav * current_weights
            cash_holding = nav * target_cash
            weight_history_vals[t] = current_weights
            cash_history[t] = target_cash
            nav_history[t] = nav
            days_since_rebalance = min_hold_days
            consecutive_non_weak = 0
            continue
        # Update holdings with daily returns
        for i in range(n_etfs):
            holdings[i] *= (1.0 + daily_returns_arr[t, i])
        cash_holding *= (1.0 + CASH_YIELD / 252.0)
        nav = np.sum(holdings) + cash_holding
        drifted_w = holdings / nav
        drifted_cash_w = cash_holding / nav

        # Track weak/non-weak streak
        if weak_market_arr[t]:
            consecutive_non_weak = 0
        else:
            consecutive_non_weak += 1

        is_aggressive = (consecutive_non_weak >= 3) and not bool(weak_market_arr[t])

        # Compute target weights
        target_cash = 0.5 if use_regime and extreme_weak_market_arr[t] else 0.0

        if override_weights_arr is not None:
            target_weights = override_weights_arr.copy()
        elif not use_regime:
            target_weights = base_weights_arr[t].copy()
            floored = np.maximum(target_weights, min_weight)
            target_weights = floored / np.sum(floored)
        else:
            target_weights = compute_v2_weights(t, bool(weak_market_arr[t]), is_aggressive)

            # Extreme defensive tilt in weak markets
            if bool(weak_market_arr[t]):
                for i in range(n_etfs):
                    if defensive_mask[i]:
                        target_weights[i] *= extreme_boost

                # Normalize again
                floored = np.maximum(target_weights, min_weight)
                target_weights = floored / np.sum(floored)

        # Apply cash holding reduction
        target_weights = target_weights * (1.0 - target_cash)

        # Check deviation and cooldown
        max_dev = 0.0
        for i in range(n_etfs):
            dev = abs(drifted_w[i] - target_weights[i])
            if dev > max_dev:
                max_dev = dev

        cash_dev = abs(drifted_cash_w - target_cash)
        if cash_dev > max_dev:
            max_dev = cash_dev

        if max_dev > rebalance_threshold and days_since_rebalance >= min_hold_days:
            # Stamp duty on sold portion
            stamp_cost = 0.0
            for i in range(n_etfs):
                new_val = nav * target_weights[i]
                if holdings[i] > new_val:
                    stamp_cost += stamp_duty * (holdings[i] - new_val)
            nav -= stamp_cost
            current_weights = target_weights
            holdings = nav * current_weights
            cash_holding = nav * target_cash
            weight_history_vals[t] = current_weights
            cash_history[t] = target_cash
            rebalance_flags[t] = True
            n_trades += 1
            days_since_rebalance = 0
        else:
            days_since_rebalance += 1
            cash_history[t] = drifted_cash_w

        nav_history[t] = nav

    return nav_history, weight_history_vals, cash_history, rebalance_flags, n_trades


def run_backtest(prices, market_data, ma60_arr, base_weights_df,
                 override_weights=None, use_regime=True, trade_start_idx=0):
    """
    Run the backtest with V2 regime logic, optimized by Numba @njit.
    base_weights_df: DataFrame of dynamic base weights of shape (n_days, n_etfs).
    override_weights: if set, skip regime model and use these fixed weights.
    use_regime: if False, no alpha momentum or trend filter is applied.
    trade_start_idx: row index into prices at which actual trading begins.
    """
    etf_names = prices.columns.tolist()
    prices_arr = prices.values.astype(np.float64)
    daily_returns_arr = safe_pct_change(prices).values.astype(np.float64)
    weak_market_arr = market_data['weak_market'].reindex(prices.index).fillna(False).values.astype(np.bool_)
    if 'extreme_weak_market' in market_data.columns:
        extreme_weak_market_arr = market_data['extreme_weak_market'].reindex(prices.index).fillna(False).values.astype(np.bool_)
    else:
        extreme_weak_market_arr = np.zeros(len(prices), dtype=np.bool_)

    defensive_mask = np.array([name in DEFENSIVE_ETFS for name in etf_names], dtype=np.bool_)

    bw_arr = base_weights_df[etf_names].values.astype(np.float64)

    ov_arr = None
    if override_weights is not None:
        ov_arr = np.array([override_weights.get(name, 0.0) for name in etf_names], dtype=np.float64)

    nav_hist, weight_hist_vals, cash_hist, rebalance_flags, n_trades = jit_backtest_core(
        prices_arr, daily_returns_arr, weak_market_arr, extreme_weak_market_arr, ma60_arr,
        defensive_mask, len(prices), len(etf_names), MIN_WEIGHT, REBALANCE_THRESHOLD,
        MIN_HOLD_DAYS, STAMP_DUTY, MOMENTUM_WINDOW, ALPHA_STRENGTH, RANK_POWER, EXTREME_BOOST,
        bw_arr, ov_arr, use_regime, trade_start_idx
    )

    # Trim nav_series to trade window so metrics reflect only live trading
    nav_series_full = pd.Series(nav_hist, index=prices.index)
    nav_series = nav_series_full.iloc[trade_start_idx:]

    weight_history = []
    for t in range(trade_start_idx, len(prices)):
        if t == trade_start_idx or rebalance_flags[t]:
            w_dict = dict(zip(etf_names, weight_hist_vals[t]))
            w_dict['Cash'] = cash_hist[t]
            weight_history.append({'date': prices.index[t], 'weights': w_dict})

    return nav_series, weight_history, n_trades








def compute_metrics(nav_series):
    """Compute performance metrics: total return, CAGR, Sharpe, Sortino, MaxDD, Calmar."""
    total_ret = nav_series.iloc[-1] / nav_series.iloc[0] - 1
    n_days = len(nav_series)
    cagr = (nav_series.iloc[-1] / nav_series.iloc[0]) ** (252 / n_days) - 1

    daily_ret = nav_series.pct_change().dropna()

    excess = daily_ret - RF_DAILY
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


def print_results(equalw_nav, regime_nav, altw_nav, altw_regime_nav, bench_nav,
                  regime_wh, altw_regime_wh, n_trades_eq, n_trades_alt, n_weak_days, n_total_days):
    """Print 4-strategy performance comparison and diagnostics."""
    eq_m = compute_metrics(equalw_nav)
    rg_m = compute_metrics(regime_nav)
    aw_m = compute_metrics(altw_nav)
    ar_m = compute_metrics(altw_regime_nav)
    bn_m = compute_metrics(bench_nav)

    COL = 12
    print("\n" + "=" * 85)
    print("  PERFORMANCE COMPARISON  (4 strategies + CSI300 benchmark)")
    print("=" * 85)
    print(f"\n{'Metric':<18} {'EqualW':>{COL}} {'Regime+Def':>{COL}} {'AltW':>{COL}} {'AltW+Reg':>{COL}} {'CSI300':>{COL}}")
    print("-" * 85)
    for key in eq_m:
        print(f"{key:<18} {eq_m[key]:>{COL}} {rg_m[key]:>{COL}} {aw_m[key]:>{COL}} {ar_m[key]:>{COL}} {bn_m[key]:>{COL}}")

    # Diagnostics
    print(f"\n  Rebalance trades fired : {n_trades_eq} (Eq Base) | {n_trades_alt} (Alt Base)")
    print(f"  Weak market days       : {n_weak_days}/{n_total_days} ({n_weak_days/n_total_days:.1%})")

    # Compact weight history
    etf_short = {n: n.split('_')[0][:6] for n in PORTFOLIO_ETFS}
    etf_short['Cash'] = 'Cash'
    print(f"\n{'=' * 85}")
    print("  WEIGHT ALLOCATION — AltW+Regime (last 10 rebalances shown)")
    print("=" * 85)
    for entry in altw_regime_wh[-10:]:
        date = entry['date']
        weights = entry['weights']
        sorted_w = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        top3 = ', '.join(f'{etf_short[n]}={w:.0%}' for n, w in sorted_w[:3])
        bot3 = ', '.join(f'{etf_short[n]}={w:.0%}' for n, w in sorted_w[-3:])
        spread = sorted_w[0][1] - sorted_w[-1][1]
        print(f"  {date.date()} | Top: {top3} | Bot: {bot3} | Spread: {spread:.1%}")

    # Save NAV series to CSV
    nav_compare = pd.DataFrame({
        'equalw_nav':  equalw_nav,
        'regime_nav':  regime_nav,
        'altw_nav': altw_nav,
        'altw_regime_nav': altw_regime_nav,
        'benchmark_nav': bench_nav,
    })
    output_path = os.path.join(BASE_DIR, 'backtest_results.csv')
    nav_compare.round(5).to_csv(output_path)
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
    print("  Portfolio Backtest — V2 Relative Momentum + Defensive Strategy")
    print(f"  Params: Mom={MOMENTUM_WINDOW}d EMA60={EMA60_WINDOW}d SharpeSpan={SHARPE_SPAN}d "
          f"MinW={MIN_WEIGHT} AlphaStr={ALPHA_STRENGTH} Thresh={REBALANCE_THRESHOLD}")
    print(f"  Convex Soft Rank: power={RANK_POWER} best={1+ALPHA_STRENGTH:.2f}x worst={1-ALPHA_STRENGTH:.2f}x "
          f"(aggressive scale=1.5x after 3 non-weak days)")
    print(f"  Defensive ETFs: {[e.split('_')[0] for e in DEFENSIVE_ETFS]} "
          f"(boost={1+ALPHA_STRENGTH:.2f}x in weak market)")

    # 1. Load ETF prices, market regime data
    print("\n[1] Loading data...")
    prices, trade_start = load_all_data(PORTFOLIO_ETFS, warmup_days=EMA60_WINDOW)
    trade_start_idx = prices.index.get_loc(trade_start)
    market_data = load_market_data()
    print(f"    ETFs        : {len(prices.columns)}")
    print(f"    Full window : {prices.index[0].date()} -> {prices.index[-1].date()} ({len(prices)} days)")
    print(f"    Trade start : {trade_start.date()} (idx={trade_start_idx}, warmup={trade_start_idx} days)")

    # 2. Precompute per-ETF EMA60 tables (pandas_ta, done once)
    print("[2] Precomputing indicators...")
    prices_ffilled = prices.ffill()              # keep NaN for not-yet-launched ETFs
    prices_filled = prices_ffilled.fillna(0)     # 0-filled only for arrays that need it
    ma60_arr = precompute_indicators(prices_filled)

    # Precompute Dynamic Sharpe Weights and Equal Weights DataFrame
    # NOTE: pass ffill-only prices so safe_pct_change sees NaN→NaN (not 0→price=inf)
    print("[Pre-3] Computing Trailing Sharpe Base Weights (with pre-fill)...")
    bench_path = os.path.join(SELECTED_DIR, f'{BENCHMARK_ETF}.csv')
    bench_df = pd.read_csv(bench_path)
    bench_df['date'] = pd.to_datetime(bench_df['date'])
    bench_df = bench_df.sort_values('date').set_index('date')
    bench_prices = bench_df['adj_close'].reindex(prices.index).ffill()
    alt_weights_df = precompute_trailing_sharpe_weights(prices_ffilled, bench_prices)
    eq_val = 1.0 / len(PORTFOLIO_ETFS)
    eq_weights_df = pd.DataFrame(eq_val, index=prices.index, columns=prices.columns)
    equal_weights = {name: eq_val for name in PORTFOLIO_ETFS}

    prices_bt = prices_filled  # use 0-filled prices for backtest arrays (Numba needs no NaN)

    # 3. Strategy 1: Equal weight baseline (static, no regime model)
    print("[3] Running Equal Weight strategy...")
    equalw_nav, _, _ = run_backtest(prices_bt, market_data, ma60_arr,
                                    base_weights_df=eq_weights_df, override_weights=equal_weights,
                                    trade_start_idx=trade_start_idx)

    # 4. Strategy 2: Equal Base + V2 Regime model
    print("[4] Running Equal Base + Regime strategy...")
    regime_nav, regime_wh, n_trades_eq = run_backtest(prices_bt, market_data, ma60_arr,
                                                      base_weights_df=eq_weights_df,
                                                      trade_start_idx=trade_start_idx)

    # 5. Strategy 3: Dynamic Sharpe Weight baseline (no regime model, just dynamic base)
    print("[5] Running Dynamic Trailing Sharpe strategy...")
    altw_nav, _, _ = run_backtest(prices_bt, market_data, ma60_arr,
                                  base_weights_df=alt_weights_df, use_regime=False,
                                  trade_start_idx=trade_start_idx)

    # 6. Strategy 4: Dynamic Base + V2 Regime model
    print("[6] Running Dynamic Base + Regime strategy...")
    altw_regime_nav, altw_regime_wh, n_trades_alt = run_backtest(prices_bt, market_data, ma60_arr,
                                                                 base_weights_df=alt_weights_df,
                                                                 trade_start_idx=trade_start_idx)

    # 7. Load CSI300 benchmark (aligned to trade window)
    bench_nav = load_benchmark(equalw_nav.index)

    # 8. Count weak-market days (trade window only)
    weak_flags = market_data['weak_market'].reindex(equalw_nav.index).fillna(False)
    n_weak_days = int(weak_flags.sum())

    # 9. Print results
    print_results(equalw_nav, regime_nav, altw_nav, altw_regime_nav, bench_nav,
                  regime_wh, altw_regime_wh, n_trades_eq, n_trades_alt, n_weak_days, len(equalw_nav))



if __name__ == "__main__":
    main()
