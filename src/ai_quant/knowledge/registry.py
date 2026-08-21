"""
Authoritative Financial Knowledge Registry.
Provides exhaustive explanations, formulas, interpretations, and usage guides
for every financial and quantitative metric across the workstation.
"""

from typing import Dict, List, Optional
from src.ai_quant.knowledge.models import FinancialMetricExplanation, MetricCategory


class FinancialKnowledgeRegistry:
    """
    In-memory registry of financial metrics and pedagogical explanations.
    """

    def __init__(self):
        self._metrics: Dict[str, FinancialMetricExplanation] = {}
        self._populate_defaults()

    def register(self, metric: FinancialMetricExplanation) -> None:
        self._metrics[metric.id.lower()] = metric

    def get(self, metric_id: str) -> Optional[FinancialMetricExplanation]:
        return self._metrics.get(metric_id.lower())

    def list_by_category(self, category: MetricCategory) -> List[FinancialMetricExplanation]:
        return [m for m in self._metrics.values() if m.category == category]

    def all_metrics(self) -> List[FinancialMetricExplanation]:
        return list(self._metrics.values())

    def search(self, query: str) -> List[FinancialMetricExplanation]:
        q = query.lower().strip()
        if not q:
            return self.all_metrics()
        results = []
        for m in self._metrics.values():
            if (
                q in m.id.lower()
                or q in m.name.lower()
                or q in m.summary.lower()
                or q in m.interpretation.lower()
                or q in m.quant_usage.lower()
            ):
                results.append(m)
        return results

    def _populate_defaults(self) -> None:
        # 1. VALUATION METRICS
        self.register(
            FinancialMetricExplanation(
                id="pe_ratio",
                name="Price-to-Earnings Ratio (P/E)",
                category=MetricCategory.VALUATION,
                summary="Measures a company's current share price relative to its per-share earnings, reflecting market expectations of future growth.",
                formula="P/E = \\frac{\\text{Market Price per Share}}{\\text{Earnings per Share (EPS)}}",
                interpretation="High P/E indicates high expected earnings growth or overvaluation. Low P/E suggests value opportunity or fundamental business contraction.",
                quant_usage="Used as a standard value factor in cross-sectional rank scoring, neutralized across sector medians.",
                pitfalls="Useless when earnings are negative. Highly distorted by one-time non-operating gains or accounting write-offs.",
                ranges={"Deep Value": "< 12", "Market Average": "15 - 25", "Growth / Premium": "> 35"},
                related_metrics=["peg_ratio", "ev_ebitda", "fcf_yield"],
            )
        )

        self.register(
            FinancialMetricExplanation(
                id="pb_ratio",
                name="Price-to-Book Ratio (P/B)",
                category=MetricCategory.VALUATION,
                summary="Compares a company's market capitalization to its accounting book value (net asset value).",
                formula="P/B = \\frac{\\text{Market Capitalization}}{\\text{Total Assets} - \\text{Total Liabilities}}",
                interpretation="P/B < 1 indicates a stock trading below liquidation value. High P/B reflects high return on equity or intangible asset value.",
                quant_usage="Core component of the Fama-French High-Minus-Low (HML) Value factor in factor neutralization.",
                pitfalls="Fails to capture intangible assets (intellectual property, software, brand equity) common in modern asset-light tech corporations.",
                ranges={"Undervalued / Distress": "< 1.0", "Normal Equity": "1.5 - 4.0", "High Premium": "> 8.0"},
                related_metrics=["pe_ratio", "altman_z_score"],
            )
        )

        self.register(
            FinancialMetricExplanation(
                id="ev_ebitda",
                name="Enterprise Value to EBITDA (EV/EBITDA)",
                category=MetricCategory.VALUATION,
                summary="Evaluates total company value (including net debt) relative to operating cash flow generation before financing and non-cash expenses.",
                formula="\\text{EV/EBITDA} = \\frac{\\text{Market Cap} + \\text{Total Debt} - \\text{Cash}}{\\text{EBITDA}}",
                interpretation="Capital-structure neutral valuation metric. Lower multiples indicate cheaper fundamental cash flow multiples.",
                quant_usage="Neutralized value factor used to rank corporate operating efficiency irrespective of debt leverage.",
                pitfalls="Ignores capital expenditures (CapEx) needed to maintain asset base, which can mislead in capital-intensive industries.",
                ranges={"Cheap": "< 8.0", "Fair Value": "10.0 - 15.0", "Expensive": "> 20.0"},
                related_metrics=["fcf_yield", "pe_ratio"],
            )
        )

        self.register(
            FinancialMetricExplanation(
                id="fcf_yield",
                name="Free Cash Flow Yield",
                category=MetricCategory.VALUATION,
                summary="The percentage of free cash flow a company generates relative to its market capitalization.",
                formula="\\text{FCF Yield} = \\frac{\\text{Operating Cash Flow} - \\text{Capital Expenditures}}{\\text{Market Capitalization}}",
                interpretation="Higher yields signify strong cash generation available for dividends, share buybacks, or debt retirement.",
                quant_usage="High-priority cash-flow quality and value factor in alpha combination models.",
                pitfalls="Can fluctuate wildly year-over-year due to lumpiness in capital expenditure cycles.",
                ranges={"Attractive Yield": "> 7.0%", "Moderate": "3.0% - 6.0%", "Low Cash Generation": "< 2.0%"},
                related_metrics=["ev_ebitda", "sloan_accruals"],
            )
        )

        self.register(
            FinancialMetricExplanation(
                id="peg_ratio",
                name="Price/Earnings-to-Growth Ratio (PEG)",
                category=MetricCategory.VALUATION,
                summary="Adjusts the traditional P/E ratio by dividing by the company's expected annual EPS growth rate.",
                formula="\\text{PEG} = \\frac{P/E}{\\text{Annual EPS Growth Rate (\\%)}}",
                interpretation="PEG < 1.0 suggests a stock is undervalued given its earnings trajectory; PEG > 2.0 suggests overvaluation.",
                quant_usage="Growth-at-a-reasonable-price (GARP) filter applied before portfolio sizing.",
                pitfalls="Heavily dependent on forward consensus analyst estimates, which often suffer from systematic optimism bias.",
                ranges={"Undervalued (GARP)": "< 1.0", "Fair Value": "1.0 - 1.5", "Overextended": "> 2.0"},
                related_metrics=["pe_ratio"],
            )
        )

        # 2. FORENSIC & FINANCIAL INTEGRITY METRICS
        self.register(
            FinancialMetricExplanation(
                id="altman_z_score",
                name="Altman Z-Score (Bankruptcy Risk)",
                category=MetricCategory.FORENSIC,
                summary="Multivariate statistical formula measuring a corporation's probability of bankruptcy within two years based on balance sheet health.",
                formula="Z = 1.2X_1 + 1.4X_2 + 3.3X_3 + 0.6X_4 + 0.999X_5",
                interpretation="Scores above 2.99 indicate safe financial health. Scores below 1.81 indicate significant distress and default vulnerability.",
                quant_usage="Hard gate filter: equities scoring in the Distress Zone (Z < 1.81) are disqualified from long portfolio allocations.",
                pitfalls="Originally calibrated on manufacturing corporations; non-manufacturing formula must be used for service/tech firms. Not applicable to banks or funds.",
                ranges={"Distress Zone": "< 1.81", "Grey Zone": "1.81 - 2.99", "Safe Zone": "> 2.99"},
                related_metrics=["piotroski_f_score", "beneish_m_score"],
            )
        )

        self.register(
            FinancialMetricExplanation(
                id="piotroski_f_score",
                name="Piotroski 9-Point F-Score",
                category=MetricCategory.FORENSIC,
                summary="Discrete 9-point score assessing profitability, leverage/liquidity, and operating efficiency trends over trailing periods.",
                formula="F = \\sum_{i=1}^9 I_i \\quad (\\text{Profitability: 4, Leverage: 3, Operating Efficiency: 2})",
                interpretation="Scores 8-9 represent pristine fundamental momentum. Scores 0-3 denote deteriorating operational health.",
                quant_usage="Quality hurdle: only value assets with F-Score >= 6 are eligible for positive alpha scoring to prevent value traps.",
                pitfalls="Binary thresholding can penalize minor temporary fluctuations in working capital.",
                ranges={"Weak / Deteriorating": "0 - 3", "Average": "4 - 6", "Strong Fundamental Momentum": "7 - 9"},
                related_metrics=["altman_z_score", "sloan_accruals"],
            )
        )

        self.register(
            FinancialMetricExplanation(
                id="beneish_m_score",
                name="Beneish M-Score (Earnings Manipulation)",
                category=MetricCategory.FORENSIC,
                summary="8-factor probit regression model that detects whether a corporation is likely manipulating its reported earnings.",
                formula="M = -4.84 + 0.920\\cdot\\text{DSRI} + 0.528\\cdot\\text{GMI} + 0.404\\cdot\\text{AQI} + 0.892\\cdot\\text{SGI} + 0.115\\cdot\\text{DEPI} - 0.172\\cdot\\text{SGAI} + 4.037\\cdot\\text{TATA} + 0.0327\\cdot\\text{LVGI}",
                interpretation="An M-Score greater than -1.78 indicates a high probability of earnings manipulation and accounting irregularities.",
                quant_usage="Red flag forensic screen: any equity with M-Score > -1.78 is immediately vetoed from capital allocation.",
                pitfalls="High growth companies experiencing genuine rapid scaling may trigger false positives on SGI and AQI.",
                ranges={"Manipulator Likely": "> -1.78", "Non-Manipulator / Clean": "< -1.78"},
                related_metrics=["sloan_accruals", "piotroski_f_score"],
            )
        )

        self.register(
            FinancialMetricExplanation(
                id="sloan_accruals",
                name="Sloan Accruals Ratio",
                category=MetricCategory.FORENSIC,
                summary="Evaluates the quality of earnings by measuring the proportion of net income driven by accounting accruals versus real cash generation.",
                formula="\\text{Accruals} = \\frac{\\text{Net Income} - (\\text{CFO} + \\text{CFI})}{\\text{Average Total Assets}}",
                interpretation="Accruals > 10% indicate low-quality earnings prone to future mean-reversion. Negative accruals indicate high cash-backed earnings.",
                quant_usage="Earnings quality factor: penalizes companies where net income outpaces cash flows from operations.",
                pitfalls="Must adjust for acquisitions and divestitures which distort balance sheet asset changes.",
                ranges={"High Quality (Cash-Rich)": "< -5.0%", "Neutral": "-5.0% - 5.0%", "Low Quality (Accrual Heavy)": "> 10.0%"},
                related_metrics=["beneish_m_score", "fcf_yield"],
            )
        )

        # 3. RISK & PERFORMANCE METRICS
        self.register(
            FinancialMetricExplanation(
                id="sharpe_ratio",
                name="Sharpe Ratio",
                category=MetricCategory.RISK,
                summary="Measures risk-adjusted excess return per unit of total portfolio volatility (standard deviation).",
                formula="\\text{Sharpe} = \\frac{E[R_p - R_f]}{\\sigma_p}",
                interpretation="Sharpe > 1.0 is acceptable, > 2.0 is excellent. Measures consistency of excess return generation.",
                quant_usage="Primary baseline benchmark for backtest strategy performance evaluation.",
                pitfalls="Assumes returns are normally distributed; penalizes upside volatility equally with downside losses.",
                ranges={"Sub-optimal": "< 1.0", "Institutional Standard": "1.0 - 2.0", "Elite Quant Alpha": "> 2.5"},
                related_metrics=["sortino_ratio", "dsr"],
            )
        )

        self.register(
            FinancialMetricExplanation(
                id="sortino_ratio",
                name="Sortino Ratio",
                category=MetricCategory.RISK,
                summary="Differentiates harmful downside volatility from total volatility by only penalizing negative return deviations.",
                formula="\\text{Sortino} = \\frac{E[R_p - R_f]}{\\sigma_d}, \\quad \\sigma_d = \\sqrt{\\frac{1}{N}\\sum (\\min(0, R_t - R_f))^2}",
                interpretation="Higher Sortino ratios denote superior protection against downside drawdowns while capturing upside expansion.",
                quant_usage="Used alongside Sharpe to evaluate asymmetric alpha strategies.",
                pitfalls="Requires sufficient downside observations to produce statistically stable estimates.",
                ranges={"Adequate": "1.5 - 2.5", "Superior Downside Control": "> 3.0"},
                related_metrics=["sharpe_ratio", "max_drawdown"],
            )
        )

        self.register(
            FinancialMetricExplanation(
                id="dsr",
                name="Deflated Sharpe Ratio (DSR)",
                category=MetricCategory.RISK,
                summary="Adjusts standard Sharpe Ratio for multiple testing bias, non-normality, and track record length (Bailey & Lopez de Prado).",
                formula="\\text{DSR} = P\\left(SR > SR^* \\mid \\text{trials}=N, \\text{skew}=S, \\text{kurt}=K, \\text{var}(SR)\\right)",
                interpretation="DSR > 0.95 indicates a statistically significant strategy that is unlikely to be the product of backtest data mining.",
                quant_usage="Mandatory quantitative validation hurdle: strategies with DSR < 0.95 cannot be deployed to execution.",
                pitfalls="Sensitive to accurate estimation of the total number of trial models tested during the research phase.",
                ranges={"Overfit / Insignificant": "< 0.80", "Marginal": "0.80 - 0.95", "Statistically Robust Alpha": "> 0.95"},
                related_metrics=["pbo", "sharpe_ratio"],
            )
        )

        self.register(
            FinancialMetricExplanation(
                id="pbo",
                name="Probability of Backtest Overfitting (PBO)",
                category=MetricCategory.RISK,
                summary="Computes the probability that the best in-sample strategy will rank below the median out-of-sample via Combinatorially Symmetric Cross-Validation (CSCV).",
                formula="\\text{PBO} = \\sum_{c \\in \\mathcal{C}} w_c \\cdot \\mathbb{I}(\\text{Rank}_{OOS} < \\text{Median})",
                interpretation="PBO < 0.20 indicates robust generalizability; PBO > 0.50 means the model is no better than random selection.",
                quant_usage="Backtest release gate: models with PBO >= 0.30 are automatically rejected.",
                pitfalls="Requires cross-validation across multiple sliced sub-periods to generate combinatorial matrix.",
                ranges={"Low Overfitting Risk": "< 0.15", "Acceptable": "0.15 - 0.30", "High Overfitting Probability": "> 0.30"},
                related_metrics=["dsr", "sharpe_ratio"],
            )
        )

        self.register(
            FinancialMetricExplanation(
                id="max_drawdown",
                name="Maximum Drawdown (MDD)",
                category=MetricCategory.RISK,
                summary="The maximum observed peak-to-trough percentage decline in portfolio equity before a new peak is attained.",
                formula="\\text{MDD} = \\max_{t \\in [0, T]} \\left( \\frac{\\text{Peak}_t - \\text{Equity}_t}{\\text{Peak}_t} \\right)",
                interpretation="Quantifies maximum historical capital destruction and recovery time requirements.",
                quant_usage="Deterministic risk circuit breaker: engine halts trading if portfolio drawdown exceeds MaxDrawdownPct (10%).",
                pitfalls="Historical MDD is a sample statistic and does not represent the theoretical worst-case loss in tail events.",
                ranges={"Conservative": "< 8.0%", "Moderate": "8.0% - 15.0%", "Severe Stress": "> 20.0%"},
                related_metrics=["cvar_95", "sortino_ratio"],
            )
        )

        self.register(
            FinancialMetricExplanation(
                id="cvar_95",
                name="Conditional Value at Risk (CVaR / Expected Shortfall 95%)",
                category=MetricCategory.RISK,
                summary="Measures the expected average loss in the worst 5% tail of return distributions.",
                formula="\\text{CVaR}_{0.95} = -E[R \\mid R \\le -\\text{VaR}_{0.95}]",
                interpretation="Coherent risk measure that explicitly accounts for severe tail losses beyond normal VaR cutoffs.",
                quant_usage="Used in portfolio optimization constraints to prevent extreme tail blowout risk.",
                pitfalls="Requires fat-tailed empirical distributions or historical resampling; parametric normal distribution severely underestimates CVaR.",
                ranges={"Controlled Tail": "< 2.5% daily", "Elevated Tail Risk": "> 4.0% daily"},
                related_metrics=["max_drawdown", "sharpe_ratio"],
            )
        )

        # 4. PORTFOLIO & FACTOR OPTIMIZATION METRICS
        self.register(
            FinancialMetricExplanation(
                id="barra_neutralization",
                name="Barra-Style Factor Neutralization",
                category=MetricCategory.PORTFOLIO,
                summary="Removes unintended systematic factor exposures (Market Beta, Size, Momentum, Value, Sector) via cross-sectional OLS regression.",
                formula="\\alpha_i = r_i - \\sum_{k=1}^K \\beta_{i,k} F_k",
                interpretation="Ensures the portfolio's returns stem purely from idiosyncratic stock selection rather than broad market or sector bets.",
                quant_usage="Pre-trade alpha purification step before portfolio weight optimization.",
                pitfalls="Over-neutralizing can remove genuine common-factor drivers of alpha, diminishing gross expected returns.",
                ranges={"Residual Alpha": "Zero factor correlation"},
                related_metrics=["ledoit_wolf_covariance", "half_kelly"],
            )
        )

        self.register(
            FinancialMetricExplanation(
                id="half_kelly",
                name="Half-Kelly Sizing Criterion",
                category=MetricCategory.PORTFOLIO,
                summary="Sizes capital allocations to 50% of the mathematically optimal Kelly growth rate to drastically reduce drawdown volatility.",
                formula="f^* = 0.5 \\times \\frac{p b - q}{b} = 0.5 \\times \\frac{\\mu}{\\sigma^2}",
                interpretation="Provides ~75% of full Kelly logarithmic growth while slashing volatility and drawdown probability by 50%.",
                quant_usage="Governs maximum position sizing in the portfolio construction engine.",
                pitfalls="Full Kelly is notoriously prone to ruin from parameter estimation errors; half-Kelly provides necessary safety buffer.",
                ranges={"Conservative Allocation": "0.25 - 0.50 Kelly"},
                related_metrics=["volatility_targeting", "sharpe_ratio"],
            )
        )

        self.register(
            FinancialMetricExplanation(
                id="ledoit_wolf_covariance",
                name="Ledoit-Wolf Covariance Shrinkage",
                category=MetricCategory.PORTFOLIO,
                summary="Shrinks empirical sample covariance toward a structured target (constant correlation) to eliminate estimation noise.",
                formula="\\Sigma_{\\text{LW}} = \\delta F + (1 - \\delta) S",
                interpretation="Produces well-conditioned, invertible covariance matrices that prevent extreme and erratic portfolio weights.",
                quant_usage="Estimates the risk matrix for mean-variance and minimum-variance portfolio optimization.",
                pitfalls="Optimal shrinkage intensity (delta) depends on sample size relative to the number of assets.",
                ranges={"Shrinkage Intensity": "\\delta \\in [0, 1]"},
                related_metrics=["barra_neutralization"],
            )
        )

        self.register(
            FinancialMetricExplanation(
                id="volatility_targeting",
                name="Volatility Targeting",
                category=MetricCategory.PORTFOLIO,
                summary="Dynamically scales gross exposure up or down inversely with forecasted market volatility to maintain constant portfolio risk.",
                formula="\\text{Leverage}_t = \\frac{\\sigma_{\\text{target}}}{\\hat{\\sigma}_t}",
                interpretation="Reduces exposure during high-volatility turbulence and expands exposure during calm market regimes.",
                quant_usage="Controls portfolio gross leverage dynamically within the risk limits.",
                pitfalls="Lagging volatility estimates can cause the strategy to deleverage near market bottoms and releverage near tops.",
                ranges={"Target Volatility": "8% - 15% annualized"},
                related_metrics=["half_kelly", "max_drawdown"],
            )
        )

        # 5. EXECUTION & BROKER INTEGRITY METRICS
        self.register(
            FinancialMetricExplanation(
                id="nbbo",
                name="National Best Bid and Offer (NBBO)",
                category=MetricCategory.EXECUTION,
                summary="The consolidated best prevailing bid and ask prices across all registered securities exchanges.",
                formula="\\text{NBBO Spread} = \\text{Ask}_{\\text{best}} - \\text{Bid}_{\\text{best}}",
                interpretation="Narrow spreads indicate deep liquidity; wide spreads indicate illiquidity and high execution costs.",
                quant_usage="Pre-trade sanity barrier: rejects orders if limit price deviates > 5% from authoritative NBBO benchmark.",
                pitfalls="Quotes can change in microseconds; requires low-latency tick timestamps to prevent false staleness triggers.",
                ranges={"Liquid Mega-Cap Spread": "< $0.02", "Illiquid / Wide Spread": "> 0.50%"},
                related_metrics=["slippage", "working_orders"],
            )
        )

        self.register(
            FinancialMetricExplanation(
                id="slippage",
                name="Execution Slippage & Buffer",
                category=MetricCategory.EXECUTION,
                summary="The difference between the expected pre-trade price and the actual execution fill price obtained from the broker.",
                formula="\\text{Slippage} = \\frac{|P_{\\text{fill}} - P_{\\text{expected}}|}{P_{\\text{expected}}}",
                interpretation="Measures market impact and latency penalty during order routing.",
                quant_usage="Deterministic risk engine adds a 0.50% conservative slippage buffer to notional calculations to protect cash reserves.",
                pitfalls="Higher on illiquid securities, market-on-open/close, or during high-volatility news releases.",
                ranges={"Tight Institutional": "< 5 bps", "Normal Retail": "5 - 20 bps", "Adverse Fill": "> 50 bps"},
                related_metrics=["nbbo", "fills"],
            )
        )

        self.register(
            FinancialMetricExplanation(
                id="exposure_reservations",
                name="Exposure Reservations (In-Flight Orders)",
                category=MetricCategory.EXECUTION,
                summary="Locks cash and position capacity for active working and in-flight orders before broker confirmation to eliminate race conditions.",
                formula="\\text{AvailCash} = \\text{Cash} - \\sum \\text{Notional}_{\\text{buy, active}} \\times (1 + \\text{buf})",
                interpretation="Guarantees concurrent order intents cannot exceed cash balance or position risk limits.",
                quant_usage="Evaluated in pre-trade risk checks across all SUBMITTING, ACKNOWLEDGED, PARTIALLY_FILLED, and CANCEL_PENDING orders.",
                pitfalls="Failing to release reservations on cancellation or terminal rejection causes persistent false-positive cash rejections.",
                ranges={"Active State": "Submitting, Ack, Partial, CancelPending"},
                related_metrics=["idempotency", "reconciliation"],
            )
        )

        self.register(
            FinancialMetricExplanation(
                id="reconciliation",
                name="Continuous Broker Reconciliation & Discrepancies",
                category=MetricCategory.EXECUTION,
                summary="Continuous 30-second deterministic state diff between local OMS ledger and broker authoritative account truth.",
                formula="\\Delta = \\text{State}_{\\text{OMS}} \\ominus \\text{State}_{\\text{Broker}}",
                interpretation="CLEAN indicates 100% agreement. CRITICAL discrepancies (unknown broker orders, position mismatches) automatically freeze the engine.",
                quant_usage="Automated safety worker freezes submission if discrepancy detected or broker becomes unreachable > MaxAge.",
                pitfalls="Temporary transient mismatches during in-flight fills must be tolerated using bounded working order checks.",
                ranges={"Clean State": "0 Discrepancies", "Warning": "Minor Cash Mismatch", "Critical": "Position/Unknown Order Mismatch"},
                related_metrics=["exposure_reservations", "idempotency"],
            )
        )

        # 6. MACRO & CROSS-ASSET METRICS
        self.register(
            FinancialMetricExplanation(
                id="interest_rate_differential",
                name="Interest Rate Differential & Carry Yield",
                category=MetricCategory.MACRO,
                summary="The spread between central bank policy rates of base and quote currencies governing FX carry trades.",
                formula="\\text{Carry Yield} = r_{\\text{base}} - r_{\\text{quote}}",
                interpretation="Positive differential provides positive roll yield on long FX positions, but carries sudden carry-unwind crash risk.",
                quant_usage="Used in Forex polymorphic workstation to evaluate carry yield vs policy divergence.",
                pitfalls="High-carry currencies are vulnerable to sudden global risk-off liquidations (Carry Crash).",
                ranges={"High Carry": "> 3.0%", "Neutral Spread": "0.0% - 1.5%"},
                related_metrics=["real_yield_sensitivity"],
            )
        )

        self.register(
            FinancialMetricExplanation(
                id="gold_silver_ratio",
                name="Gold / Silver Ratio",
                category=MetricCategory.MACRO,
                summary="The number of ounces of silver required to purchase one ounce of gold, indicating macroeconomic risk sentiment and industrial demand.",
                formula="\\text{G/S Ratio} = \\frac{P_{\\text{Gold}}}{P_{\\text{Silver}}}",
                interpretation="High ratio (> 80) indicates extreme deflationary / flight-to-safety risk; low ratio (< 50) denotes robust industrial expansion.",
                quant_usage="Commodity polymorphic matrix indicator for precious metals valuation cycles.",
                pitfalls="Silver has significant industrial demand (solar, electronics) that gold lacks, causing divergence during green transition cycles.",
                ranges={"Silver Undervalued / Fear": "> 80", "Historical Mean": "60 - 75", "Industrial Boom / Risk-On": "< 50"},
                related_metrics=["inflation_beta"],
            )
        )


# Global singleton instance
_registry_instance: Optional[FinancialKnowledgeRegistry] = None


def global_registry() -> FinancialKnowledgeRegistry:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = FinancialKnowledgeRegistry()
    return _registry_instance
