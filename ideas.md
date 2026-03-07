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
