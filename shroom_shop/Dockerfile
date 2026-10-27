FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Добавляем ffmpeg для сжатия видео
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Запускаем migrate, collectstatic и daphne (ASGI нужен для WebSocket-чата).
# Воркер django-q (qcluster) вынесен в отдельный сервис worker в compose.yml.
CMD ["sh", "-c", "\
    python manage.py migrate && \
    python manage.py collectstatic --no-input && \
    daphne -b 0.0.0.0 -p 8000 shroom_shop.asgi:application \
"]