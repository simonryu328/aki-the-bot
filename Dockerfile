# ==========================================
# Phase 1: Build Frontend (Node.js)
# ==========================================
FROM node:20-slim AS frontend-builder
WORKDIR /app/web

# Install dependencies first (caching)
COPY web/package*.json ./
RUN npm ci

# Copy source and build
COPY web/ ./
RUN npm run build

# ==========================================
# Phase 2: Runtime (Python)
# ==========================================
FROM python:3.11-slim-bookworm

WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Install system dependencies (if needed for postgres/etc)
# RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy built frontend from Phase 1
COPY --from=frontend-builder /app/web/dist ./web/dist

# Copy application code
COPY . .

# Run the server
# valid command: python run_server.py
CMD ["python", "run_server.py"]
