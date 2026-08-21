@echo off
set PYTHONPATH=src;%PYTHONPATH%
python -m ai_quant.main deep-research --symbol NVDA --market SPY --sector XLK --growth QQQ --bond TLT --gold GLD --days 1000
pause
