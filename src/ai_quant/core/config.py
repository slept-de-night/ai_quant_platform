from __future__ import annotations

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None

    # Universal LLM Provider configuration ('openai', 'anthropic', 'gemini', 'deepseek', 'ollama', 'custom')
    llm_provider: str = "openai"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None

    # Dynamic model deployment aliases
    model_fast: str = "gpt-5.6-luna"
    model_balanced: str = "gpt-5.6-terra"
    model_frontier: str = "gpt-5.6-sol"
    enable_pro_mode: bool = False

    # Token Pricing for Empirical Routing (USD per 1M tokens)
    model_fast_input_usd_per_m: float = 0.10
    model_fast_output_usd_per_m: float = 0.60
    model_balanced_input_usd_per_m: float = 1.00
    model_balanced_output_usd_per_m: float = 6.00
    model_frontier_input_usd_per_m: float = 2.50
    model_frontier_output_usd_per_m: float = 15.00

    # Runtime scheduler / worker semantics
    runtime_concurrency: int = 4
    runtime_lease_seconds: int = 120
    runtime_max_attempts: int = 3
    runtime_retry_base_seconds: int = 2
    runtime_max_retry_delay_seconds: int = 300
    agent_usd_budget_per_run: float = 10.0

    # Routing evaluation thresholds
    router_learning_min_samples: int = 8
    router_learning_min_quality: float = 0.72
    router_learning_min_success: float = 0.90

    # General AI Configuration
    openai_model: str = "gpt-5.6"
    openai_reasoning_effort: str = "medium"
    deep_research_reasoning_effort: str = "high"
    enable_web_research: bool = True

    # Agent governance / bounded delegation
    agent_max_depth: int = 2
    agent_max_children: int = 4
    agent_max_tasks_per_run: int = 24
    agent_token_budget: int = 180000
    agent_max_frontier_tasks: int = 6

    # Durable agent memory
    agent_memory_dir: str = "agent_memory"
    agent_memory_max_prompt_notes: int = 12
    agent_memory_default_expiry_days: int = 90

    # External APIs
    sec_user_agent: Optional[str] = None
    fred_api_key: Optional[str] = None
    dossier_max_age_hours: int = 24
    require_fresh_dossier: bool = True
    extra_primary_domains: str = ""
    extra_trusted_domains: str = ""

    alpaca_api_key: Optional[str] = None
    alpaca_secret_key: Optional[str] = None
    use_alpaca_data: bool = False

    db_path: str = "ai_quant.sqlite3"
    research_mask_symbols: bool = True
    alpha_candidates: int = 8
    wf_train_days: int = 504
    wf_test_days: int = 126
    wf_step_days: int = 126
    min_wf_folds: int = 2
    min_validation_sharpe: float = 0.50
    max_validation_drawdown: float = 0.25
    min_robust_score: float = 0.20

    starting_equity: float = 100000.0
    max_position_pct: float = 0.08
    max_gross_exposure_pct: float = 0.60
    min_cash_reserve_pct: float = 0.10
    max_daily_loss_pct: float = 0.02
    max_drawdown_pct: float = 0.10
    max_orders_per_day: int = 8
    min_order_notional: float = 50.0

    slippage_bps: float = 5.0
    commission_bps: float = 0.0

    # Go High-Performance Execution Core
    enable_go_engine: bool = True
    go_engine_url: str = "http://localhost:8080"

    # Control-Plane Security
    auth_token: Optional[str] = None
    auth_required: bool = False


settings = Settings()
