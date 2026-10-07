FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml ./
COPY app ./app
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN groupadd --gid 10001 backend && useradd --uid 10001 --gid backend --create-home backend
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels transformer-backend && rm -rf /wheels
WORKDIR /app
COPY --chown=backend:backend app ./app
COPY --chown=backend:backend alembic ./alembic
COPY --chown=backend:backend alembic.ini pyproject.toml ./
COPY --chown=backend:backend scripts ./scripts
COPY --chown=backend:backend docker/entrypoint.sh ./docker/entrypoint.sh
RUN chmod 755 /app/docker/entrypoint.sh
USER backend
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=6 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
