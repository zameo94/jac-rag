FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-ita \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry==2.4.3"

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

COPY . .

RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]
