#!/usr/bin/env bash
set -e

echo "=========================================================="
echo " Starting Institutional AI Quant Platform v1.2 in Docker "
echo "=========================================================="

# Check if Docker daemon is running
if ! docker info >/dev/null 2>&1; then
    echo "Docker daemon is not running."
    echo "Please start the Docker service with: sudo systemctl start docker"
    echo "Then re-run: ./docker_run.sh"
    exit 1
fi

echo "Building and starting containers (Go Core + Python Web Platform)..."
docker compose up --build -d

echo ""
echo "=========================================================="
echo " Institutional AI Quant Platform is now online!"
echo " Trading Workstation UI: http://localhost:8000"
echo " Go Execution Core:       http://localhost:8080/health"
echo " API Documentation:      http://localhost:8000/docs"
echo "=========================================================="
