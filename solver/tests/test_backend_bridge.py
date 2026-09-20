from __future__ import annotations

from routing_opt.backend_bridge import solve_payload


def test_backend_bridge_solves_json_contract():
    result = solve_payload(
        {
            "problem_id": "api-test",
            "locations": [
                {"id": "office", "latitude": 55.75, "longitude": 37.61},
                {"id": "customer", "latitude": 55.76, "longitude": 37.62},
            ],
            "jobs": [
                {
                    "id": "job-1",
                    "location_id": "customer",
                    "service_minutes": 30,
                    "window_start": "10:00",
                    "window_end": "15:00",
                    "required_skill": "local",
                    "required_transport": None,
                    "priority": "normal",
                }
            ],
            "engineers": [
                {
                    "id": "engineer-1",
                    "start_location_id": "office",
                    "shift_start": "09:00",
                    "shift_end": "18:00",
                    "skills": ["local"],
                    "transport": "car",
                }
            ],
            "options": {"solver": "greedy", "time_limit_sec": 1, "seed": 42},
        }
    )
    assert result["status"] == "feasible"
    assert result["routes"][0]["stops"][0]["job_id"] == "job-1"
