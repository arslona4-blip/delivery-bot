FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot
COPY miniapp ./miniapp

RUN mkdir -p /data

ENV PYTHONUNBUFFERED=1
ENV DATABASE_PATH=/data/bot.db
ENV WEBAPP_PORT=8088

CMD ["python", "-m", "bot.main"]
