FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /service
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt \
    && useradd --create-home --uid 10001 sentinelzone
COPY --chown=sentinelzone:sentinelzone . .
USER sentinelzone
EXPOSE 8004
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8004/health', timeout=8)" || exit 1
CMD ["python", "scripts/start.py"]
