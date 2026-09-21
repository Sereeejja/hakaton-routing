import { describe, expect, it } from "vitest";
import { bearingBetween, hasRoadGeometry, haversineDistance, pointAlongRoute } from "./geometry";
import type { PlannedRoute } from "../types/domain";

describe("route geometry helpers", () => {
  it("interpolates start, middle and end of a route", () => {
    const line: [number, number][] = [[37, 55], [38, 55]];
    expect(pointAlongRoute(line, 0)?.coordinate).toEqual([37, 55]);
    expect(pointAlongRoute(line, 0.5)?.coordinate[0]).toBeCloseTo(37.5, 5);
    expect(pointAlongRoute(line, 1)?.coordinate).toEqual([38, 55]);
  });

  it("returns realistic distance and bearing", () => {
    expect(haversineDistance([37.6173, 55.7558], [37.6173, 55.7658])).toBeCloseTo(1.11, 1);
    expect(bearingBetween([37, 55], [38, 55])).toBeGreaterThan(80);
    expect(bearingBetween([37, 55], [38, 55])).toBeLessThan(100);
  });

  it("rejects legacy straight-line geometry", () => {
    const route: PlannedRoute = {
      engineer_id: "team-1",
      departure_minutes: 540,
      finish_minutes: 600,
      stops: [{ sequence: 1, job_id: "job-1", from_location_id: "depot", travel_minutes: 10, distance_km: 2, arrival_minutes: 550, service_start_minutes: 550, service_end_minutes: 580, waiting_minutes: 0 }],
      total_travel_minutes: 10,
      total_waiting_minutes: 0,
      total_service_minutes: 30,
      total_distance_km: 2,
      geometry: { type: "LineString" as const, coordinates: [[37, 55], [38, 56]] as [number, number][] },
    };
    expect(hasRoadGeometry(route)).toBe(false);
    expect(hasRoadGeometry({
      ...route,
      geometry: { type: "LineString", coordinates: [[37, 55], [37.5, 55.5], [38, 56]] },
    })).toBe(true);
  });
});
