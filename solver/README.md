# Routing optimizer

Автономная алгоритмическая часть сервиса планирования маршрутов выездных
инженеров. Требуется Python 3.11+.

## Возможности

- единые модели `Problem`, `Job`, `Engineer`, `TravelMatrices`, `Solution`;
- загрузка исходных CSV в `cp1251` без использования контрольных назначений;
- два режима для `Глобальная проблема / Информация`: выездная работа или
  исключение с машинно-читаемой причиной;
- детерминированная генерация демонстрационных инженеров 12/12/11;
- Haversine-матрицы для автономной отладки и пакетный клиент OSRM Table;
- официальный greedy baseline и отдельная best-insertion эвристика;
- Google OR-Tools VRPTW;
- компактный Hybrid Genetic Search;
- независимый `validate_solution(problem, solution)`;
- события перепланирования и сравнение опубликованного/нового плана;
- генератор кластерных задач, benchmark по нескольким seed;
- JSON/CSV-экспорт, интерактивная карта, Gantt и таблица benchmark.
- дорожная геометрия маршрутов через кэшируемый OSRM Route client.

## Установка

Из корня репозитория:

```bash
python3 -m venv solver/.venv
solver/.venv/bin/python -m pip install -e './solver[ortools,dev]'
```

Для запуска ноутбуков в том же окружении:

```bash
solver/.venv/bin/python -m pip install -e './solver[ortools,dev,notebooks]'
solver/.venv/bin/jupyter lab solver/notebooks
```

## Проверки и демонстрация

```bash
solver/.venv/bin/pytest solver/tests
solver/.venv/bin/routing-demo --jobs 30 --time-limit 3
```

Результаты демонстрации сохраняются в `solver/outputs/demo/`:

- решения в JSON;
- сравнительная таблица CSV/HTML;
- карта `map.html`;
- расписание `gantt.html`.

## Архитектура

```text
solver/
├── configs/default.json
├── contracts/
├── notebooks/
├── scripts/
├── src/routing_opt/
│   ├── domain.py
│   ├── loaders.py
│   ├── preprocessing.py
│   ├── geocoding.py
│   ├── matrices.py
│   ├── scheduling.py
│   ├── validation.py
│   ├── benchmark.py
│   ├── synthetic.py
│   ├── replanning.py
│   ├── visualization.py
│   └── solvers/
│       ├── greedy.py
│       ├── ortools_solver.py
│       └── hgs.py
└── tests/
```

Solver’ы имеют единый контракт:

```python
solution = solver.solve(problem, time_limit_sec=10, seed=42)
```

Для backend предпочтителен фасад с выбором алгоритма по стабильному имени:

```python
from routing_opt import solve

solution = solve(
    problem,
    solver_name="ortools",
    time_limit_sec=10,
    seed=42,
)
```

Полный HTTP- и Python-контракт описан в `../docs/backend-integration.md`.
Go backend вызывает этот фасад через модуль `routing_opt.backend_bridge`: один
JSON передаётся через `stdin`, один JSON-результат читается из `stdout`. При
`routing_base_url` bridge строит матрицу через OSRM Table, иначе использует
детерминированное Haversine-приближение.

## Исходные данные организаторов

```python
from routing_opt.loaders import LoaderConfig, load_zone_dataset

draft = load_zone_dataset(
    "data/raw/east/jobs.csv",
    "east",
    LoaderConfig(info_policy="field_service"),  # либо "exclude"
)
```

`ProblemDraft` ещё не готов для solver’а: адресам нужны координаты, а затем
матрицы. Координаты можно подать через `CsvGeocoder` с колонками `address`,
`latitude`, `longitude`. После этого используются `haversine_matrices` или
`OsrmTableClient` и `draft.to_problem(matrices)`.

Публичный геокодер намеренно не зашит в приложение. Для 205 адресов нужно выбрать
сервис с подходящими условиями, кэшировать результаты и не отправлять адреса в
неодобренный провайдер. `CachedGeocoder` принимает любой явно выбранный адаптер.

OSRM-клиент использует `table` endpoint и разбивает матрицу на блоки — отдельный
HTTP-запрос на каждую пару не выполняется. `base_url` передаётся явно: это может
быть собственный OSRM или разрешённый внешний сервис.

Для карты `CachedRouteGeometry(OsrmRouteGeometryClient(...))` запрашивает полную
дорожную polyline один раз на маршрут и сохраняет её локально. Без provider карта
остаётся полностью автономной и соединяет остановки прямыми линиями. Готовый
пример находится в `notebooks/06_map_playground.ipynb`.

HTTPS-запросы к routing provider проверяют сертификат через CA bundle `certifi`.
Это нужно для Python из `pyenv`/виртуального окружения на macOS, где системные CA
не всегда доступны стандартному `urllib`.

Подложка использует бесплатные vector tiles OpenFreeMap через MapLibre. Напрямую
обращаться к volunteer-run `tile.openstreetmap.org` из локального HTML нельзя:
такие запросы не передают корректный Referer и могут получить HTTP 403.

## Допущения для текущих данных

- смена инженера: 10:00–22:00;
- старт: офис своей зоны;
- навыки демонстрационных инженеров генерируются детерминированно;
- транспорт инженеров синтетический, у исходных заявок требования к транспорту
  отсутствуют;
- все исходные приоритеты обычные;
- service time: подключение 70, авария 80, дозаказ 20, локальная работа 30 минут;
- нормативные 20 минут дороги не добавляются поверх маршрутной матрицы;
- возвращение в офис после последней заявки не требуется.

Все допущения находятся на границе загрузки/конфигурации и могут быть заменены
реальной таблицей инженеров без изменения solver’ов. Для будущего файла уже есть
`load_engineers_csv()`. Он принимает UTF-8 CSV с колонками `id`,
`start_location_id`, `shift_start`, `shift_end`, `skills`, `transport`; несколько
навыков разделяются символом `|`.

## OR-Tools

Модель использует:

- time dimension с ожиданием и индивидуальными сменами;
- временные окна на начало обслуживания;
- service time в transit callback;
- разрешённые vehicle IDs для навыков и транспорта;
- disjunction penalties для необязательных заявок;
- более высокий штраф срочных заявок;
- fixed vehicle cost;
- открытые маршруты: путь от последней заявки в конец имеет нулевую дорогу, но
  учитывает обслуживание последней заявки;
- детерминированный seed и один worker;
- стоимость смены назначения при перепланировании.

Штрафы рассчитаны из верхней границы стоимости текущей задачи: потеря заявки
доминирует над количеством инженеров, а новый инженер — над пробегом.

## HGS

Реализована минимальная, но не номинальная версия HGS:

- популяция допустимых и временно недопустимых решений;
- selective route crossover;
- локальный поиск `relocate`, `swap`, `2-opt`, `2-opt*`;
- межмаршрутные переносы;
- адаптивный штраф нарушений временных окон/смен;
- survivor selection с расстоянием по рёбрам и неназначенным заявкам;
- остановка по времени/итерациям и фиксированный seed;
- публикация только лучшего допустимого решения.

## Ограничения текущей версии

- реальные исходные данные нельзя оптимизировать до получения координат;
- без подключения route geometry provider карта проводит прямые линии;
- контрольное распределение не содержит порядка и времени посещения, поэтому с
  ним сравнимы только ограниченные агрегаты;
- HGS рассчитан на исследование и сравнение, а OR-Tools остаётся основным solver’ом.
