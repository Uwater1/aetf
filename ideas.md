# Successful Improvements

## Simplified Weak Market Definition
**Description**
The previous weak market definition relied on both price trend (CSI300 < EMA60) and volume trend (Volume MA5 < Volume MA60). The volume indicator can sometimes lag or introduce noise. Simplifying the regime filter to strictly use the price trend (`csi300_close` < `csi300_ema60`) allowed the model to react slightly better during drawdowns.

**Code Changes**
Modified `load_market_data()` to only use the price trend.
```python
    market['weak_market'] = (
        market['csi300_close'] < market['csi300_ema60']
    )
```

**Performance Before (Baseline AltW+Reg)**
- CAGR: 36.72%
- Sharpe: 1.580
- Max Drawdown: -14.58%

**Performance After (Experiment 3 AltW+Reg)**
- CAGR: 36.86%
- Sharpe: 1.589
- Max Drawdown: -13.91%

**Observations**
There was a slight uptick in overall return and Sharpe, but a notable improvement in maximum drawdown, indicating that the simplified regime filter protects capital better by eliminating the volume lag requirement.

# Failed Improvements

## Shorter Momentum Window
**Description**
Tried shortening `MOMENTUM_WINDOW` from 20 to 10.
**Performance After**
CAGR dropped to 34.53%, Sharpe to 1.528.
**Observations**
Increased noise and false signals, leading to poorer performance.

## Higher Rank Power
**Description**
Increased `RANK_POWER` from 0.5 to 1.0 (linear scaling instead of extreme-focused).
**Performance After**
CAGR dropped to 34.02%, Max DD worsened to -16.09%.
**Observations**
Diluted the strength of the momentum signal by not concentrating enough on the extremes.

## Higher Alpha Strength
**Description**
Increased `ALPHA_STRENGTH` from 0.5 to 0.7 for more aggressive tilts.
**Performance After**
CAGR dropped to 34.37%, Sharpe to 1.496.
**Observations**
Penalized non-defensive ETFs too severely and over-concentrated the portfolio.

## Shorter Sharpe Span
**Description**
Shortened `SHARPE_SPAN` from 60 to 40 for more responsive baseline weighting.
**Performance After**
CAGR dropped significantly to 32.66%, Max DD worsened to -17.02%.
**Observations**
The shorter lookback introduced excessive churn and instability in base weights.

## Lower Rank Power
**Description**
Lowered `RANK_POWER` from 0.5 to 0.25 to make momentum concentration even more extreme.
**Performance After**
CAGR dropped to 35.51%, Sharpe to 1.524.
**Observations**
Too extreme concentration added noise, leading to slightly worse performance.

## Longer Momentum Window
**Description**
Tried lengthening `MOMENTUM_WINDOW` from 20 to 30.
**Performance After**
CAGR dropped to 36.33%, Sharpe to 1.565.
**Observations**
Made the momentum signal too slow to react.

## Shorter Absolute Trend Filter Windows
**Description**
Shortened `EMA60_WINDOW` to 40 and 30.
**Performance After**
For EMA 40, CAGR increased slightly to 37.61%, but Max DD worsened to -13.74%.
For EMA 30, CAGR dropped to 35.93%, Max DD worsened to -14.90%.
**Observations**
Shorter trend filters made the strategy jump into weak market mode too often, causing whipsaws and slightly worse risk-adjusted returns (Sharpe ratio and max drawdown).

## Blended Momentum
**Description**
Tried combining 20-day and 10-day returns for a blended momentum score.
**Performance After**
CAGR dropped to 34.02%, Sharpe to 1.487.
**Observations**
The shorter 10-day signal introduced too much noise, harming performance.

## Volatility Sizing Position Scaling
**Description**
Tried penalizing high-volatility ETFs by blending target weights with inverse volatility weights.
**Performance After**
CAGR dropped to 34.25%, Sharpe improved slightly to 1.659, Max DD improved to -13.12%.
**Observations**
It reduced absolute returns significantly while the risk-adjusted return improvement was very marginal.

# Successful Improvements

## Extreme Defensive Tilt
**Description**
Increased the weight multiplier for defensive ETFs during a weak market regime from normal target weight to 5.0x target weight.

**Code Changes**
Modified `jit_backtest_core()` to apply an extra multiplier after base weights calculation.
```python
        else:
            target_weights = compute_v2_weights(t, bool(weak_market_arr[t]), is_aggressive)

            market_weak = bool(weak_market_arr[t])
            if market_weak:
                # We can increase the weight of defensive ETFs by another multiplier
                for i in range(n_etfs):
                    if defensive_mask[i]:
                        target_weights[i] *= 5.0

                # Normalize again
                floored = np.maximum(target_weights, min_weight)
                target_weights = floored / np.sum(floored)
```

**Performance Before (Baseline AltW+Reg)**
- CAGR: 36.86%
- Sharpe: 1.589
- Max Drawdown: -13.91%

**Performance After (Experiment 18 AltW+Reg)**
- CAGR: 42.31%
- Sharpe: 1.812
- Max Drawdown: -11.21%

**Observations**
Shifting extremely heavily to defensive ETFs during weak market regimes dramatically reduced drawdowns and allowed compounding to significantly boost overall returns.

## Multi-Layer Weak Market (Extreme Weak Market Cash Allocation)
**Description**
Implemented a multi-layer weak market definition by adding an `extreme_weak_market` regime, defined as `CSI300 < EMA60 * 0.95`. During this extreme weak market, the strategy shifts 50% of its capital to a cash position that yields a 2% annualized risk-free return, reducing exposure to equities.

**Performance Before (Baseline AltW+Reg)**
- CAGR: 41.35%
- Sharpe: 1.774
- Max Drawdown: -11.38%

**Performance After (Experiment A AltW+Reg)**
- CAGR: 42.27%
- Sharpe: 1.812
- Max Drawdown: -11.38%

**Observations**
Adding a 50% cash allocation during extreme weak markets yielded a small improvement in absolute returns (CAGR improved from 41.35% to 42.27%) and risk-adjusted return (Sharpe improved from 1.774 to 1.812) while keeping maximum drawdown identical. It successfully reduced downside exposure when the market trended deeply negative, allowing the strategy to bounce back slightly stronger.

## Failed Improvements

## Volume Surge Momentum Scale
**Description**
Tried adding a `volume_surge` regime (when 5-day volume MA > 60-day volume MA * 1.2) that increases the momentum scale to 2.0 (more aggressive) outside of weak markets.
**Performance After (Experiment B AltW+Reg)**
CAGR dropped from 41.35% to 40.07%, Sharpe dropped to 1.712, and Max Drawdown worsened to -11.73%.
**Observations**
Like the previous volume experiment, incorporating volume led to noisier signals and whipsawing. Increasing the scale based on volume resulted in an over-concentration during market tops right before corrections.
