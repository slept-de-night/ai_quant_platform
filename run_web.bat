@echo off
echo Starting AI Quant Platform Web Server...
python -m ai_quant.main web --host 0.0.0.0 --port 8000
pause
