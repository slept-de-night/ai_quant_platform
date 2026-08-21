from __future__ import annotations

import logging
from typing import Any, Dict, Optional
import requests

from ..core.config import settings
from ..core.models import OrderIntent

logger = logging.getLogger(__name__)


class GoEngineClient:
    """High-speed HTTP client interfacing Python with the Go Execution Core."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.go_engine_url).rstrip("/")
        self.session = requests.Session()
        self.timeout = 2.5

    def is_available(self) -> bool:
        if not settings.enable_go_engine:
            return False
        try:
            r = self.session.get(f"{self.base_url}/health", timeout=1.0)
            return r.status_code == 200
        except Exception:
            return False

    def health(self) -> Optional[Dict[str, Any]]:
        try:
            r = self.session.get(f"{self.base_url}/health", timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.debug(f"Go engine health check failed: {e}")
        return None

    def get_portfolio(self, symbol: str = "SPY") -> Optional[Dict[str, Any]]:
        try:
            r = self.session.get(f"{self.base_url}/api/v1/portfolio?symbol={symbol}", timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.debug(f"Go engine get_portfolio failed: {e}")
        return None

    def check_risk(self, order: OrderIntent) -> Optional[Dict[str, Any]]:
        try:
            payload = order.model_dump(mode="json")
            r = self.session.post(f"{self.base_url}/api/v1/risk/check", json=payload, timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.debug(f"Go engine check_risk failed: {e}")
        return None

    def submit_order(self, order: OrderIntent) -> Optional[Dict[str, Any]]:
        try:
            payload = order.model_dump(mode="json")
            r = self.session.post(f"{self.base_url}/api/v1/orders/submit", json=payload, timeout=self.timeout)
            if r.status_code in (200, 400, 500):
                return r.json()
        except Exception as e:
            logger.debug(f"Go engine submit_order failed: {e}")
        return None

    def get_market_tick(self, symbol: str = "SPY") -> Optional[Dict[str, Any]]:
        try:
            r = self.session.get(f"{self.base_url}/api/v1/market/tick?symbol={symbol}", timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.debug(f"Go engine get_market_tick failed: {e}")
        return None

    def get_readiness(self) -> Optional[Dict[str, Any]]:
        """Query detailed operational readiness and execution safety report."""
        try:
            r = self.session.get(f"{self.base_url}/api/v1/readiness", timeout=self.timeout)
            if r.status_code in (200, 503):
                return r.json()
        except Exception as e:
            logger.debug(f"Go engine get_readiness failed: {e}")
        return None

    def freeze(self, reason: str = "Emergency Kill Switch ENGAGED by operator", requested_by: str = "operator") -> Optional[Dict[str, Any]]:
        """Engage firm-wide emergency kill switch with audit metadata."""
        try:
            payload = {"reason": reason, "requested_by": requested_by}
            r = self.session.post(f"{self.base_url}/api/v1/risk/kill", json=payload, timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.debug(f"Go engine freeze failed: {e}")
        return None

    def unfreeze(self, reason: str = "manual unfreeze", requested_by: str = "operator", reconciliation_run_id: str = "") -> Optional[Dict[str, Any]]:
        """Disengage emergency kill switch with audit justification and safety validation."""
        try:
            payload = {
                "reason": reason,
                "requested_by": requested_by,
                "reconciliation_run_id": reconciliation_run_id,
            }
            r = self.session.post(f"{self.base_url}/api/v1/risk/unfreeze", json=payload, timeout=self.timeout)
            if r.status_code in (200, 409):
                return r.json()
        except Exception as e:
            logger.debug(f"Go engine unfreeze failed: {e}")
        return None

    def get_order_history(self) -> Optional[Dict[str, Any]]:
        """Retrieve event-sourced order history from the Go OMS."""
        try:
            r = self.session.get(f"{self.base_url}/api/v1/orders/history", timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.debug(f"Go engine get_order_history failed: {e}")
        return None

    def run_reconciliation(self) -> Optional[Dict[str, Any]]:
        """Run broker reconciliation against OMS state."""
        try:
            r = self.session.post(f"{self.base_url}/api/v1/reconciliation/run", timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.debug(f"Go engine run_reconciliation failed: {e}")
        return None

    def list_brokers(self) -> Optional[Dict[str, Any]]:
        """List all pluggable broker adapters and their health."""
        try:
            r = self.session.get(f"{self.base_url}/api/v1/brokers", timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.debug(f"Go engine list_brokers failed: {e}")
        return None

    def select_broker(self, name: str) -> Optional[Dict[str, Any]]:
        """Dynamically switch the active execution broker."""
        try:
            r = self.session.post(f"{self.base_url}/api/v1/brokers/select", json={"name": name}, timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.debug(f"Go engine select_broker failed: {e}")
        return None

    def get_broker_health(self) -> Optional[Dict[str, Any]]:
        """Get broker health summary from Go engine."""
        try:
            r = self.session.get(f"{self.base_url}/api/v1/brokers/health", timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.debug(f"Go engine get_broker_health failed: {e}")
        return None



