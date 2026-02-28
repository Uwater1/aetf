#!/usr/bin/env python3
"""
Portfolio Backtest with Dynamic Regime-Switching Alpha Model

Alpha Model:
  - Per-ETF volatility regime detection:
    → Low vol: Mean-reversion Z-score (buy the dip, with MA5 stop-loss)
    → High vol: Momentum (buy the winner)
  - Defensive tilt: 3 proven ETFs get priority when market is weak
    → Weak market: CSI300 < EMA60 AND Volume MA5 < Volume MA60
  - Dynamic rebalancing: trade only when max weight deviation > threshold

Benchmark: Equal-weight portfolio (10% each)
"""

import os
import pandas as pd
import numpy as np
import pandas_ta as ta
from numba import njit
# ─── Configuration ───────────────────────────────────────────────────────────
BASE_DIR = '/home/hallo/Documents/aetf'
SELECTED_DIR = os.path.join(BASE_DIR, 'selected2')
RF_FILE = os.path.join(BASE_DIR, 'riskFreeRate.csv')
BENCHMARK_ETF = '沪深300ETF广发_510360'
VOLUME_FILE = os.path.join(BASE_DIR, 'volume.csv')

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

# Defensive ETFs: proven resilient in downturns
DEFENSIVE_ETFS = ['银行ETF华夏_515020', '浙商之江凤凰ETF_512190', '石油ETF_561360']
DEFENSIVE_MULTIPLIER = 1.5           # Score boost for defensive ETFs in weak market

# Alpha model parameters
MA_WINDOWS = [40, 80, 120]           # Multi-timeframe moving average windows
MA_BLEND_WEIGHTS = [0.3, 0.4, 0.3]   # Blend weights for each MA timeframe
MOMENTUM_WINDOW = 20                 # Short-term momentum lookback (trading days)
MIN_WEIGHT = 0.03                    # 3% minimum weight per ETF
VOL_LOOKBACK = 60                    # Rolling window for volatility scaling
STAMP_DUTY = 0.001                   # 0.1% stamp duty on sold value at each rebalance
REBALANCE_THRESHOLD = 0.10           # Rebalance when max weight deviation > 10%
MIN_HOLD_DAYS = 5                    # Minimum days between rebalances (cooldown)
VOL_REGIME_WINDOW = 20               # Rolling window for per-ETF vol regime detection

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

    # Weak market: both conditions must hold
    market['weak_market'] = (
        (market['csi300_close'] < market['csi300_ema60']) &
        (market['vol_ma5'] < market['vol_ma60'])
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
    """Vectorize all per-ETF indicator series once using pandas_ta.

    Returns:
      - indicators_arr: float64 array of shape (n_etfs, n_days, 8)
        Indices: 0=ma5, 1=ma40, 2=ma80, 3=ma120, 4=vol20, 5=std40, 6=std80, 7=std120
      - vol_medians: float64 array of shape (n_etfs,)
    """
    n_days = len(prices)
    n_etfs = len(prices.columns)
    indicators_arr = np.zeros((n_etfs, n_days, 8))
    vol_medians = np.zeros(n_etfs)

    for i, name in enumerate(prices.columns):
        s = prices[name]
        ret = s.pct_change()
        indicators_arr[i, :, 0] = ta.sma(s, length=5).fillna(0).values
        indicators_arr[i, :, 1] = ta.sma(s, length=40).fillna(0).values
        indicators_arr[i, :, 2] = ta.sma(s, length=80).fillna(0).values
        indicators_arr[i, :, 3] = ta.sma(s, length=120).fillna(0).values
        
        vol20 = ret.rolling(VOL_REGIME_WINDOW).std() * np.sqrt(252)
        indicators_arr[i, :, 4] = vol20.fillna(0).values
        vol_medians[i] = vol20.median() if not vol20.dropna().empty else 0.0

        # Precompute rolling STDs for Z-score (using same windows as MAs)
        indicators_arr[i, :, 5] = s.rolling(40).std().fillna(0).values
        indicators_arr[i, :, 6] = s.rolling(80).std().fillna(0).values
        indicators_arr[i, :, 7] = s.rolling(120).std().fillna(0).values

    return indicators_arr, vol_medians


@njit
def jit_backtest_core(
    prices_arr, daily_returns_arr, weak_market_arr, indicators_arr, vol_medians,
    defensive_mask, n_days, n_etfs, min_weight, rebalance_threshold, min_hold_days, stamp_duty,
    vol_regime_window, momentum_window, ma_blend_weights, defensive_multiplier,
    override_weights_arr=None
):
    nav_history = np.zeros(n_days)
    weight_history_vals = np.zeros((n_days, n_etfs))
    rebalance_flags = np.zeros(n_days, dtype=np.bool_)
    
    nav = 1.0
    nav_history[0] = nav
    
    # Init first day
    if override_weights_arr is not None:
        current_weights = override_weights_arr.copy()
    else:
        # Initial scoring logic (expanded to avoid sub-function overhead in JIT for now)
        scores = np.zeros(n_etfs)
        for i in range(n_etfs):
            current = prices_arr[0, i]
            short_vol = indicators_arr[i, 0, 4]
            median_vol = vol_medians[i]
            
            if short_vol >= median_vol:
                scores[i] = 0.0 # simplified for index 0
            else:
                blended_z = 0.0
                # ma40=1, ma80=2, ma120=3; std40=5, std80=6, std120=7
                for k in range(3):
                    ma_val = indicators_arr[i, 0, k+1]
                    std_val = indicators_arr[i, 0, k+5]
                    if ma_val > 0 and std_val > 0:
                        blended_z += ma_blend_weights[k] * (ma_val - current) / std_val
                scores[i] = blended_z
                
                ma5_val = indicators_arr[i, 0, 0]
                if ma5_val > 0 and current < ma5_val:
                    scores[i] *= 0.5
        
        min_score = np.min(scores)
        shifted = scores - min_score + 0.1
        if weak_market_arr[0]:
            for i in range(n_etfs):
                if defensive_mask[i]:
                    shifted[i] *= defensive_multiplier
        
        total = np.sum(shifted)
        raw = shifted / total
        floored = np.maximum(raw, min_weight)
        current_weights = floored / np.sum(floored)

    weight_history_vals[0] = current_weights
    holdings = nav * current_weights
    n_trades = 0
    days_since_rebalance = min_hold_days

    for t in range(1, n_days):
        # Update holdings with returns
        for i in range(n_etfs):
            holdings[i] *= (1.0 + daily_returns_arr[t, i])
        
        nav = np.sum(holdings)
        drifted_w = holdings / nav
        
        # Target weights
        if override_weights_arr is not None:
            target_weights = override_weights_arr
        else:
            scores = np.zeros(n_etfs)
            for i in range(n_etfs):
                current = prices_arr[t, i]
                short_vol = indicators_arr[i, t, 4]
                median_vol = vol_medians[i]
                
                if short_vol >= median_vol:
                    mom_start = max(0, t - momentum_window)
                    p_start = prices_arr[mom_start, i]
                    scores[i] = (current / p_start - 1.0) if p_start > 0 else 0.0
                else:
                    blended_z = 0.0
                    for k in range(3):
                        ma_val = indicators_arr[i, t, k+1]
                        std_val = indicators_arr[i, t, k+5]
                        if ma_val > 0 and std_val > 0:
                            blended_z += ma_blend_weights[k] * (ma_val - current) / std_val
                    scores[i] = blended_z
                    ma5_val = indicators_arr[i, t, 0]
                    if ma5_val > 0 and current < ma5_val:
                        scores[i] *= 0.5
            
            min_score = np.min(scores)
            shifted = scores - min_score + 0.1
            if weak_market_arr[t]:
                for i in range(n_etfs):
                    if defensive_mask[i]:
                        shifted[i] *= defensive_multiplier
            
            total = np.sum(shifted)
            raw = shifted / total
            floored = np.maximum(raw, min_weight)
            target_weights = floored / np.sum(floored)

        # Deviation
        max_dev = 0.0
        for i in range(n_etfs):
            dev = abs(drifted_w[i] - target_weights[i])
            if dev > max_dev:
                max_dev = dev
        
        if max_dev > rebalance_threshold and days_since_rebalance >= min_hold_days:
            # Rebalance
            stamp_cost = 0.0
            for i in range(n_etfs):
                new_val = nav * target_weights[i]
                if holdings[i] > new_val:
                    stamp_cost += stamp_duty * (holdings[i] - new_val)
            
            nav -= stamp_cost
            current_weights = target_weights
            holdings = nav * current_weights
            weight_history_vals[t] = current_weights
            rebalance_flags[t] = True
            n_trades += 1
            days_since_rebalance = 0
        else:
            days_since_rebalance += 1
            # In the original, weight_history only appends on rebalance.
            # To maintain compatibility, we'll return rebalance_flags.
            
        nav_history[t] = nav

    return nav_history, weight_history_vals, rebalance_flags, n_trades


def run_backtest(prices, rf_daily, market_data, indicators_setup, override_weights=None):
    """
    Run the backtest with dynamic threshold-based rebalancing, optimized by Numba.
    """
    indicators_arr, vol_medians = indicators_setup
    etf_names = prices.columns.tolist()
    prices_arr = prices.values
    daily_returns_arr = prices.pct_change().fillna(0).values
    weak_market_arr = market_data['weak_market'].reindex(prices.index).fillna(False).values.astype(np.bool_)
    
    defensive_mask = np.array([name in DEFENSIVE_ETFS for name in etf_names], dtype=np.bool_)
    
    ov_weights_arr = None
    if override_weights is not None:
        ov_weights_arr = np.array([override_weights.get(name, 0.0) for name in etf_names])

    nav_hist, weight_hist_vals, rebalance_flags, n_trades = jit_backtest_core(
        prices_arr, daily_returns_arr, weak_market_arr, indicators_arr, vol_medians,
        defensive_mask, len(prices), len(etf_names), MIN_WEIGHT, REBALANCE_THRESHOLD, 
        MIN_HOLD_DAYS, STAMP_DUTY, VOL_REGIME_WINDOW, MOMENTUM_WINDOW, 
        np.array(MA_BLEND_WEIGHTS), DEFENSIVE_MULTIPLIER, ov_weights_arr
    )
    
    # Format outputs back to Pandas
    nav_series = pd.Series(nav_hist, index=prices.index)
    
    weight_history = []
    # Include initial weight
    weight_history.append({'date': prices.index[0], 'weights': dict(zip(etf_names, weight_hist_vals[0]))})
    
    # Include subsequent rebalances
    for t in range(1, len(prices)):
        if rebalance_flags[t]:
            weight_history.append({'date': prices.index[t], 'weights': dict(zip(etf_names, weight_hist_vals[t]))})

    return nav_series, weight_history, n_trades


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


def print_results(equalw_nav, regime_nav, bench_nav,
                  regime_wh, rf_daily, n_trades, n_weak_days, n_total_days):
    """Print 2-strategy performance comparison and diagnostics."""
    eq_m = compute_metrics(equalw_nav, rf_daily)
    rg_m = compute_metrics(regime_nav, rf_daily)
    bn_m = compute_metrics(bench_nav,  rf_daily)

    COL = 14
    print("\n" + "=" * 70)
    print("  PERFORMANCE COMPARISON  (2 strategies + CSI300 benchmark)")
    print("=" * 70)
    print(f"\n{'Metric':<20} {'EqualW':>{COL}} {'Regime+Def':>{COL}} {'CSI300':>{COL}}")
    print("-" * 70)
    for key in eq_m:
        print(f"{key:<20} {eq_m[key]:>{COL}} {rg_m[key]:>{COL}} {bn_m[key]:>{COL}}")

    # Diagnostics
    print(f"\n  Rebalance trades fired : {n_trades}")
    print(f"  Weak market days       : {n_weak_days}/{n_total_days} ({n_weak_days/n_total_days:.1%})")

    # Compact weight history
    etf_short = {n: n.split('_')[0][:6] for n in PORTFOLIO_ETFS}
    print(f"\n{'=' * 70}")
    print("  WEIGHT ALLOCATION — Regime+Defensive (last 10 rebalances shown)")
    print("=" * 70)
    for entry in regime_wh[-10:]:
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
    print("  Portfolio Backtest — Regime+Defensive Strategy")
    print(f"  Params: MA={MA_WINDOWS}/{MA_BLEND_WEIGHTS} Mom={MOMENTUM_WINDOW}d "
          f"Vol={VOL_LOOKBACK}d MinW={MIN_WEIGHT} Thresh={REBALANCE_THRESHOLD} Stamp={STAMP_DUTY}")
    print(f"  Defensive ETFs: {[e.split('_')[0] for e in DEFENSIVE_ETFS]} "
          f"(multiplier={DEFENSIVE_MULTIPLIER}x in weak market)")

    # 1. Load ETF prices, risk-free rate, market regime data
    print("\n[1] Loading data...")
    prices    = load_all_data(PORTFOLIO_ETFS)
    rf_daily  = load_risk_free_rate()
    market_data = load_market_data()
    print(f"    Price data : {prices.index[0].date()} → {prices.index[-1].date()}, {len(prices)} days")
    print(f"    ETFs       : {len(prices.columns)}")

    # 2. Precompute per-ETF indicator tables (pandas_ta, done once)
    print("[2] Precomputing indicators...")
    indicators = precompute_indicators(prices)

    # 3. Strategy 1: Equal weight baseline (static, threshold-triggered rebalance)
    print("[3] Running Equal Weight strategy...")
    equal_weights = {name: 1.0 / len(PORTFOLIO_ETFS) for name in PORTFOLIO_ETFS}
    equalw_nav, _, _ = run_backtest(prices, rf_daily, market_data, indicators,
                                    override_weights=equal_weights)

    # 4. Strategy 2: Regime + Defensive tilt (dynamic weights)
    print("[4] Running Regime+Defensive strategy...")
    regime_nav, regime_wh, n_trades = run_backtest(prices, rf_daily, market_data, indicators)

    # 5. Load CSI300 benchmark
    bench_nav = load_benchmark(equalw_nav.index)

    # 6. Count weak-market days (for diagnostics)
    price_dates = prices.index
    weak_flags = market_data['weak_market'].reindex(price_dates).fillna(False)
    n_weak_days = int(weak_flags.sum())

    # 7. Print results
    print_results(equalw_nav, regime_nav, bench_nav,
                  regime_wh, rf_daily, n_trades, n_weak_days, len(prices))


if __name__ == "__main__":
    main()

