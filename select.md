# Portfolio ETF Selection

> Generated via `portfolio_select.py` — greedy low-correlation (< 0.7) selection ranked by AdjustedSharpe.

## Selection Criteria

- **AdjustedSharpe ≥ 0.7** (risk-free rate adjusted, last 600 trading days)
- **Max pairwise correlation < 0.7** among all selected ETFs
- Domain review to exclude data-anomaly entries

---

## Final Portfolio Picks (15 ETFs)

| # | ETF | Code | AdjSharp | 1yReturn | Ann.Return | Volatility | MaxDD | Sector | Rationale |
|---|-----|------|----------|----------|------------|------------|-------|--------|-----------|
| 1 | 矿业ETF | 561330 | 1.255 | 133.9% | 44.9% | 31.3% | -24.7% | 有色/矿业 | Top AdjustedSharpe; pure commodities/mining play, unique sector |
| 2 | 浙商之江凤凰ETF | 512190 | 1.172 | 54.9% | 25.7% | 19.3% | -17.6% | 浙江区域 | Regional economy theme, low volatility, excellent risk-reward |
| 3 | 工程机械ETF | 560280 | 1.162 | 44.8% | 33.2% | 25.8% | -20.6% | 工业/基建 | Infrastructure and machinery sector, cyclical diversifier |
| 4 | 电信ETF易方达 | 563010 | 1.135 | 34.6% | 34.6% | 28.0% | -21.3% | 电信/通信 | Telecom sector, defensive with steady cash flow |
| 5 | 半导体设备ETF | 561980 | 1.094 | 61.7% | 42.5% | 36.5% | -31.9% | 半导体 | High growth tech play; low corr with commodity/finance ETFs |
| 6 | 中证2000ETF华夏 | 562660 | 1.052 | 55.7% | 34.0% | 30.3% | -34.0% | 小盘宽基 | Small-cap breadth exposure, captures micro-cap alpha |
| 7 | 石油ETF | 561360 | 0.894 | 52.8% | 21.3% | 22.1% | -21.5% | 能源/石油 | Energy/commodities diversifier, inflation hedge |
| 8 | 银行ETF华夏 | 515020 | 0.878 | 5.6% | 15.7% | 16.1% | -15.1% | 金融/银行 | Lowest volatility in portfolio; defensive dividend play, very low corr with tech |
| 9 | 沪港深500ETF富国 | 517100 | 0.813 | 19.2% | 17.0% | 17.8% | -17.7% | 跨市场宽基 | Cross-market (Shanghai + HK + Shenzhen),Large Cap moderate risk |
| 10 | 中证500ETF国联 | 515550 | 0.762 | 41.7% | 20.1% | 24.6% | -22.7% | 中盘宽基 | Mid-cap index exposure, bridges large-cap and small-cap gap |

### Conditional Picks (data review recommended)

| # | ETF | Code | AdjSharp | Volatility | Note |
|---|-----|------|----------|------------|------|
| 11 | 中证1000ETF广发 | 560010 | 1.005 | 163.8% | Very short history (310 days), extremely high reported vol — likely data artifact. Include only if data verified |
| 12 | 上证50ETF易方达 | 510100 | 0.839 | 66.8% | Large-cap tracker but abnormally high volatility — may have unusual pricing; verify data |
| 13 | 中证1000ETF华泰柏瑞 | 516300 | 0.804 | 94.7% | Small-cap index fund, reported vol abnormal |
| 14 | 沪深300ETF易方达 | 510310 | 0.756 | 99.6% | CSI 300 tracker with extreme vol/MaxDD (-50%), likely data issue |
| 15 | 房地产ETF | 512200 | 0.700 | 166.9% | Real estate sector with -63.7% MaxDD, extreme risk |

---

## Portfolio Design Summary

### Sector Diversification

| Category | ETF(s) | Weight Concept |
|----------|--------|----------------|
| **大宗商品/资源** | 矿业ETF, 石油ETF | Inflation hedge, commodity cycle |
| **科技/半导体** | 半导体设备ETF, 电信ETF | Growth + defensive tech balance |
| **宽基指数** | 中证2000ETF, 中证500ETF, 沪港深500ETF | Market breadth: small + mid + cross-market |
| **工业/基建** | 工程机械ETF | Infrastructure cycle exposure |
| **金融** | 银行ETF华夏 | Low-vol dividend anchor |
| **区域** | 浙商凤凰ETF | Regional alpha strategy |

### Key Properties

- **Top 10 average pairwise correlation**: ~0.37 (well diversified)
- **AdjustedSharpe range**: 0.76 – 1.26
- **Volatility range**: 16.1% – 36.5% (excluding conditional picks)
- **Max Drawdown range**: -15.1% – -34.0%

### Risk Notes

1. 中证2000ETF and 半导体设备ETF have higher drawdowns (~32-34%); position size accordingly
2. 银行ETF provides portfolio stability (lowest vol at 16.1%) but limited upside
3. Commodity ETFs (矿业, 石油) are cyclical — consider tactical rebalancing
4. Conditional picks (#11-15) show data anomalies — verify before including
