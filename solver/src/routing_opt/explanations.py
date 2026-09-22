from __future__ import annotations

from .domain import Problem, Solution


def explain_solution(problem: Problem, solution: Solution) -> dict[str, str]:
    engineers = problem.engineers_by_id
    jobs = problem.jobs_by_id
    explanations: dict[str, str] = {}
    for route in solution.routes:
        engineer = engineers[route.engineer_id]
        for stop in route.stops:
            job = jobs[stop.job_id]
            transport_text = (
                "транспортное ограничение отсутствует"
                if job.required_transport is None
                else f"транспорт «{_transport(engineer.transport.value)}» соответствует требованию"
            )
            explanations[job.id] = (
                f"Назначено инженеру {engineer.id}: есть навык «{_skill(job.required_skill.value)}», "
                f"{transport_text}. Переезд от предыдущей точки — {stop.distance_km:.1f} км "
                f"и {stop.travel_minutes} мин; начало в {_clock(stop.service_start_minutes)} попадает "
                f"в окно {_clock(job.window_start)}–{_clock(job.window_end)}, завершение "
                f"в {_clock(stop.service_end_minutes)} укладывается в смену."
            )
    for item in solution.unassigned:
        explanations[item.job_id] = item.message
    return explanations


def _clock(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _skill(value: str) -> str:
    return {
        "connection": "подключение и дозаказы",
        "local": "локальные работы",
        "emergency": "аварийные работы",
    }.get(value, value)


def _transport(value: str) -> str:
    return {
        "car": "автомобиль",
        "walk": "пешком",
        "bicycle": "велосипед",
        "public_transit": "общественный транспорт",
    }.get(value, value)
