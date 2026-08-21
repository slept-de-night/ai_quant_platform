@echo off
echo ===================================================
echo Starting AI Quant Platform (Go Engine + Web Server)
echo ===================================================

echo Starting Go Execution Engine in background...
start "Go Execution Engine" cmd /k "cd services\aq-engine-go && go run main.go"

timeout /t 2 /nobreak >nul

echo Starting Python AI Quant Web Workstation on http://localhost:8000 ...
set PYTHONPATH=src;%PYTHONPATH%
python -m ai_quant.main web --host 0.0.0.0 --port 8000
pause
