from types import SimpleNamespace
from ai_quant.models import PortfolioState,Regime,Side,Signal
from ai_quant.risk import RiskEngine

cfg=SimpleNamespace(max_orders_per_day=8,max_daily_loss_pct=.02,max_drawdown_pct=.10,max_position_pct=.08,max_gross_exposure_pct=.6,min_cash_reserve_pct=.1,min_order_notional=50)
def sig(side=Side.BUY,score=.8): return Signal(symbol="SPY",strategy_name="s",score=score,side=side,reference_price=100,regime=Regime.BULL_LOW_VOL,reason="x")
def p(**kw):
    d=dict(equity=100000,cash=100000,gross_exposure=0,daily_pnl=0,peak_equity=100000,current_symbol_exposure=0,current_symbol_qty=0,orders_today=0); d.update(kw); return PortfolioState(**d)
def test_buy_is_capped():
    d=RiskEngine(cfg).evaluate(sig(),p()); assert d.approved and d.order.notional<=8000
def test_sell_cannot_open_short():
    d=RiskEngine(cfg).evaluate(sig(Side.SELL,-.8),p()); assert not d.approved
def test_sell_closes_existing_long():
    d=RiskEngine(cfg).evaluate(sig(Side.SELL,-.8),p(current_symbol_qty=12,current_symbol_exposure=1200)); assert d.approved and d.order.qty==12
def test_daily_loss_kill():
    d=RiskEngine(cfg).evaluate(sig(),p(daily_pnl=-3000)); assert not d.approved

def test_institutional_var_metrics():
    import numpy as np
    from ai_quant.risk import calculate_institutional_risk_profile, calculate_parametric_var, calculate_cvar
    returns = np.random.normal(0.0005, 0.012, 252)
    profile = calculate_institutional_risk_profile(returns, equity=100000.0)
    assert profile["equity"] == 100000.0
    assert profile["var_95_usd"] > 0
    assert profile["var_99_usd"] >= profile["var_95_usd"]
    assert profile["cvar_95_usd"] > 0
    assert "annualized_volatility" in profile
    assert "sharpe_ratio" in profile

