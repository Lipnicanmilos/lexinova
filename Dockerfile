# Multi-stage build for smaller production image
FROM python:3.12-slim as builder

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Environment variables (override in deployment, e.g., via Docker run or Compose)
ENV PYTHONPATH=/app
ENV DATABASE_URL=postgresql://user:pass@host:port/db  # Set to Supabase URL
ENV SESSION_SECRET=your-secret-key-12345  # Set secure value
ENV GOOGLE_CLIENT_ID=your-google-client-id
ENV GOOGLE_CLIENT_SECRET=your-google-client-secret
ENV GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# Run the app with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
