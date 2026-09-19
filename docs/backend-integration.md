# Контракт алгоритма с backend

## Рекомендуемая схема

Алгоритм подключается к Python-backend как библиотека, а не как отдельный
микросервис:

```text
HTTP request
    ↓
Backend: проверка схемы, авторизация, хранение
    ↓
Adapter: HTTP DTO → routing_opt.Problem
    ↓
Геокодирование и кэш → TravelMatrices
    ↓
routing_opt.solve(problem, ...)
    ↓
validate_solution(problem, solution)
    ↓
Solution → JSON/GeoJSON → frontend
```

Такой вариант проще для MVP: нет сетевого контракта между backend и solver,
типизированные модели передаются напрямую в памяти. При росте нагрузки тот же
вызов можно вынести в worker без изменения математической части.

## Python-контракт

Backend вызывает один стабильный фасад:

```python
from routing_opt import solve, validate_solution

solution = solve(
    problem,
    solver_name="ortools",
    time_limit_sec=10,
    seed=42,
)
report = validate_solution(problem, solution)
if not report.valid:
    raise RuntimeError(report.errors)
```

Поддерживаемые значения `solver_name`:

- `greedy` — официальный baseline;
- `improved_greedy` — best-insertion эвристика;
- `ortools` — основной solver;
- `hgs` — исследовательский Hybrid Genetic Search.

Вызов синхронный и CPU-bound. В FastAPI его нельзя выполнять непосредственно в
асинхронном event loop: используйте обычный `def` endpoint, thread pool или
фоновый worker.

## Что backend передаёт алгоритму

### `Problem`

| Блок | Обязательные данные |
|---|---|
| Заявки | ID, location ID, service time, окно начала, навык, транспорт при наличии, приоритет |
| Инженеры | ID, стартовая точка, смена, навыки, транспорт |
| Локации | ID, нормализованный адрес, координаты |
| Матрицы | единый порядок location IDs, время в минутах, расстояние в километрах |
| Перепланирование | предыдущее назначение `job_id → engineer_id`, если оно опубликовано |

Backend не должен передавать solver’у бригаду из контрольного распределения.
Контроль используется только после расчёта для аналитического сравнения.

Backend отвечает за:

- проверку входного JSON;
- перевод ISO 8601/`HH:MM` во внутренние минуты дня;
- геокодирование и кэш координат;
- получение/кэш матриц;
- хранение планов и событий;
- выбор solver, time limit и seed;
- вызов независимого валидатора;
- получение дорожной геометрии только для уже выбранных маршрутов.

Solver отвечает за:

- назначение заявок;
- порядок посещения;
- расписание с ожиданием;
- соблюдение навыков, транспорта, окон и смен;
- неназначенные заявки и машинно-читаемые причины;
- расчёт маршрутных метрик.

## Предлагаемый HTTP API backend

### Первичное планирование

```http
POST /api/v1/plans
Content-Type: application/json
```

Тело соответствует `solver/contracts/plan_request.example.json`. Для хакатонного
MVP endpoint может синхронно вернуть `200 OK` с готовым планом. Если расчёт
переносится в очередь:

```json
{
  "plan_id": "plan-2026-08-17-east-001",
  "status": "queued"
}
```

и результат читается через:

```http
GET /api/v1/plans/{plan_id}
```

### Перепланирование

```http
POST /api/v1/plans/{plan_id}/events
```

Примеры событий:

```json
{"type": "cancel_job", "job_id": "74198"}
```

```json
{"type": "engineer_unavailable", "engineer_id": "east-engineer-03"}
```

```json
{
  "type": "new_urgent_job",
  "job": {
    "id": "urgent-1",
    "location_id": "location-urgent-1",
    "service_minutes": 80,
    "window_start": "14:00",
    "window_end": "16:00",
    "required_skill": "emergency",
    "priority": "urgent"
  }
}
```

Backend применяет событие через `apply_event`, обновляет координаты/матрицы для
новой точки, вызывает solver с `previous_assignments` и возвращает новый план
вместе с `compare_plans(before, after)`.

## Что алгоритм возвращает backend

`Solution` содержит:

- `status`: `feasible`, `partial`, `infeasible` или `error`;
- маршрут каждого инженера;
- последовательность заявок;
- выезд, прибытие, начало/окончание работ и ожидание;
- время и расстояние каждого переезда;
- суммарные метрики маршрута и плана;
- неназначенные заявки с `code` и понятным `message`;
- runtime, seed, имя алгоритма и диагностические metadata.

Backend сериализует результат через `solution_to_dict()` или
`save_solution_json()`. Пример находится в
`solver/contracts/plan_response.example.json`.

Дорожную polyline рекомендуется возвращать отдельно в стандартном GeoJSON:

```json
{
  "type": "Feature",
  "properties": {"engineer_id": "east-engineer-01", "color": "#4363d8"},
  "geometry": {
    "type": "LineString",
    "coordinates": [[37.61, 55.75], [37.62, 55.76]]
  }
}
```

В GeoJSON порядок координат — `[longitude, latitude]`.

## Семантика ошибок

- `422 Unprocessable Entity` — некорректные поля, неизвестные навыки/транспорт;
- `503 Service Unavailable` — недоступен routing/geocoding provider и нет кэша;
- `200 OK` + `status=partial` — корректный план, но часть заявок не назначена;
- `500 Internal Server Error` — solver вернул решение, не прошедшее независимый
  валидатор; такой результат нельзя отдавать frontend как успешный.

Неназначенные заявки не являются HTTP-ошибкой. Frontend должен показывать их
отдельным списком и использовать `code` для фильтрации/локализации сообщения.

## Версионирование и воспроизводимость

- HTTP-контракт имеет префикс `/api/v1`;
- request и сохранённый план содержат `seed`, `solver_name`, `time_limit_sec`;
- вместе с планом сохраняются provider/profile и версия матрицы;
- внутренние времена — целые минуты, внешние — ISO 8601 или `HH:MM` с датой и
  timezone плана;
- frontend не рассчитывает расписание и не исправляет ограничения самостоятельно.
