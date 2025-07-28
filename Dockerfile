FROM python:3.11-slim
ARG IS_4K_REQUEST=false
ENV IS_4K_REQUEST=$IS_4K_REQUEST
ENV AUTO_APPROVE=false
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir /logs
COPY scrape_imdb_and_request.py .
CMD ["python", "scrape_imdb_and_request.py"]
