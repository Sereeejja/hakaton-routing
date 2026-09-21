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

При первом запуске сборка скачает Go-, Python- и npm-зависимости. React-фронтенд
собирается в отдельном Docker stage и затем раздаётся Go-сервером.

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

React-интерфейс с hot reload запускается отдельно (backend должен работать на
`:8080`, запросы проксируются автоматически):

```bash
cd frontend
npm ci
npm run dev
```

Откройте <http://localhost:5173>.

Миграции `*.up.sql` применяются при старте. Это отключается через
`AUTO_MIGRATE=false`.

## API

| Метод | Endpoint | Назначение |
|---|---|---|
| `POST` | `/api/v1/requests/` | Создать заявку |
| `GET` | `/api/v1/requests/` | Получить заявки |
| `DELETE` | `/api/v1/requests/` | Удалить все заявки и планы, сохранив бригады |
| `DELETE` | `/api/v1/requests/{id}` | Удалить заявку и связанные с ней планы |
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

В `docker compose` по умолчанию задан публичный демонстрационный OSRM: он даёт
дорожную матрицу времени, расстояния и GeoJSON-геометрию вдоль дорог. Для
нагруженного или автономного окружения задайте свой endpoint:

```bash
OSRM_BASE_URL=https://your-osrm.example docker compose up --build
```

При ошибке Route API маршрут остаётся без геометрии и UI явно показывает ошибку:
прямая линия вместо дороги намеренно не рисуется. Ошибка Table API останавливает
расчёт, чтобы backend не выдавал расписание по неожиданно другой матрице.

Чтобы полностью отключить внешний routing и вернуться к Haversine/прямой
геометрии только для отладки, запустите backend вне compose без
`OSRM_BASE_URL`.
