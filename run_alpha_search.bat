@echo off
set PYTHONPATH=src;%PYTHONPATH%
python -m ai_quant.main alpha-search --symbol SPY --count 6 --days 1800
pause
