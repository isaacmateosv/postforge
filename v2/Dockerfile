FROM python:3.12-alpine@sha256:e6dae589c1c05976188fd3bd019afd091445fc533ed2ea29001beddc7368a9c8
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY postforge_v2.py telegram_worker.py ./
RUN mkdir /state && chown 10001:10001 /state
USER 10001:10001
CMD ["python", "-m", "postforge_v2", "web"]
