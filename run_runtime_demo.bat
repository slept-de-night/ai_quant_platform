@echo off
set PYTHONPATH=src;%PYTHONPATH%
python -m ai_quant.main runtime-run --symbol NVDA --concurrency 4
pause
