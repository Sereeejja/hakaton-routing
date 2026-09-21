import type { Coordinate, PlannedRoute } from "../types/domain";

const EARTH_RADIUS_KM = 6371.0088;

function radians(degrees: number): number {
  return (degrees * Math.PI) / 180;
}

export function haversineDistance(a: Coordinate, b: Coordinate): number {
  const latitudeDelta = radians(b[1] - a[1]);
  const longitudeDelta = radians(b[0] - a[0]);
  const latitudeA = radians(a[1]);
  const latitudeB = radians(b[1]);
  const value =
    Math.sin(latitudeDelta / 2) ** 2 +
    Math.cos(latitudeA) * Math.cos(latitudeB) * Math.sin(longitudeDelta / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(value));
}

export function bearingBetween(a: Coordinate, b: Coordinate): number {
  const longitudeDelta = radians(b[0] - a[0]);
  const latitudeA = radians(a[1]);
  const latitudeB = radians(b[1]);
  const y = Math.sin(longitudeDelta) * Math.cos(latitudeB);
  const x =
    Math.cos(latitudeA) * Math.sin(latitudeB) -
    Math.sin(latitudeA) * Math.cos(latitudeB) * Math.cos(longitudeDelta);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

export interface RoutePosition {
  coordinate: Coordinate;
  bearing: number;
  distanceKm: number;
}

export function hasRoadGeometry(route: PlannedRoute | undefined): boolean {
  const coordinateCount = route?.geometry?.coordinates?.length ?? 0;
  if (!route || coordinateCount < 2) return false;
  // Legacy/fallback geometry contains exactly depot + stop coordinates and is
  // therefore a set of straight chords, not a route following the road graph.
  return coordinateCount > route.stops.length + 1;
}

export function pointAlongRoute(coordinates: Coordinate[], progress: number): RoutePosition | null {
  if (!coordinates.length) return null;
  if (coordinates.length === 1) {
    return { coordinate: coordinates[0], bearing: 0, distanceKm: 0 };
  }

  const segmentLengths = coordinates.slice(1).map((coordinate, index) =>
    haversineDistance(coordinates[index], coordinate),
  );
  const totalDistance = segmentLengths.reduce((sum, value) => sum + value, 0);
  const targetDistance = Math.min(1, Math.max(0, progress)) * totalDistance;
  let travelled = 0;

  for (let index = 0; index < segmentLengths.length; index += 1) {
    const segmentLength = segmentLengths[index];
    if (travelled + segmentLength >= targetDistance || index === segmentLengths.length - 1) {
      const start = coordinates[index];
      const end = coordinates[index + 1];
      const segmentProgress = segmentLength === 0 ? 0 : (targetDistance - travelled) / segmentLength;
      return {
        coordinate: [
          start[0] + (end[0] - start[0]) * segmentProgress,
          start[1] + (end[1] - start[1]) * segmentProgress,
        ],
        bearing: bearingBetween(start, end),
        distanceKm: targetDistance,
      };
    }
    travelled += segmentLength;
  }
  return null;
}
