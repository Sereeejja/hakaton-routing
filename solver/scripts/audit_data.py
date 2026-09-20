from __future__ import annotations

from pathlib import Path

from routing_opt.loaders import load_zone_dataset


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    total = 0
    for zone in ("east", "south_east", "south_center"):
        draft = load_zone_dataset(root / "data" / "raw" / zone / "jobs.csv", zone)
        excluded = sum(not job.planning_eligible for job in draft.jobs)
        print(
            f"{zone}: jobs={len(draft.jobs)}, engineers={len(draft.engineers)}, "
            f"excluded={excluded}, office={draft.locations[0].address}"
        )
        total += len(draft.jobs)
    print(f"total jobs={total}")


if __name__ == "__main__":
    main()
