FROM python:3.13-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose port (Render overrides with $PORT at runtime)
EXPOSE 8000

# Shell form so $PORT is expanded at runtime from Render's injected env var.
# Falls back to 8000 for local Docker runs.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
