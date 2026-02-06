# Build Stage for Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /build

# Copy frontend source
COPY traffic-app/package*.json ./
RUN npm install

COPY traffic-app/ ./
RUN npm run build

# Final Stage
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy built frontend from builder stage
# Ensure the directory exists
RUN mkdir -p traffic-app/dist
COPY --from=frontend-builder /build/dist ./traffic-app/dist

# Create directory for maps if it doesn't exist (though code does this)
RUN mkdir -p traffic-app/maps

# Expose port
EXPOSE 5000

# Run the unified scraper and server
CMD ["python", "traffic_scraper.py"]
