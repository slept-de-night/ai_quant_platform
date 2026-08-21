@echo off
echo Starting Go High-Performance Execution Engine on :8080...
set GOROOT=C:\Users\2465975\go
set PATH=C:\Users\2465975\go\bin;%PATH%
cd services\aq-engine-go
go run main.go
pause
