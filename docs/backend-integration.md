# Контракт алгоритма с backend

## Рекомендуемая схема

Backend реализован на Go, поэтому Python-алгоритм подключён через локальный
процессный JSON-адаптер:

```text
HTTP request
    ↓
Go backend: проверка схемы и хранение в PostgreSQL
    ↓
planning.Service → JSON SolverInput
    ↓
python -m routing_opt.backend_bridge
    ↓
JSON → Problem → TravelMatrices → routing_opt.solve(...)
    ↓
validate_solution(problem, solution)
    ↓
Solution → Go → PostgreSQL + GeoJSON → frontend
```

Для MVP это не требует отдельного сетевого Python-сервиса: Go передаёт один JSON
в `stdin` и получает один JSON из `stdout`. При росте нагрузки тот же контракт
можно перенести в очередь и Python worker без изменения HTTP API и математики.

## Python-контракт

Процессный адаптер внутри Python вызывает стабильный фасад:

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

Go запускает solver через `exec.CommandContext` с ограниченным timeout. Сейчас
`POST /api/v1/plans` синхронный; следующая стадия масштабирования — очередь задач
и отдельный worker с тем же JSON-контрактом.

## Что backend передаёт алгоритму

### `Problem`

| Блок | Обязательные данные |
|---|---|
| Заявки | ID, location ID, service time, окно начала, навык, транспорт при наличии, приоритет |
| Инженеры | ID, стартовая точка, график `2/2`/`5/2`, смена, навыки, транспорт |
| Локации | ID, нормализованный адрес, координаты |
| Матрицы | единый порядок location IDs, время в минутах, расстояние в километрах |
| Перепланирование | предыдущее назначение `job_id → engineer_id`, если оно опубликовано |

Backend не должен передавать solver’у бригаду из контрольного распределения.
Контроль используется только после расчёта для аналитического сравнения.

Go backend отвечает за:

- проверку входного JSON;
- хранение времени как `HH:MM`/PostgreSQL `time`;
- хранение координат (до подключения геокодера они обязательны во входе);
- хранение планов и событий;
- применение серверных настроек solver, time limit и seed (они не показываются диспетчеру);
- запуск процессного адаптера и контроль timeout;
- получение дорожной геометрии только для уже выбранных маршрутов.

Python solver отвечает за:

- назначение заявок;
- порядок посещения;
- расписание с ожиданием;
- соблюдение навыков, транспорта, окон и смен;
- неназначенные заявки и машинно-читаемые причины;
- расчёт маршрутных метрик.

Без внешнего провайдера bridge строит детерминированную Haversine-матрицу. Если
задан `OSRM_BASE_URL`, Python использует OSRM Table для времени/расстояния, а Go
использует OSRM Route для GeoJSON готовых маршрутов. HTTP-контракт не меняется.

## Предлагаемый HTTP API backend

### Первичное планирование

```http
POST /api/v1/plans
Content-Type: application/json
```

Текущий endpoint использует все активные сущности либо переданные UUID. Для
обычного запуска frontend отправляет пустой объект — backend сам применяет
проверенные настройки:

```json
{}
```

Поля `request_ids`, `brigade_ids`, `solver_name`, `time_limit_seconds` и `seed`
остаются доступны для интеграционных тестов и исследовательских запусков, но не
являются пользовательскими настройками рабочего интерфейса.

MVP синхронно возвращает `201 Created`: объект плана с полем `solution`. Если
расчёт позднее переносится в очередь, первоначальный ответ может стать таким:

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
{"type":"cancel_request","payload":{"request_id":"UUID"}}
```

```json
{"type":"brigade_unavailable","payload":{"brigade_id":"UUID"}}
```

```json
{
  "type": "new_urgent_request",
  "payload": {
    "address": "Москва, Тверская улица, 1",
    "latitude": 55.7578,
    "longitude": 37.6156,
    "service_minutes": 80,
    "occurred_at": "14:00",
    "reaction_minutes": 120,
    "required_transport": null
  }
}
```

Для динамической аварии backend сам строит окно от момента поступления;
`reaction_minutes` допускается от 60 до 120 минут и по умолчанию равен 120.
Приоритет и навык `emergency` назначаются автоматически. Backend фиксирует
событие в `replan_events`, меняет статус сущности или создаёт срочную заявку,
извлекает назначения исходного плана как
`previous_assignments` и возвращает новый план со ссылкой на исходный.

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

Python bridge сериализует результат через `solution_to_dict()`, Go сохраняет его
в `plans.solution` и нормализованных таблицах. Пример базового solution находится в
`solver/contracts/plan_response.example.json`.

Дорожная polyline возвращается в `solution.routes[].geometry` как GeoJSON:

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
- `503 Service Unavailable` — solver не запустился, превысил timeout или вернул
  решение, не прошедшее независимый валидатор;
- `201 Created` + `status=partial` внутри solution — корректный план, но часть
  заявок не назначена.

Неназначенные заявки не являются HTTP-ошибкой. Frontend должен показывать их
отдельным списком и использовать `code` для фильтрации/локализации сообщения.

## Версионирование и воспроизводимость

- HTTP-контракт имеет префикс `/api/v1`;
- сохранённый план содержит `seed`, `solver_name`, `time_limit_sec` для аудита,
  хотя диспетчер их не выбирает;
- вместе с планом сохраняются provider/profile и версия матрицы;
- внутренние времена — целые минуты, внешние — ISO 8601 или `HH:MM` с датой и
  timezone плана;
- frontend не рассчитывает расписание и не исправляет ограничения самостоятельно.
