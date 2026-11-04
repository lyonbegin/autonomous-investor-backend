FROM python:3.11-slim
WORKDIR /app
COPY market_daily_10y/requirements.txt /tmp/market-requirements.txt
RUN pip install --no-cache-dir -r /tmp/market-requirements.txt
COPY market_daily_10y /app/market_daily_10y
ENV PYTHONUNBUFFERED=1 DAILY_POOL_ROOT=/data/market_daily_10y DAILY_BATCH_LIMIT=20
CMD ["python","-m","market_daily_10y.collector"]
