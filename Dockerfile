FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /app/

# Define ENV variables
ENV USE_JWT=false
ENV JELLYSEERR_URL=http://localhost:5055
ENV API_KEY=""
ENV USER_EMAIL=""
ENV USER_PASSWORD=""
ENV IS_4K_REQUEST=true
ENV AUTO_APPROVE=true
ENV RUN_INTERVAL_DAYS=7
ENV MOVIE_LIMIT=50
ENV DEBUG_MODE=SIMPLE

RUN mkdir -p /logs

CMD ["python", "imdb.py"]
