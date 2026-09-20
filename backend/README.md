# Go backend

REST API хранит заявки, бригады, планы и события в PostgreSQL, а оптимизацию
выполняет существующий пакет `routing_opt` через JSON-процессный адаптер. На
`/` backend отдаёт SPA из `frontend/`.

## Запуск целиком

Из корня репозитория:

```bash
docker compose up --build
```

После старта доступны:

- интерфейс: <http://localhost:8080>;
- Swagger UI: <http://localhost:8080/swagger/index.html>;
- OpenAPI JSON: <http://localhost:8080/swagger/doc.json>;
- healthcheck: <http://localhost:8080/healthz>;
- PostgreSQL: `localhost:5432`, база/пользователь/пароль `routing`.

Docker в текущей машине не установлен, поэтому compose-конфигурация проверяется
структурно и сборкой Go, но полный контейнерный smoke test нужно выполнить на
машине с Docker.

## Локальная разработка

1. Запустить PostgreSQL и создать базу `routing`.
2. Установить solver по инструкции из `solver/README.md`.
3. Перейти в `backend/`, при необходимости скопировать `.env.example` в своё
   окружение и выполнить:

```bash
export DATABASE_URL='postgres://routing:routing@localhost:5432/routing?sslmode=disable'
export SOLVER_PYTHON='../solver/.venv/bin/python'
make run
```

Миграции `*.up.sql` применяются при старте. Это отключается через
`AUTO_MIGRATE=false`.

## API

| Метод | Endpoint | Назначение |
|---|---|---|
| `POST` | `/api/v1/requests/` | Создать заявку |
| `GET` | `/api/v1/requests/` | Получить заявки |
| `PATCH` | `/api/v1/requests/{id}/status` | Сменить жизненный статус |
| `POST` | `/api/v1/brigades/` | Создать бригаду |
| `GET` | `/api/v1/brigades/` | Получить бригады |
| `PATCH` | `/api/v1/brigades/{id}/status` | Изменить доступность |
| `POST` | `/api/v1/plans/` | Синхронно рассчитать план |
| `GET` | `/api/v1/plans/` | Получить последние 50 планов |
| `GET` | `/api/v1/plans/{id}` | Получить план и solution |
| `POST` | `/api/v1/plans/{id}/events` | Применить событие и перепланировать |

Если `request_ids`/`brigade_ids` не переданы в планирование, используются все
неотменённые заявки и доступные бригады. Параметры расчёта:

```json
{
  "solver_name": "ortools",
  "time_limit_seconds": 10,
  "seed": 42
}
```

Для оперативного перепланирования поддержаны события:

```json
{"type":"cancel_request","payload":{"request_id":"..."}}
```

```json
{"type":"brigade_unavailable","payload":{"brigade_id":"..."}}
```

```json
{
  "type": "new_urgent_request",
  "payload": {
    "address": "Москва, ...",
    "latitude": 55.75,
    "longitude": 37.61,
    "service_minutes": 80,
    "window_start": "14:00",
    "window_end": "16:00",
    "required_skill": "emergency"
  }
}
```

## Swagger

OpenAPI генерируется из комментариев в handlers:

```bash
make swagger
```

Команда обновляет `docs/docs.go`, `docs/swagger.json` и `docs/swagger.yaml`.

## Маршрутная геометрия

По умолчанию solver использует приближённую Haversine-матрицу, а backend
возвращает GeoJSON `LineString` по точкам маршрута. Для дорожной матрицы времени,
расстояний и дорожной геометрии задайте разрешённый OSRM endpoint:

```bash
OSRM_BASE_URL=https://router.project-osrm.org docker compose up --build
```

Для геометрии при ошибке OSRM срабатывает fallback на прямые линии. Ошибка Table
API останавливает расчёт, чтобы backend не выдавал расписание по неожиданно
другой матрице.
