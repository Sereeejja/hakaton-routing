from __future__ import annotations

from pathlib import Path

import pytest

from routing_opt.domain import Priority, business_priority_rank
from routing_opt.loaders import LoaderConfig, load_engineers_csv, load_zone_dataset

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("zone", "count"),
    (("east", 66), ("south_east", 83), ("south_center", 56)),
)
def test_organizer_job_counts(zone, count):
    path = ROOT / "data" / "raw" / zone / "jobs.csv"
    draft = load_zone_dataset(path, zone)
    assert len(draft.jobs) == count
    assert len({job.id for job in draft.jobs}) == count
    assert len(draft.engineers) in (11, 12)
    assert draft.locations[0].address


def test_information_policy_supports_both_modes():
    path = ROOT / "data" / "raw" / "east" / "jobs.csv"
    field = load_zone_dataset(path, "east", LoaderConfig(info_policy="field_service"))
    excluded = load_zone_dataset(path, "east", LoaderConfig(info_policy="exclude"))
    field_info = [job for job in field.jobs if job.metadata["hd_type"] == "Информация"]
    excluded_info = [job for job in excluded.jobs if job.metadata["hd_type"] == "Информация"]
    assert len(field_info) == len(excluded_info) == 5
    assert all(job.planning_eligible for job in field_info)
    assert all(not job.planning_eligible for job in excluded_info)


def test_source_accidents_are_urgent_but_information_is_not():
    path = ROOT / "data" / "raw" / "east" / "jobs.csv"
    draft = load_zone_dataset(path, "east")
    accidents = [job for job in draft.jobs if job.metadata["hd_type"] == "Авария"]
    information = [job for job in draft.jobs if job.metadata["hd_type"] == "Информация"]

    assert accidents
    assert all(job.priority is Priority.URGENT for job in accidents)
    assert all(job.priority is Priority.NORMAL for job in information)


def test_source_business_priority_is_accident_then_connection_then_other():
    path = ROOT / "data" / "raw" / "east" / "jobs.csv"
    draft = load_zone_dataset(path, "east")
    ranks_by_type: dict[str, set[int]] = {}
    for job in draft.jobs:
        ranks_by_type.setdefault(str(job.metadata["bk_type"]), set()).add(
            business_priority_rank(job)
        )

    assert 2 in {business_priority_rank(job) for job in draft.jobs if job.metadata["hd_type"] == "Авария"}
    assert ranks_by_type["Подключение"] == {1}
    assert ranks_by_type["Дозаказ"] == {0}
    assert ranks_by_type["Локальная заявка"] == {0}


def test_future_engineer_csv_contract(tmp_path):
    path = tmp_path / "engineers.csv"
    path.write_text(
        "id,start_location_id,shift_start,shift_end,skills,transport\n"
        "real-1,office:east,10:00,22:00,connection|local,car\n",
        encoding="utf-8",
    )
    engineers = load_engineers_csv(path)
    assert engineers[0].id == "real-1"
    assert {skill.value for skill in engineers[0].skills} == {"connection", "local"}
    assert engineers[0].metadata["synthetic"] is False
    assert engineers[0].metadata["work_schedule"] == "2/2"


def test_additional_day_without_office_uses_explicit_master_data(tmp_path):
    path = tmp_path / "day.csv"
    path.write_text(
        "Заявка;Тип заявки BK;Статус BK;Тип заявки HD;Начало;Окончание;Район;Адрес\n"
        "100;Подключение;Отправлена;Конвергенция абонента;29.09.2026 10:00;29.09.2026 12:00;Центр;Москва\n",
        encoding="cp1251",
    )
    draft = load_zone_dataset(
        path,
        "east",
        LoaderConfig(office_address="Москва, офис", work_schedule="5/2"),
    )
    assert draft.locations[0].address == "Москва, офис"
    assert draft.jobs[0].metadata["source_date"] == "2026-09-29"
    assert draft.metadata["source_dates"] == ["2026-09-29"]
    assert draft.metadata["work_schedule"] == "5/2"
    assert all(item.metadata["work_schedule"] == "5/2" for item in draft.engineers)
