FROM node:24-bookworm-slim AS frontend
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.6
COPY pyproject.toml uv.lock ./
COPY src/ src/
RUN uv sync --frozen --no-dev --no-editable
COPY --from=frontend /build/web/dist web/dist/
COPY logging.json ./
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "exec .venv/bin/uvicorn urja.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log --log-config logging.json"]
