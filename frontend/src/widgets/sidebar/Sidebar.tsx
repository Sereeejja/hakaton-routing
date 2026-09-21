import {
  AlertTriangle,
  ArrowUpRight,
  BriefcaseBusiness,
  CarFront,
  CirclePlus,
  Crosshair,
  Database,
  MapPin,
  RefreshCw,
  Route,
  Trash2,
  Users,
} from "lucide-react";
import { useState } from "react";
import { formatSkill, shortAddress } from "../../shared/lib/format";
import type { Brigade, PlacementMode, ServiceRequest } from "../../shared/types/domain";

interface SidebarProps {
  requests: ServiceRequest[];
  brigades: Brigade[];
  placementMode: PlacementMode;
  apiOnline: boolean | null;
  isRefreshing: boolean;
  isLoadingDemo: boolean;
  deletingRequestId: string | null;
  isClearingRequests: boolean;
  onPlacementMode: (mode: PlacementMode) => void;
  onRefresh: () => void;
  onLoadDemo: () => void;
  onDeleteRequest: (id: string) => void;
  onClearRequests: () => void;
}

type Tab = "requests" | "brigades";

export function Sidebar({
  requests,
  brigades,
  placementMode,
  apiOnline,
  isRefreshing,
  isLoadingDemo,
  deletingRequestId,
  isClearingRequests,
  onPlacementMode,
  onRefresh,
  onLoadDemo,
  onDeleteRequest,
  onClearRequests,
}: SidebarProps) {
  const [tab, setTab] = useState<Tab>("requests");
  const activeRequests = requests.filter((request) => request.status === "pending" || request.status === "planned");
  const availableBrigades = brigades.filter((brigade) => brigade.status === "available");

  return (
    <aside className="sidebar">
      <header className="brand-row">
        <div className="brand-mark"><Route size={18} strokeWidth={2.5} /></div>
        <div className="brand-copy">
          <strong>routecraft</strong>
          <span>dispatch studio</span>
        </div>
        <div className={`api-indicator ${apiOnline === false ? "offline" : apiOnline ? "online" : ""}`}>
          <i />
          {apiOnline === false ? "offline" : apiOnline ? "live" : "…"}
        </div>
      </header>

      <section className="sidebar-intro">
        <p>Москва · сегодня</p>
        <h1>Соберите точки.<br />Запустите маршрут.</h1>
        <span>Клик по карте открывает карточку новой точки — координаты вводить руками не нужно.</span>
      </section>

      <div className="point-actions">
        <button
          type="button"
          className={`point-action primary ${placementMode === "request" ? "active" : ""}`}
          onClick={() => onPlacementMode(placementMode === "request" ? null : "request")}
        >
          <span><MapPin size={18} /></span>
          <div><strong>Добавить заявку</strong><small>кликните точку на карте</small></div>
          <Crosshair size={17} />
        </button>
        <button
          type="button"
          className={`point-action ${placementMode === "brigade" ? "active" : ""}`}
          onClick={() => onPlacementMode(placementMode === "brigade" ? null : "brigade")}
        >
          <span><CarFront size={18} /></span>
          <div><strong>Добавить старт</strong><small>база новой бригады</small></div>
          <CirclePlus size={17} />
        </button>
      </div>

      <div className="entity-tabs" role="tablist">
        <button type="button" className={tab === "requests" ? "active" : ""} onClick={() => setTab("requests")}>
          Заявки <b>{activeRequests.length}</b>
        </button>
        <button type="button" className={tab === "brigades" ? "active" : ""} onClick={() => setTab("brigades")}>
          Бригады <b>{availableBrigades.length}</b>
        </button>
        <button type="button" className="icon-tab" onClick={onRefresh} aria-label="Обновить данные">
          <RefreshCw size={14} className={isRefreshing ? "spin" : ""} />
        </button>
      </div>

      <div className="entity-list">
        {tab === "requests" && activeRequests.map((request) => (
          <article className="entity-card request-card" key={request.id}>
            <div className={`entity-index ${request.priority === "urgent" ? "urgent" : ""}`}>
              {request.priority === "urgent" ? <AlertTriangle size={13} /> : <MapPin size={13} />}
            </div>
            <div className="entity-copy">
              <strong title={request.address}>{shortAddress(request.address)}</strong>
              <span>{request.window_start}–{request.window_end} · {request.service_minutes} мин</span>
              <small>{formatSkill(request.required_skill)}</small>
            </div>
            <button
              type="button"
              className="delete-request-button"
              disabled={deletingRequestId === request.id || isClearingRequests}
              onClick={() => onDeleteRequest(request.id)}
              aria-label={`Удалить заявку ${request.address}`}
              title="Удалить заявку"
            >
              <Trash2 size={13} />
            </button>
          </article>
        ))}
        {tab === "requests" && !activeRequests.length && (
          <div className="list-empty"><MapPin size={22} /><strong>Заявок пока нет</strong><span>Нажмите «Добавить заявку» и поставьте точку.</span></div>
        )}

        {tab === "brigades" && availableBrigades.map((brigade) => (
          <article className="entity-card brigade-card" key={brigade.id}>
            <div className="entity-index depot">S</div>
            <div className="entity-copy">
              <strong>{brigade.name}</strong>
              <span>{shortAddress(brigade.start_address, 34)}</span>
              <small>{brigade.shift_start}–{brigade.shift_end} · {brigade.transport}</small>
            </div>
            <i className="status-dot available" />
          </article>
        ))}
        {tab === "brigades" && !availableBrigades.length && (
          <div className="list-empty"><Users size={22} /><strong>Нет доступных бригад</strong><span>Добавьте старт бригады на карте.</span></div>
        )}
      </div>

      <footer className="sidebar-footer">
        {!!requests.length && (
          <button
            type="button"
            className="clear-button"
            onClick={onClearRequests}
            disabled={isClearingRequests || deletingRequestId !== null}
            title="Удалить все заявки; бригады сохранятся"
          >
            <Trash2 size={14} />
            {isClearingRequests ? "Очищаем…" : "Очистить"}
          </button>
        )}
        <button type="button" className="demo-button" onClick={onLoadDemo} disabled={isLoadingDemo || isClearingRequests}>
          <Database size={15} />
          {isLoadingDemo ? "Загружаем…" : "Добавить демо-набор"}
        </button>
        <a href="/swagger/index.html" target="_blank" rel="noreferrer">
          <BriefcaseBusiness size={14} /> API <ArrowUpRight size={12} />
        </a>
      </footer>
    </aside>
  );
}
