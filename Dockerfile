# Dockerfile for Radiology Information Systems Multi-Agent Workflow
# Compatible with Mistral AI Studio Managed Agents
#
# Usage:
#   docker build -t ris-assist-mistral-workflow .
#   docker run -e MISTRAL_API_KEY=your-key ris-assist-mistral-workflow
#
# Or with agents deploy:
#   agents deploy --config config/deployment.yaml

# Use official Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install mistralai-agents if not already in requirements
RUN pip install --no-cache-dir mistralai-agents || true

# Copy project files
COPY . .

# Create directories for runtime files
RUN mkdir -p /tmp/ris-assist-output /app/output

# Set default environment variables
ENV SITE_PROFILE_PATH="/app/site_profile.yaml" \
    COMMS_PROFILE_PATH="/app/comms_profile.yaml" \
    OUTPUT_DIR="/app/output" \
    LOG_LEVEL="INFO"

# Expose port for potential web interface
EXPOSE 8000

# Set the entry point
ENTRYPOINT ["python", "workflows/ris_multi_agent_workflow.py"]

# Alternative entry point for agents serve
# To use: docker run -p 8000:8000 ris-assist-mistral-workflow agents serve --config config/deployment.yaml
CMD ["--help"]
