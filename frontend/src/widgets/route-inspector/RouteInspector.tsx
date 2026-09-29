import {
  AlertCircle,
  ArrowDown,
  CarFront,
  CheckCircle2,
  Clock3,
  Flag,
  MapPinned,
  Route as RouteIcon,
  TimerReset,
} from "lucide-react";
import { formatClock, formatDistance, shortAddress } from "../../shared/lib/format";
import { hasRoadGeometry } from "../../shared/lib/geometry";
import type { Brigade, Plan, PlannedRoute, ServiceRequest } from "../../shared/types/domain";
import { routeColor } from "../map/PlanningMap";

interface RouteInspectorProps {
  plan: Plan | null;
  requests: ServiceRequest[];
  brigades: Brigade[];
  selectedRouteId: string | null;
  isApplyingEvent: boolean;
  onSelectRoute: (engineerId: string) => void;
  onApplyEvent: (type: string, payload: Record<string, string>) => void;
}

function RouteTimeline({
  route,
  brigade,
  requests,
  explanations,
  onApplyEvent,
}: {
  route: PlannedRoute;
  brigade?: Brigade;
  requests: ServiceRequest[];
  explanations: Record<string, string>;
  onApplyEvent: (type: string, payload: Record<string, string>) => void;
}) {
  const requestById = new Map(requests.map((request) => [request.id, request]));
  return (
    <div className="route-timeline">
      <div className="timeline-node start-node">
        <i>S</i>
        <div><span>СТАРТ · {formatClock(route.departure_minutes)}</span><strong>{brigade?.start_address ?? "База бригады"}</strong></div>
      </div>
      {route.stops.map((stop, index) => {
        const request = requestById.get(stop.job_id);
        const isFinish = index === route.stops.length - 1;
        const explanation = explanations[stop.job_id]?.replace(
          `инженеру ${route.engineer_id}`,
          `бригаде ${brigade?.name ?? route.engineer_id}`,
        );
        return (
          <div className={`timeline-node ${isFinish ? "finish-node" : ""}`} key={stop.job_id}>
            <i>{isFinish ? <Flag size={12} /> : index + 1}</i>
            <div>
              <span>{isFinish ? "ФИНИШ" : `ОСТАНОВКА ${index + 1}`} · {formatClock(stop.service_start_minutes)}</span>
              <strong title={request?.address}>{shortAddress(request?.address ?? stop.job_id, 42)}</strong>
              <small>{stop.travel_minutes} мин в пути · работа до {formatClock(stop.service_end_minutes)}</small>
              {explanation && (
                <details className="assignment-explanation">
                  <summary>Почему назначено сюда</summary>
                  <p>{explanation}</p>
                </details>
              )}
              <button type="button" onClick={() => onApplyEvent("cancel_request", { request_id: stop.job_id })}>Отменить заявку</button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function RouteInspector({
  plan,
  requests,
  brigades,
  selectedRouteId,
  isApplyingEvent,
  onSelectRoute,
  onApplyEvent,
}: RouteInspectorProps) {
  const solution = plan?.solution;
  const routes = solution?.routes.filter((route) => route.stops.length > 0) ?? [];
  const selectedRoute = routes.find((route) => route.engineer_id === selectedRouteId) ?? routes[0];
  const selectedIndex = routes.findIndex((route) => route.engineer_id === selectedRoute?.engineer_id);
  const selectedBrigade = brigades.find((brigade) => brigade.id === selectedRoute?.engineer_id);

  if (!solution) {
    return (
      <aside className="inspector empty-inspector">
        <div className="empty-route-visual"><RouteIcon size={34} /><i /><i /><Flag size={20} /></div>
        <span>ПЛАН ЕЩЁ НЕ ПОСТРОЕН</span>
        <h2>Сначала точки,<br />потом магия.</h2>
        <p>Нужна хотя бы одна доступная бригада и одна заявка. Старт и финиш будут отмечены отдельно.</p>
        <div className="how-it-works">
          <div><b>1</b><span>Поставьте старт бригады</span></div>
          <ArrowDown size={13} />
          <div><b>2</b><span>Добавьте заявки кликами</span></div>
          <ArrowDown size={13} />
          <div><b>3</b><span>Нажмите «Построить»</span></div>
        </div>
      </aside>
    );
  }

  return (
    <aside className="inspector route-inspector">
      <header className="route-summary-header">
        <div><span>ПОСЛЕДНИЙ РАСЧЁТ</span><h2>План готов</h2></div>
        <div className={`plan-status ${solution.status}`}><CheckCircle2 size={13} /> Готово</div>
      </header>

      <div className="metric-grid">
        <div><MapPinned size={15} /><span>Выполнено</span><strong>{solution.metrics.completed_jobs}<small> заявок</small></strong></div>
        <div><RouteIcon size={15} /><span>Пробег</span><strong>{formatDistance(solution.metrics.total_distance_km)}<small> км</small></strong></div>
        <div><Clock3 size={15} /><span>В пути</span><strong>{solution.metrics.total_travel_minutes}<small> мин</small></strong></div>
        <div><CarFront size={15} /><span>Бригад</span><strong>{solution.metrics.active_engineers}<small> в пути</small></strong></div>
      </div>

      {solution.baseline && (
        <section className="baseline-comparison">
          <header><span>СРАВНЕНИЕ С BASELINE</span><small>порядок входа · первый допустимый инженер</small></header>
          <div>
            <span>Метрика</span><b>План</b><b>Baseline</b>
            <span>Выполнено</span><strong>{solution.metrics.completed_jobs}</strong><em>{solution.baseline.metrics.completed_jobs}</em>
            <span>Бригад</span><strong>{solution.metrics.active_engineers}</strong><em>{solution.baseline.metrics.active_engineers}</em>
            <span>Пробег</span><strong>{formatDistance(solution.metrics.total_distance_km)} км</strong><em>{formatDistance(solution.baseline.metrics.total_distance_km)} км</em>
          </div>
        </section>
      )}

      {!!solution.warnings?.length && (
        <div className="route-warning"><AlertCircle size={16} /><div><strong>Есть предупреждение</strong><span>{solution.warnings[0]}</span></div></div>
      )}

      <section className="routes-section">
        <div className="section-label"><span>МАРШРУТЫ · {routes.length}</span><small>выберите для просмотра</small></div>
        <div className="route-switcher">
          {routes.map((route, index) => {
            const brigade = brigades.find((item) => item.id === route.engineer_id);
            return (
              <button
                type="button"
                className={route.engineer_id === selectedRoute?.engineer_id ? "active" : ""}
                onClick={() => onSelectRoute(route.engineer_id)}
                key={route.engineer_id}
                style={{ "--route-color": routeColor(index) } as React.CSSProperties}
              >
                <i /><span><strong>{brigade?.name ?? `Маршрут ${index + 1}`}</strong><small>{route.stops.length} точек · {formatDistance(route.total_distance_km)} км</small></span>
              </button>
            );
          })}
        </div>
      </section>

      {selectedRoute && (
        <section className="selected-route" style={{ "--route-color": routeColor(Math.max(0, selectedIndex)) } as React.CSSProperties}>
          <header>
            <div className="route-car"><CarFront size={18} /></div>
            <div><span>ВЫБРАННЫЙ МАРШРУТ</span><h3>{selectedBrigade?.name ?? selectedRoute.engineer_id}</h3></div>
            <strong>{formatClock(selectedRoute.departure_minutes)} → {formatClock(selectedRoute.finish_minutes)}</strong>
          </header>
          {!hasRoadGeometry(selectedRoute) && (
            <div className="geometry-missing"><AlertCircle size={15} />Дорожная геометрия не загрузилась. Прямая линия намеренно не рисуется.</div>
          )}
          <RouteTimeline
            route={selectedRoute}
            brigade={selectedBrigade}
            requests={requests}
            explanations={solution.explanations ?? {}}
            onApplyEvent={onApplyEvent}
          />
          <button
            type="button"
            className="unavailable-button"
            disabled={isApplyingEvent}
            onClick={() => onApplyEvent("brigade_unavailable", { brigade_id: selectedRoute.engineer_id })}
          >
            <TimerReset size={14} /> Бригада недоступна — перестроить
          </button>
        </section>
      )}

      {!!solution.unassigned?.length && (
        <section className="unassigned-block">
          <strong><AlertCircle size={15} /> Не назначено: {solution.unassigned.length}</strong>
          {solution.unassigned.map((item) => <span key={item.job_id}>{shortAddress(requests.find((request) => request.id === item.job_id)?.address ?? item.job_id)} · {item.message}</span>)}
        </section>
      )}

      <footer className="solver-footer">План учитывает временные окна, навыки бригад и дорожные маршруты.</footer>
    </aside>
  );
}
