@echo off
echo Building and running AI Quant Platform in Docker...
docker compose up --build -d
echo AI Quant Platform is running at http://localhost:8000
pause
