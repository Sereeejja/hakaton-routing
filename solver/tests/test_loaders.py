from __future__ import annotations

from pathlib import Path

import pytest

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
