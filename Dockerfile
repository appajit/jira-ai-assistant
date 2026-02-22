# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Install system dependencies used by bash scripts
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    jq \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files first for layer caching
COPY requirements.txt pyproject.toml ./

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project (scripts, agent/, app files)
COPY . .

# Make all scripts executable
RUN chmod +x scripts/*.sh

EXPOSE 8503

# Streamlit config: headless, no CORS restrictions for cloud hosting
ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8503 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

CMD ["streamlit", "run", "ui_app_ai.py", \
     "--server.headless=true", \
     "--server.address=0.0.0.0", \
     "--server.port=8503"]
