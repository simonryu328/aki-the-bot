# ==========================================
# Aki — Runtime (Python + static frontend)
# ==========================================
FROM python:3.11-slim-bookworm

WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (includes web/ with vanilla HTML/CSS/JS)
COPY . .

# Run the server
CMD ["python", "run_server.py"]
