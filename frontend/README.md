# Routecraft frontend

React + TypeScript SPA для диспетчера выездных бригад. Production-сборка
создаётся Vite и копируется в backend Docker image.

## Разработка

```bash
npm ci
npm run dev
```

Dev-сервер доступен на <http://localhost:5173> и проксирует `/api`, `/healthz`
и `/swagger` на backend `localhost:8080`.

Проверки:

```bash
npm run typecheck
npm test
npm run build
```

## Структура

```text
src/
├── app/                    # композиция приложения и глобальная тема
├── features/
│   └── route-animation/    # состояние проигрывателя маршрута
├── shared/
│   ├── api/                # типизированный REST-клиент
│   ├── lib/                # форматирование и геометрия
│   └── types/              # DTO и доменные типы
└── widgets/
    ├── map/                # MapLibre, маркеры и дорожные слои
    ├── planner/            # запуск оптимизации
    ├── playback/           # управление анимацией машины
    ├── point-editor/       # создание точки кликом
    ├── route-inspector/    # порядок старт → остановки → финиш
    └── sidebar/            # заявки и бригады
```

Карта отображает только детальную дорожную геометрию из backend. Старые
fallback-линии вида «старт + точки заявок» распознаются и не рисуются как дороги.
