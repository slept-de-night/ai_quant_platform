from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import requests

from .models import Direction, FundamentalSnapshot, FundamentalView


class SECCompanyFactsClient:
    """Minimal point-in-time SEC XBRL adapter for US issuers."""

    def __init__(self, user_agent: str, timeout: int = 20):
        if not user_agent or "@" not in user_agent:
            raise ValueError("SEC_USER_AGENT should identify the application and include a contact email")
        self.headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
        self.timeout = timeout

    def _json(self, url: str) -> Any:
        r = requests.get(url, headers=self.headers, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def ticker_to_cik(self, symbol: str) -> Tuple[int, Optional[str]]:
        data = self._json("https://www.sec.gov/files/company_tickers.json")
        symbol = symbol.upper()
        for row in data.values():
            if str(row.get("ticker", "")).upper() == symbol:
                return int(row["cik_str"]), row.get("title")
        raise KeyError(f"Ticker {symbol} not found in SEC ticker mapping")

    def company_facts(self, cik: int) -> Dict[str, Any]:
        return self._json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json")

    @staticmethod
    def _annual_values(facts: dict, tags: List[str], units: List[str]) -> List[Tuple[int, str, float]]:
        usgaap = facts.get("facts", {}).get("us-gaap", {})
        rows: List[Tuple[int, str, float]] = []
        for tag in tags:
            node = usgaap.get(tag)
            if not node:
                continue
            for unit in units:
                for x in node.get("units", {}).get(unit, []):
                    if x.get("form") not in {"10-K", "20-F", "40-F"}:
                        continue
                    fy = x.get("fy")
                    end = x.get("end")
                    val = x.get("val")
                    if fy is None or end is None or val is None:
                        continue
                    fp = x.get("fp")
                    if fp not in {"FY", None}:
                        continue
                    try:
                        rows.append((int(fy), str(end), float(val)))
                    except Exception:
                        pass
            if rows:
                break
        best: Dict[int, Tuple[int, str, float]] = {}
        for row in rows:
            if row[0] not in best or row[1] > best[row[0]][1]:
                best[row[0]] = row
        return sorted(best.values(), key=lambda z: (z[0], z[1]))

    def snapshot(self, symbol: str) -> FundamentalSnapshot:
        cik, name = self.ticker_to_cik(symbol)
        facts = self.company_facts(cik)

        def vals(tags, units=("USD",)):
            return self._annual_values(facts, tags, list(units))

        revenue = vals(["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"])
        opinc = vals(["OperatingIncomeLoss"])
        net = vals(["NetIncomeLoss", "ProfitLoss"])
        assets = vals(["Assets"])
        liab = vals(["Liabilities"])
        equity = vals(
            ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]
        )
        debt = vals(
            [
                "LongTermDebtAndFinanceLeaseObligations",
                "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
                "LongTermDebtNoncurrent",
                "LongTermDebt",
            ]
        )
        eps = vals(["EarningsPerShareDiluted"], units=("USD/shares",))

        latest_fy = max([v[-1][0] for v in [revenue, opinc, net, assets, liab, equity, debt, eps] if v], default=None)

        def latest(series):
            return series[-1][2] if series else None

        def growth(series):
            if len(series) < 2 or series[-2][2] == 0:
                return None
            return series[-1][2] / series[-2][2] - 1

        rev = latest(revenue)
        ni = latest(net)
        oi = latest(opinc)
        eq = latest(equity)
        db = latest(debt)

        return FundamentalSnapshot(
            symbol=symbol.upper(),
            company_name=name,
            fiscal_year=latest_fy,
            revenue=rev,
            revenue_growth=growth(revenue),
            operating_income=oi,
            operating_margin=(oi / rev if oi is not None and rev else None),
            net_income=ni,
            net_margin=(ni / rev if ni is not None and rev else None),
            assets=latest(assets),
            asset_growth=growth(assets),
            liabilities=latest(liab),
            equity=eq,
            debt=db,
            debt_to_equity=(db / eq if db is not None and eq not in {None, 0} else None),
            eps_diluted=latest(eps),
            source_url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json",
        )


def _direction(score: float) -> Direction:
    if score >= 0.55:
        return Direction.STRONG_BULLISH
    if score >= 0.15:
        return Direction.BULLISH
    if score <= -0.55:
        return Direction.STRONG_BEARISH
    if score <= -0.15:
        return Direction.BEARISH
    return Direction.NEUTRAL


def analyze_fundamental(s: Optional[FundamentalSnapshot]) -> FundamentalView:
    """Analyze fundamental corporate health and balance sheet metrics."""
    if s is None:
        return FundamentalView(
            score=0,
            confidence=0,
            direction=Direction.UNKNOWN,
            quality="unavailable",
            growth="unavailable",
            balance_sheet="unavailable",
            profitability="unavailable",
            valuation_note="No point-in-time valuation dataset is configured; the system will not invent one.",
            observations=[],
        )

    components: List[float] = []
    obs: List[str] = []

    if s.revenue_growth is not None:
        components.append(max(-1, min(1, s.revenue_growth / 0.20)))
        obs.append(f"revenue growth: {s.revenue_growth:+.1%}")
    if s.operating_margin is not None:
        components.append(max(-1, min(1, (s.operating_margin - 0.08) / 0.20)))
        obs.append(f"operating margin: {s.operating_margin:.1%}")
    if s.net_margin is not None:
        components.append(max(-1, min(1, (s.net_margin - 0.05) / 0.20)))
        obs.append(f"net margin: {s.net_margin:.1%}")
    if s.debt_to_equity is not None:
        components.append(max(-1, min(1, 0.5 - s.debt_to_equity / 2)))
        obs.append(f"debt/equity: {s.debt_to_equity:.2f}")
    if s.asset_growth is not None:
        components.append(max(-1, min(1, s.asset_growth / 0.25)) * 0.4)
        obs.append(f"asset growth: {s.asset_growth:+.1%}")

    score = sum(components) / len(components) if components else 0.0
    conf = min(0.90, 0.18 * len(components))
    growth = (
        "positive"
        if (s.revenue_growth or 0) > 0.03
        else "contracting"
        if (s.revenue_growth or 0) < -0.03
        else "flat/mixed"
    )
    profit = (
        "strong"
        if (s.net_margin or 0) > 0.15
        else "positive"
        if (s.net_margin or 0) > 0
        else "weak/negative"
    )
    bs = (
        "conservative"
        if s.debt_to_equity is not None and s.debt_to_equity < 0.5
        else "leveraged"
        if s.debt_to_equity is not None and s.debt_to_equity > 1.5
        else "moderate/unknown"
    )
    quality = "strong" if score > 0.45 else "weak" if score < -0.25 else "mixed"

    return FundamentalView(
        score=max(-1, min(1, score)),
        confidence=conf,
        direction=_direction(score),
        quality=quality,
        growth=growth,
        balance_sheet=bs,
        profitability=profit,
        valuation_note="SEC Company Facts provides accounting fundamentals, not a complete valuation model.",
        observations=obs,
        snapshot=s,
    )
