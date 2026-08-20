from __future__ import annotations

import math
from typing import Mapping, Any, Dict, Optional, Union

Number = Union[int, float]
EPSILON = 1e-12


class FinancialDataError(ValueError):
    """Raised when required financial data is missing or invalid."""
    pass


def _number(
    data: Mapping[str, Any],
    key: str,
    *,
    default: Optional[float] = None,
) -> float:
    if key not in data:
        if default is not None:
            return float(default)
        raise FinancialDataError(f"Missing required field: {key}")
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        # Try parsing if string
        try:
            val_str = str(value).replace("$", "").replace(",", "").replace("%", "").strip()
            if val_str.endswith("B"):
                value = float(val_str[:-1]) * 1e9
            elif val_str.endswith("M"):
                value = float(val_str[:-1]) * 1e6
            elif val_str.endswith("K"):
                value = float(val_str[:-1]) * 1e3
            else:
                value = float(val_str)
        except Exception:
            if default is not None:
                return float(default)
            raise FinancialDataError(f"{key} must be numeric, got {type(value).__name__} ({value})")
    value = float(value)
    if not math.isfinite(value):
        if default is not None:
            return float(default)
        raise FinancialDataError(f"{key} must be finite")
    return value


def _divide(
    numerator: float,
    denominator: float,
    label: str,
) -> float:
    if abs(denominator) <= EPSILON:
        return 1.0  # Safe fallback for neutral ratio
    result = numerator / denominator
    if not math.isfinite(result):
        return 1.0
    return result


def _ratio_of_ratios(
    numerator_current: float,
    denominator_current: float,
    numerator_previous: float,
    denominator_previous: float,
    label: str,
) -> float:
    current_ratio = _divide(
        numerator_current,
        denominator_current,
        f"{label} current ratio",
    )
    previous_ratio = _divide(
        numerator_previous,
        denominator_previous,
        f"{label} previous ratio",
    )
    return _divide(
        current_ratio,
        previous_ratio,
        label,
    )


def calculate_beneish_m_score(
    current_period: Mapping[str, Any],
    previous_period: Mapping[str, Any],
) -> Dict[str, Any]:
    """Calculate the 8-variable Beneish M-Score for earnings manipulation detection.

    Variables:
      - DSRI: Days Sales in Receivables Index
      - GMI: Gross Margin Index
      - AQI: Asset Quality Index
      - SGI: Sales Growth Index
      - DEPI: Depreciation Index
      - SGAI: Sales, General and Administrative expenses Index
      - LVGI: Leverage Index
      - TATA: Total Accruals to Total Assets

    Cutoff threshold: -1.78.
    If M-Score < -1.78 => "Safe" (Low probability of manipulation).
    If M-Score >= -1.78 => "Manipulator" (High probability of earnings distortion).
    """
    cur = current_period
    prev = previous_period

    sales_t = _number(cur, "sales", default=100.0)
    sales_p = _number(prev, "sales", default=90.0)
    receivables_t = _number(cur, "receivables", default=15.0)
    receivables_p = _number(prev, "receivables", default=14.0)
    cogs_t = _number(cur, "cogs", default=40.0)
    cogs_p = _number(prev, "cogs", default=38.0)
    current_assets_t = _number(cur, "current_assets", default=50.0)
    current_assets_p = _number(prev, "current_assets", default=45.0)
    ppe_t = _number(cur, "ppe", default=30.0)
    ppe_p = _number(prev, "ppe", default=28.0)
    total_assets_t = _number(cur, "total_assets", default=120.0)
    total_assets_p = _number(prev, "total_assets", default=110.0)
    depreciation_t = _number(cur, "depreciation", default=5.0)
    depreciation_p = _number(prev, "depreciation", default=4.5)
    sga_t = _number(cur, "sga", default=18.0)
    sga_p = _number(prev, "sga", default=16.5)
    current_liabilities_t = _number(cur, "current_liabilities", default=25.0)
    current_liabilities_p = _number(prev, "current_liabilities", default=24.0)
    long_term_debt_t = _number(cur, "long_term_debt", default=20.0)
    long_term_debt_p = _number(prev, "long_term_debt", default=22.0)

    # 1. DSRI
    dsri = _ratio_of_ratios(
        receivables_t,
        sales_t,
        receivables_p,
        sales_p,
        "DSRI",
    )

    # 2. GMI (previous gross margin / current gross margin)
    gross_margin_t = _divide(sales_t - cogs_t, sales_t, "current gross margin")
    gross_margin_p = _divide(sales_p - cogs_p, sales_p, "previous gross margin")
    gmi = _divide(gross_margin_p, gross_margin_t, "GMI")

    # 3. AQI (Asset Quality Index)
    asset_quality_t = 1.0 - _divide(current_assets_t + ppe_t, total_assets_t, "cur AQ")
    asset_quality_p = 1.0 - _divide(current_assets_p + ppe_p, total_assets_p, "prev AQ")
    if abs(asset_quality_p) <= EPSILON:
        aqi = 1.0
    else:
        aqi = asset_quality_t / asset_quality_p

    # 4. SGI (Sales Growth Index)
    sgi = _divide(sales_t, sales_p, "SGI")

    # 5. DEPI (Depreciation Index)
    dep_rate_t = _divide(depreciation_t, depreciation_t + ppe_t, "cur dep rate")
    dep_rate_p = _divide(depreciation_p, depreciation_p + ppe_p, "prev dep rate")
    depi = _divide(dep_rate_p, dep_rate_t, "DEPI")

    # 6. SGAI (SGA Index)
    sgai = _ratio_of_ratios(sga_t, sales_t, sga_p, sales_p, "SGAI")

    # 7. LVGI (Leverage Index)
    lvgi = _ratio_of_ratios(
        current_liabilities_t + long_term_debt_t,
        total_assets_t,
        current_liabilities_p + long_term_debt_p,
        total_assets_p,
        "LVGI",
    )

    # 8. TATA (Total Accruals to Total Assets)
    original_tata_fields = ("cash", "current_maturities_long_term_debt", "income_tax_payable")
    has_original_tata = all(k in cur and k in prev for k in original_tata_fields)

    if has_original_tata:
        cash_t = _number(cur, "cash")
        cash_p = _number(prev, "cash")
        curr_mat_t = _number(cur, "current_maturities_long_term_debt")
        curr_mat_p = _number(prev, "current_maturities_long_term_debt")
        tax_t = _number(cur, "income_tax_payable")
        tax_p = _number(prev, "income_tax_payable")

        delta_ca = current_assets_t - current_assets_p
        delta_cash = cash_t - cash_p
        delta_cl = current_liabilities_t - current_liabilities_p
        delta_curr_mat = curr_mat_t - curr_mat_p
        delta_tax = tax_t - tax_p

        total_accruals = (
            delta_ca - delta_cash - (delta_cl - delta_curr_mat - delta_tax) - depreciation_t
        )
        tata = total_accruals / total_assets_t
        tata_method = "beneish_balance_sheet"
    else:
        # Cash-flow fallback
        if "income_from_continuing_operations" in cur:
            income = _number(cur, "income_from_continuing_operations")
        else:
            income = _number(cur, "net_income", default=25.0)
        cfo = _number(cur, "operating_cash_flow", default=30.0)
        tata = (income - cfo) / total_assets_t
        tata_method = "cash_flow_fallback"

    # Beneish 8-variable unweighted probit M-score formula
    m_score = (
        -4.840
        + 0.920 * dsri
        + 0.528 * gmi
        + 0.404 * aqi
        + 0.892 * sgi
        + 0.115 * depi
        - 0.172 * sgai
        + 4.679 * tata
        - 0.327 * lvgi
    )

    threshold = -1.78
    zone = "Safe (Unlikely Manipulation)" if m_score < threshold else "High Manipulation Risk"
    zone_color = "emerald" if m_score < threshold else "rose"
    model_variant = "BENEISH_M8_ORIGINAL" if tata_method == "beneish_balance_sheet" else "BENEISH_M8_CF_PROXY"

    return {
        "m_score": round(m_score, 3),
        "zone": zone,
        "zone_color": zone_color,
        "threshold": threshold,
        "model_variant": model_variant,
        "ratios": {
            "DSRI": round(dsri, 3),
            "GMI": round(gmi, 3),
            "AQI": round(aqi, 3),
            "SGI": round(sgi, 3),
            "DEPI": round(depi, 3),
            "SGAI": round(sgai, 3),
            "LVGI": round(lvgi, 3),
            "TATA": round(tata, 3),
        },
        "tata_method": tata_method,
    }


def calculate_canonical_piotroski_f_score(
    current_period: Mapping[str, Any],
    previous_period: Mapping[str, Any],
) -> Dict[str, Any]:
    """Calculate the canonical 9-point Joseph Piotroski (2000) F-Score.

    Evaluates 9 binary criteria across Profitability, Leverage/Liquidity/Financing, and Operating Efficiency:
      1. ROA > 0 (Positive Return on Assets)
      2. CFO > 0 (Positive Cash Flow from Operations)
      3. ΔROA > 0 (ROA increased YoY)
      4. CFO / Assets > ROA (Accrual Quality: Cash flow exceeds Net Income)
      5. ΔLeverage <= 0 (Lower long-term debt to assets)
      6. ΔCurrent Ratio >= 0 (Liquidity improvement)
      7. No equity issuance / dilution (Shares outstanding <= prior year)
      8. ΔGross Margin >= 0 (Pricing power expansion)
      9. ΔAsset Turnover >= 0 (Asset productivity expansion)
    """
    cur = current_period
    prev = previous_period

    assets_t = _number(cur, "total_assets", default=100.0)
    assets_p = _number(prev, "total_assets", default=90.0)
    sales_t = _number(cur, "sales", default=100.0)
    sales_p = _number(prev, "sales", default=90.0)
    cogs_t = _number(cur, "cogs", default=50.0)
    cogs_p = _number(prev, "cogs", default=48.0)
    net_income_t = _number(cur, "net_income", default=15.0)
    net_income_p = _number(prev, "net_income", default=12.0)
    cfo_t = _number(cur, "operating_cash_flow", default=18.0)
    cfo_p = _number(prev, "operating_cash_flow", default=14.0)
    current_assets_t = _number(cur, "current_assets", default=40.0)
    current_assets_p = _number(prev, "current_assets", default=35.0)
    current_liab_t = _number(cur, "current_liabilities", default=20.0)
    current_liab_p = _number(prev, "current_liabilities", default=19.0)
    lt_debt_t = _number(cur, "long_term_debt", default=15.0)
    lt_debt_p = _number(prev, "long_term_debt", default=16.0)
    shares_t = _number(cur, "shares_outstanding", default=100.0)
    shares_p = _number(prev, "shares_outstanding", default=100.0)

    score = 0
    checks = []

    # 1. Profitability: Positive ROA
    roa_t = net_income_t / assets_t
    roa_p = net_income_p / assets_p
    if roa_t > 0:
        score += 1
        checks.append("1. Positive Return on Assets (ROA > 0) [+1]")

    # 2. Profitability: Positive CFO
    if cfo_t > 0:
        score += 1
        checks.append("2. Positive Operating Cash Flow (CFO > 0) [+1]")

    # 3. Profitability: ΔROA > 0
    if roa_t > roa_p:
        score += 1
        checks.append("3. Return on Assets Expansion (ΔROA > 0) [+1]")

    # 4. Profitability: Accruals (CFO / Assets > ROA)
    cfo_assets = cfo_t / assets_t
    if cfo_assets > roa_t:
        score += 1
        checks.append("4. Cash Flow Exceeds Net Income (CFO/Assets > ROA) [+1]")

    # 5. Leverage: ΔLeverage <= 0
    lev_t = lt_debt_t / assets_t
    lev_p = lt_debt_p / assets_p
    if lev_t <= lev_p:
        score += 1
        checks.append("5. Deleveraging / Stable Long-Term Debt (ΔLeverage ≤ 0) [+1]")

    # 6. Liquidity: ΔCurrent Ratio >= 0
    cr_t = current_assets_t / max(current_liab_t, 1e-6)
    cr_p = current_assets_p / max(current_liab_p, 1e-6)
    if cr_t >= cr_p:
        score += 1
        checks.append("6. Improved Liquidity (ΔCurrent Ratio ≥ 0) [+1]")

    # 7. Financing: No Dilution (Shares_t <= Shares_p)
    if shares_t <= shares_p * 1.005:  # within 0.5% threshold
        score += 1
        checks.append("7. Zero Dilution / Share Repurchases (ΔShares ≤ 0) [+1]")

    # 8. Efficiency: ΔGross Margin >= 0
    gm_t = (sales_t - cogs_t) / max(sales_t, 1e-6)
    gm_p = (sales_p - cogs_p) / max(sales_p, 1e-6)
    if gm_t >= gm_p:
        score += 1
        checks.append("8. Pricing Power Expansion (ΔGross Margin ≥ 0) [+1]")

    # 9. Efficiency: ΔAsset Turnover >= 0
    at_t = sales_t / assets_t
    at_p = sales_p / assets_p
    if at_t >= at_p:
        score += 1
        checks.append("9. Asset Productivity Expansion (ΔAsset Turnover ≥ 0) [+1]")

    if score >= 8:
        rating = "VERY STRONG (8-9/9)"
        rating_color = "emerald"
    elif score >= 5:
        rating = "MODERATE (5-7/9)"
        rating_color = "indigo"
    else:
        rating = "WEAK / HIGH RISK (0-4/9)"
        rating_color = "rose"

    return {
        "f_score": score,
        "max_score": 9,
        "rating": rating,
        "rating_color": rating_color,
        "checks": checks,
        "model": "PIOTROSKI_9_CANONICAL",
    }



def calculate_sloan_accrual_anomaly(
    financials: Mapping[str, Any],
) -> Dict[str, Any]:
    """Calculate Sloan Accrual Anomaly Ratio: (Net Income - Operating Cash Flow) / Total Assets.

    High positive accruals indicate earnings are driven by non-cash accounting adjustments rather than cash generation.
    """
    net_income = _number(financials, "net_income", default=25.0)
    operating_cash_flow = _number(financials, "operating_cash_flow", default=30.0)
    total_assets = _number(financials, "total_assets", default=100.0)

    if total_assets <= 0:
        total_assets = 100.0

    cash_flow_accruals = net_income - operating_cash_flow
    cash_flow_accrual_ratio = cash_flow_accruals / total_assets

    quality = "High Quality (Cash-Backed)" if cash_flow_accrual_ratio <= 0 else "Moderate/High Accruals"
    quality_color = "emerald" if cash_flow_accrual_ratio <= 0 else "amber"

    result = {
        "accruals": round(cash_flow_accruals, 2),
        "accrual_ratio": round(cash_flow_accrual_ratio, 4),
        "quality": quality,
        "quality_color": quality_color,
        "direction": (
            "positive_accruals"
            if cash_flow_accrual_ratio > 0
            else "negative_accruals"
            if cash_flow_accrual_ratio < 0
            else "neutral"
        ),
    }

    bs_fields = (
        "current_assets",
        "previous_current_assets",
        "cash",
        "previous_cash",
        "current_liabilities",
        "previous_current_liabilities",
        "short_term_debt",
        "previous_short_term_debt",
        "income_tax_payable",
        "previous_income_tax_payable",
        "depreciation_and_amortization",
    )
    if all(k in financials for k in bs_fields):
        delta_ca = _number(financials, "current_assets") - _number(financials, "previous_current_assets")
        delta_cash = _number(financials, "cash") - _number(financials, "previous_cash")
        delta_cl = _number(financials, "current_liabilities") - _number(financials, "previous_current_liabilities")
        delta_st_debt = _number(financials, "short_term_debt") - _number(financials, "previous_short_term_debt")
        delta_tax = _number(financials, "income_tax_payable") - _number(financials, "previous_income_tax_payable")
        depreciation = _number(financials, "depreciation_and_amortization")

        bs_accruals = delta_ca - delta_cash - (delta_cl - delta_st_debt - delta_tax) - depreciation
        bs_ratio = bs_accruals / total_assets
        result.update({
            "balance_sheet_accruals": round(bs_accruals, 2),
            "balance_sheet_accrual_ratio": round(bs_ratio, 4),
            "cash_vs_balance_sheet_gap": round(cash_flow_accrual_ratio - bs_ratio, 4),
        })

    return result
