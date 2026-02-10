# Use Python 3.14 as base image
FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml ./

# Install dependencies
RUN uv pip install --system --no-cache -e .

# Copy application code
COPY app ./app
COPY config ./config

# Create necessary directories
RUN mkdir -p /app/data /app/logs

# Run the bot
CMD ["python", "-m", "app"]
