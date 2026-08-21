"""
Contextual Metric Explainer with asset-class awareness and quant decision impact.
"""

from typing import Any, Dict, List, Optional
from src.ai_quant.knowledge.models import FinancialMetricExplanation, MetricCategory
from src.ai_quant.knowledge.registry import global_registry


class ContextualExplainer:
    """
    Generates tailored, asset-class aware explanations for financial and quantitative metrics.
    """

    def __init__(self):
        self.registry = global_registry()

    def explain(
        self,
        metric_id: str,
        value: Optional[Any] = None,
        symbol: str = "AAPL",
        asset_type: str = "EQUITY",
        sector: Optional[str] = None,
        percentile: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Generate contextual explanation for a metric and asset combination.
        """
        base = self.registry.get(metric_id)
        if not base:
            return {
                "metric_id": metric_id,
                "error": f"Metric '{metric_id}' not found in Financial Knowledge Registry",
                "is_applicable": False,
            }

        norm_asset = asset_type.upper().strip()

        # 1. Cross-Asset Inapplicability Check
        inapplicable_reasons = self._check_asset_applicability(base, norm_asset, symbol)
        if inapplicable_reasons:
            return {
                "metric_id": base.id,
                "name": base.name,
                "category": base.category.value,
                "summary": base.summary,
                "is_applicable": False,
                "inapplicable_reason": inapplicable_reasons["reason"],
                "recommended_alternative": inapplicable_reasons["alternative"],
            }

        # 2. Contextual value analysis for applicable assets
        value_assessment = self._assess_value(base, value, symbol, sector, percentile)

        return {
            "metric_id": base.id,
            "name": base.name,
            "category": base.category.value,
            "summary": base.summary,
            "formula": base.formula,
            "is_applicable": True,
            "current_value": value,
            "assessment": value_assessment["assessment"],
            "zone": value_assessment.get("zone", "Normal"),
            "quant_impact": value_assessment["quant_impact"],
            "pitfalls": base.pitfalls,
            "related_metrics": base.related_metrics,
        }

    def _check_asset_applicability(
        self, base: FinancialMetricExplanation, asset_type: str, symbol: str
    ) -> Optional[Dict[str, str]]:
        if asset_type in ("CRYPTO", "COMMODITY", "FOREX", "ETF"):
            if base.category in (MetricCategory.VALUATION, MetricCategory.FORENSIC):
                alternatives = {
                    "CRYPTO": "Review Tokenomics, 24/7 Realized Volatility, Circulating Supply, and ATH Drawdown.",
                    "COMMODITY": "Review Futures Term Structure, Roll Yield, Gold/Silver Ratio, and Real Yield Beta.",
                    "FOREX": "Review Central Bank Policy Rates, Interest Rate Differential, and Annualized Carry Yield.",
                    "ETF": "Review Fund AUM, Expense Ratio, Tracking Error, Top 25 Holdings, and Sector Weights.",
                }
                return {
                    "reason": f"{base.name} is a corporate accounting metric and is NOT applicable to {asset_type} ({symbol}). Non-equity assets do not report SEC 10-K filings, balance sheets, or GAAP earnings.",
                    "alternative": alternatives.get(asset_type, "Use asset-specific quantitative indicators."),
                }
        return None

    def _assess_value(
        self,
        base: FinancialMetricExplanation,
        value: Any,
        symbol: str,
        sector: Optional[str],
        percentile: Optional[float],
    ) -> Dict[str, str]:
        val_float = None
        try:
            if value is not None:
                val_float = float(value)
        except (ValueError, TypeError):
            pass

        # Specific metric assessments
        if base.id == "altman_z_score" and val_float is not None:
            if val_float < 1.81:
                return {
                    "zone": "Distress Zone",
                    "assessment": f"{symbol} Z-Score of {val_float:.2f} is in the Distress Zone (< 1.81), indicating elevated credit risk and bankruptcy vulnerability over a 2-year horizon.",
                    "quant_impact": "Disqualified from long portfolio allocation by forensic risk gate.",
                }
            elif val_float > 2.99:
                return {
                    "zone": "Safe Zone",
                    "assessment": f"{symbol} Z-Score of {val_float:.2f} indicates robust balance sheet solvency and low default risk.",
                    "quant_impact": "Passes forensic solvency hurdle with full sizing eligibility.",
                }
            else:
                return {
                    "zone": "Grey Zone",
                    "assessment": f"{symbol} Z-Score of {val_float:.2f} is in the Grey Zone (1.81 - 2.99). Financial condition is stable but requires monitoring.",
                    "quant_impact": "Allowed with standard position limits; secondary quality filters enforced.",
                }

        if base.id == "piotroski_f_score" and val_float is not None:
            if val_float >= 7:
                return {
                    "zone": "Strong Momentum",
                    "assessment": f"{symbol} F-Score of {int(val_float)}/9 denotes high operational improvement across profitability, leverage, and asset turnover.",
                    "quant_impact": "High quality boost applied in composite alpha scoring.",
                }
            elif val_float <= 3:
                return {
                    "zone": "Weak / Deteriorating",
                    "assessment": f"{symbol} F-Score of {int(val_float)}/9 indicates deteriorating fundamentals across multiple operational dimensions.",
                    "quant_impact": "Vetoed from long value baskets to avoid value traps.",
                }

        if base.id == "beneish_m_score" and val_float is not None:
            if val_float > -1.78:
                return {
                    "zone": "Manipulation Likely",
                    "assessment": f"{symbol} Beneish M-Score of {val_float:.2f} > -1.78 indicates significant probability of earnings distortion or aggressive revenue recognition.",
                    "quant_impact": "Immediate hard veto: disqualified from execution and capital sizing.",
                }
            else:
                return {
                    "zone": "Clean / Non-Manipulator",
                    "assessment": f"{symbol} M-Score of {val_float:.2f} is below the -1.78 manipulation threshold, indicating clean financial reporting.",
                    "quant_impact": "Forensic integrity check cleared.",
                }

        # Default assessment
        context_str = f"Current value for {symbol}: {value}"
        if percentile is not None:
            context_str += f" ({percentile:.0f}th percentile historically)"
        if sector:
            context_str += f" within sector {sector}"

        return {
            "zone": "Normal",
            "assessment": context_str,
            "quant_impact": f"Evaluated according to {base.category.value} rules in strategy validation.",
        }
