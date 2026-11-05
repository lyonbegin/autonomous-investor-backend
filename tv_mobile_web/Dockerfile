FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
COPY tv_mobile_web/requirements.txt /app/tv_mobile_web/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/tv_mobile_web/requirements.txt
COPY tv_mobile_web /app/tv_mobile_web
EXPOSE 8080
CMD ["sh", "-c", "uvicorn tv_mobile_web.server:app --host 0.0.0.0 --port ${PORT:-8080}"]
