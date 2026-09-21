FROM golang:1.25-bookworm AS builder

WORKDIR /src/backend
COPY backend/go.mod backend/go.sum ./
RUN go mod download
COPY backend/ ./
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/routing-api ./cmd/server

FROM node:22-alpine AS frontend-builder

WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HTTP_ADDR=:8080 \
    MIGRATIONS_DIR=/app/backend/migrations \
    FRONTEND_DIR=/app/frontend \
    SOLVER_PYTHON=python3 \
    SOLVER_PYTHONPATH=/app/solver/src \
    SOLVER_TIMEOUT=30s \
    AUTO_MIGRATE=true

WORKDIR /app
COPY solver/ /app/solver/
RUN pip install --no-cache-dir "/app/solver[ortools]"

COPY --from=builder /out/routing-api /usr/local/bin/routing-api
COPY backend/migrations/ /app/backend/migrations/
COPY --from=frontend-builder /src/frontend/dist/ /app/frontend/

RUN useradd --uid 10001 --home-dir /app --shell /usr/sbin/nologin routing \
    && mkdir -p /app/.cache \
    && chown -R routing:routing /app/.cache

EXPOSE 8080
USER routing
ENTRYPOINT ["routing-api"]
