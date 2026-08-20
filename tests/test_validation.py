from ai_quant.data import synthetic_bars
from ai_quant.factors import seed_strategies
from ai_quant.validation import walk_forward_validate

def test_walk_forward_has_multiple_folds():
    r=walk_forward_validate(synthetic_bars("SPY",1300),seed_strategies()[0],train_days=400,test_days=100,step_days=100,min_folds=2,min_sharpe=-99,max_drawdown=1,min_robust=-99); assert len(r.folds)>=2
