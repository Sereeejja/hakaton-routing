import { MousePointer2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRoutePlayback } from "../features/route-animation/useRoutePlayback";
import { api } from "../shared/api/client";
import { hasRoadGeometry } from "../shared/lib/geometry";
import type {
  Brigade,
  Coordinate,
  CreateBrigadeInput,
  CreateRequestInput,
  Plan,
  PlannedRoute,
  PlacementMode,
  PointDraft,
  PointKind,
  ServiceRequest,
} from "../shared/types/domain";
import { PlanningMap } from "../widgets/map/PlanningMap";
import { PlaybackBar } from "../widgets/playback/PlaybackBar";
import { PlannerToolbar } from "../widgets/planner/PlannerToolbar";
import { PointEditor } from "../widgets/point-editor/PointEditor";
import { RouteInspector } from "../widgets/route-inspector/RouteInspector";
import { Sidebar } from "../widgets/sidebar/Sidebar";
import "./styles.css";

interface ToastState {
  message: string;
  tone: "success" | "error";
}

function preferredRouteId(routes: PlannedRoute[]): string | null {
  if (!routes.length) return null;
  return [...routes]
    .sort((left, right) => {
      const leftIsOutlier = left.total_distance_km > 100 ? 1 : 0;
      const rightIsOutlier = right.total_distance_km > 100 ? 1 : 0;
      return leftIsOutlier - rightIsOutlier || right.stops.length - left.stops.length || left.total_distance_km - right.total_distance_km;
    })[0].engineer_id;
}

const demoBrigades: CreateBrigadeInput[] = [
  {
    name: "Бригада Центр-1",
    start_address: "Каланчёвская улица, 15",
    start_latitude: 55.7752,
    start_longitude: 37.6521,
    shift_start: "09:00",
    shift_end: "18:00",
    work_schedule: "5/2",
    skills: ["connection", "local"],
    transport: "car",
  },
  {
    name: "Аварийная бригада",
    start_address: "Нижегородская улица, 32",
    start_latitude: 55.7315,
    start_longitude: 37.7066,
    shift_start: "10:00",
    shift_end: "22:00",
    work_schedule: "2/2",
    skills: ["local", "emergency"],
    transport: "car",
  },
];

const demoRequests: CreateRequestInput[] = [
  { address: "Мясницкая улица, 18", latitude: 55.7631, longitude: 37.6354, service_minutes: 70, window_start: "10:00", window_end: "13:00", required_skill: "connection", priority: "normal" },
  { address: "улица Покровка, 31", latitude: 55.7593, longitude: 37.6534, service_minutes: 30, window_start: "11:00", window_end: "15:00", required_skill: "local", priority: "normal" },
  { address: "Волочаевская улица, 12", latitude: 55.751, longitude: 37.6808, service_minutes: 80, window_start: "12:00", window_end: "15:00", required_skill: "emergency", priority: "urgent" },
  { address: "Бауманская улица, 44", latitude: 55.7723, longitude: 37.6787, service_minutes: 70, window_start: "14:00", window_end: "18:00", required_skill: "connection", priority: "normal" },
];

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Произошла неизвестная ошибка";
}

export default function App() {
  const [requests, setRequests] = useState<ServiceRequest[]>([]);
  const [brigades, setBrigades] = useState<Brigade[]>([]);
  const [activePlan, setActivePlan] = useState<Plan | null>(null);
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [draft, setDraft] = useState<PointDraft | null>(null);
  const [placementMode, setPlacementMode] = useState<PlacementMode>(null);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isPlanning, setIsPlanning] = useState(false);
  const [isLoadingDemo, setIsLoadingDemo] = useState(false);
  const [deletingRequestId, setDeletingRequestId] = useState<string | null>(null);
  const [isClearingRequests, setIsClearingRequests] = useState(false);
  const [isApplyingEvent, setIsApplyingEvent] = useState(false);
  const [toast, setToast] = useState<ToastState | null>(null);

  const showToast = useCallback((message: string, tone: ToastState["tone"] = "success") => {
    setToast({ message, tone });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const refresh = useCallback(async (quiet = false) => {
    if (!quiet) setIsRefreshing(true);
    try {
      const [requestItems, brigadeItems, planItems] = await Promise.all([
        api.requests.list(),
        api.brigades.list(),
        api.plans.list(),
      ]);
      setRequests(requestItems);
      setBrigades(brigadeItems);
      setApiOnline(true);
      const newest = planItems.find((plan) => plan.solution);
      if (newest) setActivePlan((current) => current ?? newest);
    } catch (error) {
      setApiOnline(false);
      showToast(errorMessage(error), "error");
    } finally {
      setIsRefreshing(false);
    }
  }, [showToast]);

  useEffect(() => {
    void refresh(true);
  }, [refresh]);

  const routes = useMemo(
    () => activePlan?.solution?.routes.filter((route) => route.stops.length > 0) ?? [],
    [activePlan],
  );

  useEffect(() => {
    if (!routes.length) {
      setSelectedRouteId(null);
      return;
    }
    if (!routes.some((route) => route.engineer_id === selectedRouteId)) {
      setSelectedRouteId(preferredRouteId(routes));
    }
  }, [routes, selectedRouteId]);

  const selectedRoute = routes.find((route) => route.engineer_id === selectedRouteId) ?? routes[0];
  const selectedBrigade = brigades.find((brigade) => brigade.id === selectedRoute?.engineer_id);
  const routeCoordinates = hasRoadGeometry(selectedRoute) ? selectedRoute?.geometry?.coordinates ?? [] : [];
  const playback = useRoutePlayback(routeCoordinates, `${activePlan?.id ?? "none"}:${selectedRoute?.engineer_id ?? "none"}`);

  const handleMapClick = useCallback((coordinate: Coordinate) => {
    setDraft({
      kind: placementMode ?? "request",
      longitude: coordinate[0],
      latitude: coordinate[1],
    });
  }, [placementMode]);

  const handlePlacementMode = useCallback((mode: PlacementMode) => {
    setPlacementMode(mode);
    if (mode) setDraft(null);
  }, []);

  const changeDraftKind = (kind: PointKind) => {
    setDraft((current) => current ? { ...current, kind } : current);
  };

  const createRequest = async (input: CreateRequestInput) => {
    setIsSaving(true);
    try {
      const created = await api.requests.create(input);
      setRequests((items) => [created, ...items]);
      setDraft(null);
      setPlacementMode(null);
      showToast("Заявка добавлена. Поставьте ещё точки или запустите маршрут.");
    } catch (error) {
      showToast(errorMessage(error), "error");
    } finally {
      setIsSaving(false);
    }
  };

  const createBrigade = async (input: CreateBrigadeInput) => {
    setIsSaving(true);
    try {
      const created = await api.brigades.create(input);
      setBrigades((items) => [created, ...items]);
      setDraft(null);
      setPlacementMode(null);
      showToast("Старт бригады добавлен и отмечен буквой S.");
    } catch (error) {
      showToast(errorMessage(error), "error");
    } finally {
      setIsSaving(false);
    }
  };

  const runPlan = async () => {
    setIsPlanning(true);
    try {
      const plan = await api.plans.create({});
      setActivePlan(plan);
      setSelectedRouteId(preferredRouteId(plan.solution?.routes.filter((route) => route.stops.length > 0) ?? []));
      setDraft(null);
      showToast("Дорожные маршруты рассчитаны. Анимация запущена.");
    } catch (error) {
      showToast(errorMessage(error), "error");
    } finally {
      setIsPlanning(false);
    }
  };

  const loadDemo = async () => {
    setIsLoadingDemo(true);
    try {
      await Promise.all([
        ...demoBrigades.map((item) => api.brigades.create(item)),
        ...demoRequests.map((item) => api.requests.create(item)),
      ]);
      await refresh(true);
      showToast("Демо-точки добавлены. Теперь нажмите «Построить маршруты».");
    } catch (error) {
      showToast(errorMessage(error), "error");
    } finally {
      setIsLoadingDemo(false);
    }
  };

  const deleteRequest = async (id: string) => {
    setDeletingRequestId(id);
    try {
      await api.requests.delete(id);
      setRequests((items) => items.filter((item) => item.id !== id));
      setActivePlan(null);
      setSelectedRouteId(null);
      showToast("Заявка удалена. Связанные с ней старые планы сброшены.");
    } catch (error) {
      showToast(errorMessage(error), "error");
    } finally {
      setDeletingRequestId(null);
    }
  };

  const clearRequests = async () => {
    if (!window.confirm(`Удалить все заявки (${requests.length})? Бригады останутся.`)) return;
    setIsClearingRequests(true);
    try {
      const result = await api.requests.clear();
      setRequests([]);
      setActivePlan(null);
      setSelectedRouteId(null);
      showToast(`Удалено заявок: ${result.deleted_count}.`);
    } catch (error) {
      showToast(errorMessage(error), "error");
    } finally {
      setIsClearingRequests(false);
    }
  };

  const applyEvent = async (type: string, payload: Record<string, string>) => {
    if (!activePlan) return;
    setIsApplyingEvent(true);
    try {
      const result = await api.plans.applyEvent(activePlan.id, type, payload);
      setActivePlan(result.plan);
      await refresh(true);
      showToast("Изменение применено, маршрут перестроен.");
    } catch (error) {
      showToast(errorMessage(error), "error");
    } finally {
      setIsApplyingEvent(false);
    }
  };

  const activeRequests = requests.filter((request) => request.status === "pending" || request.status === "planned");
  const availableBrigades = brigades.filter((brigade) => brigade.status === "available");
  const canPlan = activeRequests.length > 0 && availableBrigades.length > 0;
  const fitKey = activePlan
    ? `${activePlan.id}:${selectedRouteId ?? routes[0]?.engineer_id ?? "route"}`
    : `entities:${requests.length}:${brigades.length}`;

  return (
    <div className="app-shell">
      <Sidebar
        requests={requests}
        brigades={brigades}
        placementMode={placementMode}
        apiOnline={apiOnline}
        isRefreshing={isRefreshing}
        isLoadingDemo={isLoadingDemo}
        deletingRequestId={deletingRequestId}
        isClearingRequests={isClearingRequests}
        onPlacementMode={handlePlacementMode}
        onRefresh={() => void refresh()}
        onLoadDemo={() => void loadDemo()}
        onDeleteRequest={(id) => void deleteRequest(id)}
        onClearRequests={() => void clearRequests()}
      />

      <main className="map-workspace">
        <PlanningMap
          requests={requests}
          brigades={brigades}
          routes={routes}
          selectedRouteId={selectedRouteId}
          draft={draft}
          placementMode={placementMode}
          carPosition={playback.position}
          fitKey={fitKey}
          onMapClick={handleMapClick}
          onSelectRoute={setSelectedRouteId}
        />
        <PlannerToolbar isPlanning={isPlanning} canPlan={canPlan} onPlan={() => void runPlan()} />
        <div className={`map-instruction ${placementMode ? "active" : ""}`}>
          <MousePointer2 size={16} />
          <span>{placementMode === "brigade" ? "Кликните на карту — здесь будет старт бригады" : placementMode === "request" ? "Кликните на карту — здесь будет новая заявка" : "Клик по карте добавляет заявку"}</span>
          {placementMode && <button type="button" onClick={() => setPlacementMode(null)} aria-label="Отменить"><X size={14} /></button>}
        </div>
        {hasRoadGeometry(selectedRoute) && selectedRoute?.geometry?.coordinates && (
          <PlaybackBar
            route={selectedRoute}
            brigade={selectedBrigade}
            progress={playback.progress}
            isPlaying={playback.isPlaying}
            speed={playback.speed}
            onPlayPause={playback.playPause}
            onRestart={playback.restart}
            onSeek={playback.seek}
            onSpeed={playback.setSpeed}
          />
        )}
      </main>

      {draft ? (
        <PointEditor
          key={`${draft.latitude}:${draft.longitude}`}
          draft={draft}
          isSaving={isSaving}
          onChangeKind={changeDraftKind}
          onCreateRequest={createRequest}
          onCreateBrigade={createBrigade}
          onClose={() => setDraft(null)}
        />
      ) : (
        <RouteInspector
          plan={activePlan}
          requests={requests}
          brigades={brigades}
          selectedRouteId={selectedRouteId}
          isApplyingEvent={isApplyingEvent}
          onSelectRoute={setSelectedRouteId}
          onApplyEvent={(type, payload) => void applyEvent(type, payload)}
        />
      )}

      {toast && (
        <div className={`toast ${toast.tone}`} role="status">
          <i />
          <span>{toast.message}</span>
          <button type="button" onClick={() => setToast(null)} aria-label="Закрыть"><X size={14} /></button>
        </div>
      )}
    </div>
  );
}
