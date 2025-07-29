# Use official Python base image
FROM python:3.11-slim

# Environment defaults (can be overridden)
ENV IS_4K_REQUEST=true
ENV DEBUG_MODE=SIMPLE
ENV RUN_INTERVAL_DAYS=7
ENV MOVIE_LIMIT=50

# Add placeholders for JWT login
ENV JELLYSEERR_URL=http://127.0.0.1:5055
ENV JELLYSEERR_EMAIL=""
ENV JELLYSEERR_PASSWORD=""

# Install dependencies
RUN pip install --no-cache-dir requests beautifulsoup4

# Create log directory
RUN mkdir -p /logs

# Copy script into container
COPY imdb.py /app/imdb.py

# Set working directory
WORKDIR /app

# Default command
CMD ["python", "imdb.py"]
