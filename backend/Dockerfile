FROM golang:1.25-bookworm AS builder

WORKDIR /src/backend
COPY backend/go.mod backend/go.sum ./
RUN go mod download
COPY backend/ ./
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/routing-api ./cmd/server

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
COPY frontend/ /app/frontend/

EXPOSE 8080
USER nobody
ENTRYPOINT ["routing-api"]
