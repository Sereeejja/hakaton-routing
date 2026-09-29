from __future__ import annotations

import csv
import random
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from .domain import Engineer, Job, Location, Priority, Problem, Skill, Transport, TravelMatrices
from .preprocessing import normalize_address

InfoPolicy = Literal["field_service", "exclude"]


ZONE_ENGINEER_COUNTS: Mapping[str, int] = {
    "east": 12,
    "south_east": 12,
    "south_center": 11,
}

SERVICE_MINUTES_BY_BK: Mapping[str, int] = {
    "Подключение": 70,
    "Дозаказ": 20,
    "Локальная заявка": 30,
    "Глобальная проблема": 80,
}

SKILL_BY_BK: Mapping[str, Skill] = {
    "Подключение": Skill.CONNECTION,
    "Дозаказ": Skill.CONNECTION,
    "Локальная заявка": Skill.LOCAL,
    "Глобальная проблема": Skill.EMERGENCY,
}


@dataclass(frozen=True, slots=True)
class LoaderConfig:
    info_policy: InfoPolicy = "field_service"
    information_service_minutes: int = 80
    shift_start: int = 10 * 60
    shift_end: int = 22 * 60
    seed: int = 42
    office_address: str | None = None
    work_schedule: Literal["2/2", "5/2"] = "2/2"


@dataclass(frozen=True, slots=True)
class ProblemDraft:
    id: str
    zone: str
    jobs: tuple[Job, ...]
    engineers: tuple[Engineer, ...]
    locations: tuple[Location, ...]
    metadata: dict[str, object]

    def with_locations(self, locations: tuple[Location, ...]) -> ProblemDraft:
        return replace(self, locations=locations)

    def to_problem(self, matrices: TravelMatrices) -> Problem:
        return Problem(
            id=self.id,
            jobs=self.jobs,
            engineers=self.engineers,
            locations=self.locations,
            matrices=matrices,
            metadata=self.metadata,
        )


def load_zone_dataset(
    csv_path: str | Path,
    zone: str,
    config: LoaderConfig | None = None,
) -> ProblemDraft:
    """Parse one organizer synthetic CSV without consulting control assignments."""

    config = config or LoaderConfig()
    csv_path = Path(csv_path)
    with csv_path.open("r", encoding="cp1251", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))

    office_address = _extract_office(rows, fallback=config.office_address)
    office_id = f"office:{zone}"
    jobs: list[Job] = []
    locations: list[Location] = [Location(id=office_id, address=normalize_address(office_address))]

    source_dates: set[str] = set()
    for source_order, row in enumerate(rows):
        raw_id = (row.get("Заявка") or "").strip()
        if not raw_id.isdigit():
            continue
        bk_type = (row.get("Тип заявки BK") or "").strip()
        hd_type = (row.get("Тип заявки HD") or "").strip()
        try:
            skill = SKILL_BY_BK[bk_type]
            service_minutes = SERVICE_MINUTES_BY_BK[bk_type]
        except KeyError as exc:
            raise ValueError(f"Unknown BK job type {bk_type!r} in {csv_path}") from exc

        is_information = bk_type == "Глобальная проблема" and hd_type == "Информация"
        planning_eligible = not (is_information and config.info_policy == "exclude")
        if is_information:
            service_minutes = config.information_service_minutes

        source_date = _parse_source_date(row["Начало"])
        source_dates.add(source_date)
        location_id = f"job:{zone}:{raw_id}"
        address = normalize_address((row.get("Адрес") or "").strip())
        locations.append(Location(id=location_id, address=address))
        jobs.append(
            Job(
                id=raw_id,
                location_id=location_id,
                service_minutes=service_minutes,
                window_start=_parse_minutes(row["Начало"]),
                window_end=_parse_minutes(row["Окончание"]),
                required_skill=skill,
                priority=Priority.URGENT if hd_type == "Авария" else Priority.NORMAL,
                planning_eligible=planning_eligible,
                metadata={
                    "zone": zone,
                    "source_order": source_order,
                    "source_date": source_date,
                    "bk_type": bk_type,
                    "hd_type": hd_type,
                    "district": (row.get("Район") or "").strip(),
                    "gigabit": (row.get("Гигабитное подключение") or "").strip(),
                    "connection_type": (row.get("Подключение") or "").strip(),
                    "information_policy": config.info_policy if is_information else None,
                },
            )
        )

    engineer_count = ZONE_ENGINEER_COUNTS.get(zone)
    if engineer_count is None:
        raise ValueError(f"Unknown zone {zone!r}; provide one of {sorted(ZONE_ENGINEER_COUNTS)}")
    engineers = generate_demo_engineers(
        zone=zone,
        count=engineer_count,
        office_location_id=office_id,
        shift_start=config.shift_start,
        shift_end=config.shift_end,
        seed=config.seed,
        work_schedule=config.work_schedule,
    )
    return ProblemDraft(
        id=f"organizer-{zone}",
        zone=zone,
        jobs=tuple(jobs),
        engineers=engineers,
        locations=tuple(locations),
        metadata={
            "source": str(csv_path),
            "source_dates": sorted(source_dates),
            "work_schedule": config.work_schedule,
            "info_policy": config.info_policy,
            "assumptions": [
                "demo engineers are synthetic and do not use control assignments",
                "HD type Авария is urgent; other source priorities are normal",
                "job transport requirement is absent",
            ],
        },
    )


def generate_demo_engineers(
    zone: str,
    count: int,
    office_location_id: str,
    shift_start: int,
    shift_end: int,
    seed: int = 42,
    work_schedule: Literal["2/2", "5/2"] = "2/2",
) -> tuple[Engineer, ...]:
    """Create deterministic demo profiles without leaking control assignments."""

    skill_templates = (
        frozenset({Skill.CONNECTION, Skill.LOCAL, Skill.EMERGENCY}),
        frozenset({Skill.CONNECTION, Skill.LOCAL}),
        frozenset({Skill.CONNECTION}),
        frozenset({Skill.LOCAL}),
        frozenset({Skill.EMERGENCY, Skill.LOCAL}),
        frozenset({Skill.EMERGENCY, Skill.CONNECTION}),
    )
    transports = [
        Transport.CAR,
        Transport.PUBLIC_TRANSIT,
        Transport.CAR,
        Transport.BICYCLE,
        Transport.WALK,
        Transport.CAR,
    ]
    rng = random.Random(f"{seed}:{zone}")
    offset = rng.randrange(len(skill_templates))
    result = []
    for index in range(count):
        template_index = (index + offset) % len(skill_templates)
        result.append(
            Engineer(
                id=f"{zone}-engineer-{index + 1:02d}",
                start_location_id=office_location_id,
                shift_start=shift_start,
                shift_end=shift_end,
                skills=skill_templates[template_index],
                transport=transports[template_index],
                metadata={"synthetic": True, "work_schedule": work_schedule},
            )
        )
    return tuple(result)


def load_engineers_csv(path: str | Path) -> tuple[Engineer, ...]:
    """Load future real engineer profiles from a stable UTF-8 interchange schema.

    Required columns: id, start_location_id, shift_start, shift_end, skills,
    transport. Optional ``work_schedule`` is ``2/2`` or ``5/2``. Skills are pipe-separated values such as
    ``connection|local``; times use HH:MM.
    """

    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {
        "id",
        "start_location_id",
        "shift_start",
        "shift_end",
        "skills",
        "transport",
    }
    if rows and not required.issubset(rows[0]):
        raise ValueError(f"Engineer CSV is missing columns: {sorted(required - set(rows[0]))}")
    engineers = []
    for row in rows:
        try:
            skills = frozenset(
                Skill(value.strip()) for value in row["skills"].split("|") if value.strip()
            )
            engineers.append(
                Engineer(
                    id=row["id"].strip(),
                    start_location_id=row["start_location_id"].strip(),
                    shift_start=_parse_clock(row["shift_start"]),
                    shift_end=_parse_clock(row["shift_end"]),
                    skills=skills,
                    transport=Transport(row["transport"].strip()),
                    metadata={
                        "synthetic": False,
                        "source": str(path),
                        "work_schedule": _work_schedule(row.get("work_schedule", "2/2")),
                    },
                )
            )
        except (KeyError, ValueError) as exc:
            raise ValueError(f"Invalid engineer row for ID {row.get('id', '<missing>')!r}") from exc
    return tuple(engineers)


def _extract_office(rows: list[dict[str, str]], fallback: str | None = None) -> str:
    for row in rows:
        marker = (row.get("Заявка") or "").strip().casefold()
        if marker == "адрес офиса":
            values = list(row.values())
            return (values[1] if len(values) > 1 else "").strip()
    if fallback and fallback.strip():
        return fallback.strip()
    raise ValueError("Office marker row was not found; pass LoaderConfig(office_address=...)")


def _work_schedule(value: str) -> str:
    schedule = value.strip() or "2/2"
    if schedule not in {"2/2", "5/2"}:
        raise ValueError(f"Unknown work schedule {schedule!r}")
    return schedule


def _parse_source_date(value: str) -> str:
    parts = value.strip().split()
    if len(parts) != 2:
        raise ValueError(f"Expected DD.MM.YYYY HH:MM, got {value!r}")
    day, month, year = (int(part) for part in parts[0].split("."))
    if not (1 <= day <= 31 and 1 <= month <= 12 and year >= 2000):
        raise ValueError(f"Invalid date in {value!r}")
    return f"{year:04d}-{month:02d}-{day:02d}"


def _parse_minutes(value: str) -> int:
    _parse_source_date(value)
    parts = value.strip().split()
    return _parse_clock(parts[1])


def _parse_clock(value: str) -> int:
    hour, minute = (int(part) for part in value.strip().split(":"))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid clock value {value!r}")
    return hour * 60 + minute
