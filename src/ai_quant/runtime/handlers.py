from __future__ import annotations

import json
from typing import Any, Callable, Dict, List

from ..core.config import Settings
from ..intelligence.evidence import verify_evidence
from ..intelligence.fundamentals import SECCompanyFactsClient, analyze_fundamental
from ..intelligence.models import ConflictBatch
from ..intelligence.technical import analyze_technical
from ..intelligence.trends import FREDClient, analyze_megatrend, analyze_microtrend
from ..intelligence.web_research import OpenAIWebResearcher
from .gate import AIExecutionGate, ExecutionDecision, ExecutionKind, GateRequest
from .models import RuntimeTask
from .router import ModelRouter, RouteRequest
from .snapshot import ResearchSnapshot


class ResearchRuntimeHandlers:
    """Executable handlers for the quantitative multi-agent research DAG."""

    def __init__(
        self,
        cfg: Settings,
        data_loader: Callable[[str, int], Any],
        execute_ai: bool = False,
        router: Optional[ModelRouter] = None,
        gate: Optional[AIExecutionGate] = None,
        snapshot: Optional[ResearchSnapshot] = None,
    ):
        self.cfg = cfg
        self.data_loader = data_loader
        self.execute_ai = execute_ai
        self.router = router or ModelRouter(cfg)
        self.gate = gate or AIExecutionGate(cfg, self.router)
        self.snapshot = snapshot

    def handlers(self) -> Dict[str, Callable[[RuntimeTask, Dict[str, Dict[str, Any]]], Dict[str, Any]]]:
        return {
            "extract": self.extract,
            "fundamental_review": self.fundamental,
            "trend_review": self.trend,
            "web_research": self.web_research,
            "contradiction": self.contradiction,
            "scenario_synthesis": self.scenario,
            "falsification": self.falsification,
            "critical_review": self.audit,
            "research_digest": self.digest,
            "research_program": self.digest,
        }

    @staticmethod
    def _clean_deps(deps: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [v for _, v in sorted(deps.items())]

    def _get_bars(self, symbol: str, limit: int = 1000) -> Any:
        if self.snapshot is not None:
            cached = self.snapshot.get_bars(symbol)
            if cached is not None:
                return cached
        return self.data_loader(symbol, limit)

    def extract(self, task: RuntimeTask, deps: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        bars = self._get_bars(task.symbol or "SPY", 1000)
        view = analyze_technical(bars)
        return {"agent": task.agent_role, "kind": "technical", "view": view.model_dump(mode="json")}

    def fundamental(self, task: RuntimeTask, deps: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        if not self.cfg.sec_user_agent or not task.symbol:
            view = analyze_fundamental(None)
        else:
            try:
                if self.snapshot and self.snapshot.sec_snapshot and (self.snapshot.symbol.upper() == task.symbol.upper()):
                    snap = self.snapshot.sec_snapshot
                else:
                    snap = SECCompanyFactsClient(self.cfg.sec_user_agent).snapshot(task.symbol)
                view = analyze_fundamental(snap)
            except Exception as exc:
                view = analyze_fundamental(None)
                view.observations.append(f"SEC unavailable: {type(exc).__name__}: {exc}")
        return {"agent": task.agent_role, "kind": "fundamental", "view": view.model_dump(mode="json")}

    def trend(self, task: RuntimeTask, deps: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        symbol_bars = self._get_bars(task.symbol or "SPY", 1000)
        market = self._get_bars("SPY", 1000)
        if task.agent_role == "microtrend_agent":
            view = analyze_microtrend(symbol_bars, None, market)
            return {"agent": task.agent_role, "kind": "microtrend", "view": view.model_dump(mode="json")}
        growth = self._get_bars("QQQ", 1000)
        bond = self._get_bars("TLT", 1000)
        gold = self._get_bars("GLD", 1000)
        macro = None
        if self.snapshot and self.snapshot.macro_snapshot:
            macro = self.snapshot.macro_snapshot
        elif self.cfg.fred_api_key:
            try:
                macro = FREDClient(self.cfg.fred_api_key).snapshot()
            except Exception:
                macro = None
        view = analyze_megatrend(market, growth, bond, gold, macro)
        return {"agent": task.agent_role, "kind": "megatrend", "view": view.model_dump(mode="json")}

    def web_research(self, task: RuntimeTask, deps: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        if task.agent_role == "evidence_manager":
            return self.digest(task, deps)

        force_refresh = bool(task.payload.get("force_refresh", False))
        gate_req = GateRequest(
            task_type="web_research",
            symbol=task.symbol,
            agent_role=task.agent_role,
            objective=task.objective,
            complexity=0.68,
            criticality=0.78,
            ambiguity=0.70,
            financial_impact=0.55,
            needs_web=True,
            needs_tools=True,
            run_id=task.root_id,
            force_refresh=force_refresh,
        )
        decision = self.gate.evaluate(gate_req)

        if not self.execute_ai or not self.cfg.openai_api_key or not task.symbol or decision.kind != ExecutionKind.AI:
            return {
                "agent": task.agent_role,
                "kind": "evidence",
                "summary": f"AI web research not executed in this runtime run ({decision.reason}).",
                "evidence": {"overall_trust": 0.0, "verified_claim_ratio": 0.0, "claims": []},
                "skipped": True,
                "execution_decision": decision.model_dump(mode="json"),
            }

        route = decision.model_route or self.router.decide(
            RouteRequest(
                task_type="web_research",
                complexity=0.68,
                criticality=0.78,
                ambiguity=0.70,
                financial_impact=0.55,
                needs_web=True,
                needs_tools=True,
                run_id=task.root_id,
            )
        )
        primary = {x.strip().lower() for x in self.cfg.extra_primary_domains.split(",") if x.strip()}
        trusted = {x.strip().lower() for x in self.cfg.extra_trusted_domains.split(",") if x.strip()}
        researcher = OpenAIWebResearcher(
            self.cfg.openai_api_key, route.model, route.reasoning_effort, primary, trusted
        )
        summary, items = researcher.research(task.symbol)
        report = verify_evidence(items)
        return {
            "agent": task.agent_role,
            "kind": "evidence",
            "summary": summary,
            "route": route.model_dump(mode="json"),
            "execution_decision": decision.model_dump(mode="json"),
            "evidence": report.model_dump(mode="json"),
            "skipped": False,
        }

    def contradiction(self, task: RuntimeTask, deps: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        evidence_outputs = self._clean_deps(deps)
        claims = []
        for out in evidence_outputs:
            report = out.get("evidence", {})
            for claim in report.get("claims", []):
                claims.append({"claim": claim.get("claim"), "verdict": claim.get("verdict")})

        force_refresh = bool(task.payload.get("force_refresh", False))
        gate_req = GateRequest(
            task_type="contradiction",
            symbol=task.symbol,
            agent_role=task.agent_role,
            objective=task.objective,
            claims_count=len(claims),
            complexity=0.55,
            criticality=0.82,
            ambiguity=0.60,
            financial_impact=0.55,
            run_id=task.root_id,
            force_refresh=force_refresh,
        )
        decision = self.gate.evaluate(gate_req)

        if decision.kind != ExecutionKind.AI or not self.execute_ai or not self.cfg.openai_api_key:
            return {
                "agent": task.agent_role,
                "kind": "contradiction",
                "conflicts": [],
                "note": f"AI contradiction pass skipped ({decision.reason})",
                "execution_decision": decision.model_dump(mode="json"),
            }

        response, route = self.router.parse(
            RouteRequest(
                task_type="contradiction",
                complexity=0.55,
                criticality=0.82,
                ambiguity=0.60,
                financial_impact=0.55,
                run_id=task.root_id,
            ),
            input=[
                {
                    "role": "system",
                    "content": "Find only direct material contradictions in sanitized financial claims. Do not invent facts.",
                },
                {"role": "user", "content": json.dumps(claims)},
            ],
            text_format=ConflictBatch,
        )
        batch = response.output_parsed
        return {
            "agent": task.agent_role,
            "kind": "contradiction",
            "route": route.model_dump(mode="json"),
            "execution_decision": decision.model_dump(mode="json"),
            "conflicts": batch.model_dump(mode="json")["conflicts"] if batch else [],
        }

    def scenario(self, task: RuntimeTask, deps: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        inputs = self._clean_deps(deps)
        if task.agent_role == "future_agent":
            return {
                "agent": task.agent_role,
                "kind": "future_scenarios",
                "scenarios": [
                    {
                        "name": "base",
                        "thesis": "Current verified conditions broadly persist.",
                        "invalidators": ["material trend or evidence regime change"],
                    },
                    {
                        "name": "upside",
                        "thesis": "Company/industry and macro conditions improve together.",
                        "invalidators": ["growth or leadership fails to confirm"],
                    },
                    {
                        "name": "downside",
                        "thesis": "Company, industry, or macro conditions deteriorate materially.",
                        "invalidators": ["fundamentals and relative strength re-accelerate"],
                    },
                ],
                "inputs_seen": len(inputs),
            }
        return {"agent": task.agent_role, "kind": "thesis_digest", "components": inputs}

    def falsification(self, task: RuntimeTask, deps: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "agent": task.agent_role,
            "kind": "falsification",
            "tests": [
                "relative leadership reverses on 60/120-day horizons",
                "fundamental growth/profitability deteriorates",
                "verified evidence contradicts the central narrative",
                "macro regime changes materially",
            ],
            "inputs_seen": len(deps),
        }

    def audit(self, task: RuntimeTask, deps: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        items = self._clean_deps(deps)
        skipped = 0
        warnings = []
        for item in items:
            if item.get("skipped"):
                skipped += 1
            if "error" in item:
                warnings.append(str(item["error"]))
        return {
            "agent": task.agent_role,
            "kind": "audit",
            "dependency_count": len(items),
            "skipped_components": skipped,
            "warnings": warnings,
            "passed_structure": len(items) > 0 and not warnings,
        }

    def digest(self, task: RuntimeTask, deps: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        items = self._clean_deps(deps)
        return {
            "agent": task.agent_role,
            "kind": "digest",
            "objective": task.objective,
            "dependency_count": len(items),
            "components": items,
        }
