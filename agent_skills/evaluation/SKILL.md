# Evaluation skill

Evaluate a model/task result using evidence external to the model's own confidence.

Prefer, in order:

1. deterministic validation or ground truth;
2. downstream walk-forward / robustness outcome;
3. source/evidence verification score;
4. blinded human or judge evaluation when objective scoring is unavailable.

Record failure as failure. Do not discard poor runs from the evaluation set.
Do not recommend routing changes from tiny samples.
