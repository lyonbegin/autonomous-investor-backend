FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends sqlite3 wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY recovery/recover.sh /recover.sh
RUN chmod +x /recover.sh

CMD ["/recover.sh"]
