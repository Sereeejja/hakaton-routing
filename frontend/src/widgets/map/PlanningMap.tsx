import { LocateFixed } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  LngLatBounds,
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  Popup,
  setWorkerUrl,
  type GeoJSONSource,
  type MapMouseEvent,
} from "maplibre-gl";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Feature, FeatureCollection, LineString, Point } from "geojson";
import type {
  Brigade,
  Coordinate,
  PlacementMode,
  PlannedRoute,
  PointDraft,
  ServiceRequest,
} from "../../shared/types/domain";
import { coordinateLabel, formatClock, shortAddress } from "../../shared/lib/format";
import { hasRoadGeometry } from "../../shared/lib/geometry";

setWorkerUrl(maplibreWorkerUrl);

const ROUTE_COLORS = ["#d9ff43", "#85a7ff", "#ff8e5b", "#61dca3", "#d793ff", "#ffd166"];
const MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";
const MOSCOW_CENTER: Coordinate = [37.6176, 55.7558];
const REQUEST_CLUSTER_SOURCE = "request-clusters";
const REQUEST_CLUSTER_LAYER = "request-cluster-bubbles";
const REQUEST_CLUSTER_COUNT_LAYER = "request-cluster-count";
const REQUEST_CLUSTER_SINGLE_LAYER = "request-cluster-single";
const REQUEST_MARKER_MIN_ZOOM = 13;

export function routeColor(index: number): string {
  return ROUTE_COLORS[index % ROUTE_COLORS.length];
}

function fitVisibleRoute(
  map: MapLibreMap,
  routes: PlannedRoute[],
  selectedRouteId: string | null,
  requests: ServiceRequest[],
  brigades: Brigade[],
  duration = 900,
) {
  const bounds = new LngLatBounds();
  const focusedRoute = routes.find((route) => route.engineer_id === selectedRouteId) ?? routes[0];
  if (hasRoadGeometry(focusedRoute)) {
    focusedRoute.geometry?.coordinates.forEach((coordinate) => bounds.extend(coordinate));
  }
  if (bounds.isEmpty()) {
    brigades.filter((brigade) => brigade.status === "available").forEach((brigade) =>
      bounds.extend([brigade.start_longitude, brigade.start_latitude]),
    );
    requests.filter((request) => request.status !== "canceled").forEach((request) =>
      bounds.extend([request.longitude, request.latitude]),
    );
  }
  if (!bounds.isEmpty()) {
    map.fitBounds(bounds, {
      padding: { top: 130, right: 90, bottom: 150, left: 90 },
      maxZoom: 15,
      duration,
    });
  }
}

interface CarPosition {
  coordinate: Coordinate;
  bearing: number;
}

interface PlanningMapProps {
  requests: ServiceRequest[];
  brigades: Brigade[];
  routes: PlannedRoute[];
  selectedRouteId: string | null;
  draft: PointDraft | null;
  placementMode: PlacementMode;
  carPosition: CarPosition | null;
  fitKey: string;
  onMapClick: (coordinate: Coordinate) => void;
  onSelectRoute: (engineerId: string) => void;
}

function popupContent(title: string, lines: string[]): HTMLElement {
  const root = document.createElement("div");
  root.className = "map-popup";
  const heading = document.createElement("strong");
  heading.textContent = title;
  root.append(heading);
  lines.forEach((line) => {
    const node = document.createElement("span");
    node.textContent = line;
    root.append(node);
  });
  return root;
}

export function PlanningMap({
  requests,
  brigades,
  routes,
  selectedRouteId,
  draft,
  placementMode,
  carPosition,
  fitKey,
  onMapClick,
  onSelectRoute,
}: PlanningMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const carMarkerRef = useRef<Marker | null>(null);
  const clickCallbackRef = useRef(onMapClick);
  const selectRouteRef = useRef(onSelectRoute);
  const fitKeyRef = useRef("");
  const routeLayerCountRef = useRef(0);
  const [loaded, setLoaded] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);

  useEffect(() => {
    clickCallbackRef.current = onMapClick;
    selectRouteRef.current = onSelectRoute;
  }, [onMapClick, onSelectRoute]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let map: MapLibreMap;
    try {
      map = new MapLibreMap({
        container: containerRef.current,
        style: MAP_STYLE,
        center: MOSCOW_CENTER,
        zoom: 11,
        minZoom: 3,
        maxZoom: 18,
        attributionControl: false,
        pitch: 0,
      });
    } catch (error) {
      setMapError(error instanceof Error ? `Карта не запустилась: ${error.message}` : "Карта не запустилась");
      return;
    }
    mapRef.current = map;
    map.addControl(new NavigationControl({ showCompass: false }), "bottom-right");
    map.on("style.load", () => setLoaded(true));
    map.on("error", (event) => {
      if (event.error?.message) setMapError("Часть картографических данных не загрузилась");
    });
    const handleClick = (event: MapMouseEvent) => {
      const clusterLayers = [REQUEST_CLUSTER_LAYER, REQUEST_CLUSTER_SINGLE_LAYER]
        .filter((layerID) => Boolean(map.getLayer(layerID)));
      const feature = clusterLayers.length
        ? map.queryRenderedFeatures(event.point, { layers: clusterLayers })[0]
        : undefined;
      if (feature) {
        const clusterID = feature.properties?.cluster_id;
        if (clusterID !== undefined) {
          const source = map.getSource(REQUEST_CLUSTER_SOURCE) as GeoJSONSource | undefined;
          void source?.getClusterExpansionZoom(Number(clusterID)).then((zoom) => {
            if (feature.geometry.type !== "Point") return;
            map.easeTo({ center: feature.geometry.coordinates as Coordinate, zoom, duration: 450 });
          });
        } else if (feature.geometry.type === "Point") {
          map.easeTo({ center: feature.geometry.coordinates as Coordinate, zoom: REQUEST_MARKER_MIN_ZOOM, duration: 450 });
        }
        return;
      }
      clickCallbackRef.current([event.lngLat.lng, event.lngLat.lat]);
    };
    map.on("click", handleClick);
    const syncRequestMarkerVisibility = () => {
      const visible = map.getZoom() >= REQUEST_MARKER_MIN_ZOOM;
      markersRef.current.forEach((marker) => {
        const element = marker.getElement();
        if (element.classList.contains("stop-marker")) {
          element.style.display = visible ? "" : "none";
        }
      });
    };
    map.on("zoom", syncRequestMarkerVisibility);

    const observer = new ResizeObserver(() => map.resize());
    observer.observe(containerRef.current);
    return () => {
      observer.disconnect();
      map.off("zoom", syncRequestMarkerVisibility);
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.getCanvas().style.cursor = placementMode ? "crosshair" : "crosshair";
  }, [placementMode]);

  const focusRoute = useCallback(() => {
    if (!mapRef.current) return;
    fitVisibleRoute(mapRef.current, routes, selectedRouteId, requests, brigades);
  }, [brigades, requests, routes, selectedRouteId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) return;
    const data: FeatureCollection<Point, { request_id: string; priority: string }> = {
      type: "FeatureCollection",
      features: requests
        .filter((request) => request.status !== "canceled")
        .map((request) => ({
          type: "Feature",
          properties: { request_id: request.id, priority: request.priority },
          geometry: { type: "Point", coordinates: [request.longitude, request.latitude] },
        })),
    };
    const existing = map.getSource(REQUEST_CLUSTER_SOURCE) as GeoJSONSource | undefined;
    if (existing) {
      existing.setData(data);
      return;
    }
    map.addSource(REQUEST_CLUSTER_SOURCE, {
      type: "geojson",
      data,
      cluster: true,
      clusterMaxZoom: REQUEST_MARKER_MIN_ZOOM - 1,
      clusterRadius: 58,
    });
    map.addLayer({
      id: REQUEST_CLUSTER_LAYER,
      type: "circle",
      source: REQUEST_CLUSTER_SOURCE,
      maxzoom: REQUEST_MARKER_MIN_ZOOM,
      filter: ["has", "point_count"],
      paint: {
        "circle-color": "#d9ff43",
        "circle-radius": ["step", ["get", "point_count"], 18, 10, 23, 30, 29],
        "circle-stroke-color": "#171a16",
        "circle-stroke-width": 3,
        "circle-opacity": 0.96,
      },
    });
    map.addLayer({
      id: REQUEST_CLUSTER_COUNT_LAYER,
      type: "symbol",
      source: REQUEST_CLUSTER_SOURCE,
      maxzoom: REQUEST_MARKER_MIN_ZOOM,
      filter: ["has", "point_count"],
      layout: {
        "text-field": ["get", "point_count_abbreviated"],
        "text-size": 12,
        "text-font": ["Noto Sans Bold"],
      },
      paint: { "text-color": "#171a16" },
    });
    map.addLayer({
      id: REQUEST_CLUSTER_SINGLE_LAYER,
      type: "circle",
      source: REQUEST_CLUSTER_SOURCE,
      maxzoom: REQUEST_MARKER_MIN_ZOOM,
      filter: ["!", ["has", "point_count"]],
      paint: {
        "circle-color": ["case", ["==", ["get", "priority"], "urgent"], "#ff7549", "#f8faf2"],
        "circle-radius": 8,
        "circle-stroke-color": "#171a16",
        "circle-stroke-width": 2,
      },
    });
  }, [loaded, requests]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) return;

    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = [];

    for (let routeIndex = 0; routeIndex < routeLayerCountRef.current; routeIndex += 1) {
      const sourceId = `route-source-${routeIndex}`;
      const casingId = `route-casing-${routeIndex}`;
      const lineId = `route-line-${routeIndex}`;
      if (map.getLayer(lineId)) map.removeLayer(lineId);
      if (map.getLayer(casingId)) map.removeLayer(casingId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
    }
    routeLayerCountRef.current = routes.length;

    routes.forEach((route, routeIndex) => {
      const sourceId = `route-source-${routeIndex}`;
      const casingId = `route-casing-${routeIndex}`;
      const lineId = `route-line-${routeIndex}`;
      if (!hasRoadGeometry(route) || !route.geometry) return;
      const feature: Feature<LineString> = {
        type: "Feature",
        properties: {},
        geometry: route.geometry,
      };
      map.addSource(sourceId, { type: "geojson", data: feature });
      const selected = route.engineer_id === selectedRouteId;
      map.addLayer({
        id: casingId,
        type: "line",
        source: sourceId,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#171a16",
          "line-width": selected ? 14 : 7,
          "line-opacity": selected ? 0.9 : 0.2,
        },
      });
      map.addLayer({
        id: lineId,
        type: "line",
        source: sourceId,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": routeColor(routeIndex),
          "line-width": selected ? 8 : 3,
          "line-opacity": selected ? 1 : 0.3,
        },
      });
    });

    const plannedStops = new Map<
      string,
      { route: PlannedRoute; routeIndex: number; stopIndex: number; isFinish: boolean }
    >();
    routes.forEach((route, routeIndex) => {
      route.stops.forEach((stop, stopIndex) => {
        plannedStops.set(stop.job_id, {
          route,
          routeIndex,
          stopIndex,
          isFinish: stopIndex === route.stops.length - 1,
        });
      });
    });

    const visibleBrigades = routes.length
      ? brigades.filter((brigade) => routes.some((route) => route.engineer_id === brigade.id && route.stops.length > 0))
      : brigades.filter((brigade) => brigade.status === "available");
    visibleBrigades.forEach((brigade) => {
      const routeIndex = routes.findIndex((route) => route.engineer_id === brigade.id);
      const element = document.createElement("button");
      element.type = "button";
      const secondary = selectedRouteId && brigade.id !== selectedRouteId ? " secondary-marker" : "";
      element.className = `map-marker depot-marker${brigade.status !== "available" ? " is-muted" : ""}${secondary}`;
      if (routeIndex >= 0) element.style.setProperty("--marker-color", routeColor(routeIndex));
      element.innerHTML = '<span class="marker-core">S</span><span class="marker-caption">СТАРТ</span>';
      element.setAttribute("aria-label", `Старт: ${brigade.name}`);
      element.addEventListener("click", (event) => {
        event.stopPropagation();
        if (routeIndex >= 0) selectRouteRef.current(brigade.id);
      });
      const marker = new Marker({ element, anchor: "bottom" })
        .setLngLat([brigade.start_longitude, brigade.start_latitude])
        .setPopup(
          new Popup({ offset: 22, closeButton: false }).setDOMContent(
            popupContent(`Старт · ${brigade.name}`, [
              brigade.start_address,
              `График ${brigade.work_schedule ?? "2/2"} · ${brigade.shift_start}–${brigade.shift_end}`,
            ]),
          ),
        )
        .addTo(map);
      markersRef.current.push(marker);
    });

    requests
      .filter((request) => request.status !== "canceled")
      .forEach((request) => {
        const planned = plannedStops.get(request.id);
        const element = document.createElement("button");
        element.type = "button";
        const finishClass = planned?.isFinish ? " finish-marker" : "";
        const pendingClass = planned ? "" : " pending-marker";
        const urgentClass = request.priority === "urgent" ? " urgent-marker" : "";
        const secondaryClass = planned && selectedRouteId && planned.route.engineer_id !== selectedRouteId ? " secondary-marker" : "";
        element.className = `map-marker stop-marker${finishClass}${pendingClass}${urgentClass}${secondaryClass}`;
        element.style.display = map.getZoom() >= REQUEST_MARKER_MIN_ZOOM ? "" : "none";
        if (planned) element.style.setProperty("--marker-color", routeColor(planned.routeIndex));
        element.innerHTML = planned?.isFinish
          ? '<span class="marker-core"><span class="finish-grid"></span></span><span class="marker-caption">ФИНИШ</span>'
          : `<span class="marker-core">${planned ? planned.stopIndex + 1 : "•"}</span>`;
        element.setAttribute("aria-label", planned ? `Остановка ${planned.stopIndex + 1}: ${request.address}` : request.address);
        element.addEventListener("click", (event) => {
          event.stopPropagation();
          if (planned) selectRouteRef.current(planned.route.engineer_id);
        });
        const stop = planned?.route.stops[planned.stopIndex];
        const lines = stop
          ? [request.address, `${formatClock(stop.service_start_minutes)}–${formatClock(stop.service_end_minutes)}`]
          : [request.address, `${request.window_start}–${request.window_end} · ещё не назначена`];
        const marker = new Marker({ element, anchor: "bottom" })
          .setLngLat([request.longitude, request.latitude])
          .setPopup(
            new Popup({ offset: 18, closeButton: false }).setDOMContent(
              popupContent(planned ? `Остановка ${planned.stopIndex + 1}` : "Заявка", lines),
            ),
          )
          .addTo(map);
        markersRef.current.push(marker);
      });

    if (draft) {
      const element = document.createElement("div");
      element.className = `draft-marker ${draft.kind}`;
      element.innerHTML = '<span></span>';
      const marker = new Marker({ element, anchor: "center" })
        .setLngLat([draft.longitude, draft.latitude])
        .setPopup(
          new Popup({ offset: 18, closeButton: false }).setDOMContent(
            popupContent(draft.kind === "brigade" ? "Новый старт" : "Новая заявка", [
              coordinateLabel(draft.latitude, draft.longitude),
              "Заполните карточку справа",
            ]),
          ),
        )
        .addTo(map);
      markersRef.current.push(marker);
    }

    if (fitKey && fitKeyRef.current !== fitKey) {
      fitKeyRef.current = fitKey;
      fitVisibleRoute(map, routes, selectedRouteId, requests, brigades);
    }
  }, [brigades, draft, fitKey, loaded, requests, routes, selectedRouteId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) return;
    if (!carPosition) {
      carMarkerRef.current?.remove();
      carMarkerRef.current = null;
      return;
    }
    if (!carMarkerRef.current) {
      const element = document.createElement("div");
      element.className = "car-marker";
      element.innerHTML = '<span class="car-pulse"></span><span class="car-body"><i></i><i></i></span>';
      carMarkerRef.current = new Marker({ element, anchor: "center", rotationAlignment: "map" })
        .setLngLat(carPosition.coordinate)
        .addTo(map);
    }
    carMarkerRef.current.setLngLat(carPosition.coordinate).setRotation(carPosition.bearing);
  }, [carPosition, loaded]);

  return (
    <div className="map-shell">
      <div ref={containerRef} className="map-canvas" aria-label="Интерактивная карта маршрутов" />
      <div className="map-vignette" aria-hidden="true" />
      {mapError && <div className="map-error">{mapError}</div>}
      <div className="map-legend" aria-label="Обозначения карты">
        <span><i className="legend-depot">S</i> старт</span>
        <span><i className="legend-stop">1</i> остановка</span>
        <span><i className="legend-finish" /> финиш</span>
      </div>
      {!!routes.length && (
        <button type="button" className="route-focus-button" onClick={focusRoute}>
          <LocateFixed size={14} /> Маршрут в кадр
        </button>
      )}
      <div className="map-credit">
        <a href="https://openfreemap.org" target="_blank" rel="noreferrer">OpenFreeMap</a>
        <span>·</span>
        <a href="https://openmaptiles.org" target="_blank" rel="noreferrer">© OpenMapTiles</a>
        <span>·</span>
        <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap</a>
      </div>
      {!routes.length && (
        <div className="map-empty-state">
          <span>КЛИК ПО КАРТЕ</span>
          <strong>Поставьте первую точку</strong>
          <p>Добавьте старт бригады и заявки, затем запустите расчёт.</p>
        </div>
      )}
    </div>
  );
}
