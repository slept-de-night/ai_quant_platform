# Stage 1: Build the Modern React 19 Trading Workstation
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python API & Execution Engine
FROM python:3.12-slim
WORKDIR /app

# Install system dependencies (curl for container healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt httpx

# Copy source code and project metadata
COPY pyproject.toml .
COPY src ./src
COPY agent_skills ./agent_skills

# Copy compiled frontend assets from builder stage
COPY --from=frontend-builder /app/src/ai_quant/web/static ./src/ai_quant/web/static

# Install project package in editable mode
RUN pip install -e .

# Create directories for persistent volume mounts
RUN mkdir -p /app/data /app/agent_memory

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    DB_PATH=/app/data/ai_quant.sqlite3 \
    AGENT_MEMORY_DIR=/app/agent_memory

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/status || exit 1

CMD ["uvicorn", "ai_quant.server:app", "--host", "0.0.0.0", "--port", "8000"]
