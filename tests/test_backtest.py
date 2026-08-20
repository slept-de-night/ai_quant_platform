from ai_quant.data import synthetic_bars
from ai_quant.factors import seed_strategies
from ai_quant.backtest import run_backtest

def test_backtest_runs_and_is_shifted():
    m,frame=run_backtest(synthetic_bars("SPY",900),seed_strategies()[0]); assert m.observations>100; assert "equity" in frame; assert frame.position.iloc[0]==0
