const API = "/api/v1";
const state = { requests: [], brigades: [], plans: [], activePlan: null, map: null, markers: [] };
const routeColors = ["#d8ff58", "#6f91ff", "#ff8b52", "#b7f4d0", "#e880d8", "#ffd166"];

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) throw new Error(data?.message || `HTTP ${response.status}`);
  return data;
}

function escapeHTML(value = "") {
  return String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
}

function toast(message, error = false) {
  const node = $("#toast");
  node.textContent = message;
  node.style.background = error ? "#762f28" : "#17211d";
  node.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => node.classList.remove("show"), 3200);
}

function minutes(value) {
  const hours = Math.floor(value / 60).toString().padStart(2, "0");
  const mins = (value % 60).toString().padStart(2, "0");
  return `${hours}:${mins}`;
}

const skillNames = { connection: "Подключение", local: "Локальная", emergency: "Авария" };

async function refresh() {
  try {
    const [requests, brigades, plans] = await Promise.all([api("/requests/"), api("/brigades/"), api("/plans/")]);
    Object.assign(state, { requests, brigades, plans });
    $("#api-status").className = "api-status online";
    $("#api-status").innerHTML = "<span></span> API работает";
    renderAll();
  } catch (error) {
    $("#api-status").className = "api-status offline";
    $("#api-status").innerHTML = "<span></span> API недоступен";
    toast(error.message, true);
  }
}

function renderAll() {
  const activeRequests = state.requests.filter((item) => item.status === "pending" || item.status === "planned");
  $("#request-count").textContent = activeRequests.length;
  $("#urgent-count").textContent = `${activeRequests.filter((item) => item.priority === "urgent").length} срочных`;
  $("#brigade-count").textContent = state.brigades.filter((item) => item.status === "available").length;
  renderRequests();
  renderBrigades();
  const latestSuccessfulPlan = state.plans.find((plan) => plan.solution);
  if (latestSuccessfulPlan) renderPlan(latestSuccessfulPlan);
}

function renderRequests() {
  const body = $("#requests-table");
  body.innerHTML = state.requests.map((item) => `<tr>
    <td><strong>${escapeHTML(item.address)}</strong><br><small>${item.latitude.toFixed(4)}, ${item.longitude.toFixed(4)}</small></td>
    <td>${item.window_start}–${item.window_end}<br><small>${item.service_minutes} мин</small></td>
    <td>${escapeHTML(skillNames[item.required_skill] || item.required_skill)}${item.priority === "urgent" ? '<br><span class="status-pill urgent">срочно</span>' : ""}</td>
    <td><span class="status-pill">${escapeHTML(item.status)}</span></td>
  </tr>`).join("");
  $("#requests-empty").classList.toggle("hidden", state.requests.length > 0);
  $(".table-scroll").classList.toggle("hidden", state.requests.length === 0);
}

function renderBrigades() {
  $("#brigades-list").innerHTML = state.brigades.map((item) => `<article class="brigade-card">
    <div><strong>${escapeHTML(item.name)}</strong><p>${escapeHTML(item.start_address)}</p></div>
    <span class="status-pill ${item.status}">${escapeHTML(item.status)}</span>
    <p>${item.shift_start}–${item.shift_end} · ${escapeHTML(item.transport)}</p>
    <div class="skill-row">${item.skills.map((skill) => `<span class="skill">${escapeHTML(skillNames[skill] || skill)}</span>`).join("")}</div>
  </article>`).join("");
  $("#brigades-empty").classList.toggle("hidden", state.brigades.length > 0);
}

function formObject(form) {
  return Object.fromEntries(new FormData(form).entries());
}

$("#request-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const value = formObject(event.currentTarget);
  value.latitude = Number(value.latitude);
  value.longitude = Number(value.longitude);
  value.service_minutes = Number(value.service_minutes);
  if (!value.required_transport) value.required_transport = null;
  try {
    await api("/requests/", { method: "POST", body: JSON.stringify(value) });
    toast("Заявка добавлена");
    await refresh();
  } catch (error) { toast(error.message, true); }
});

$("#brigade-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const value = formObject(event.currentTarget);
  value.start_latitude = Number(value.start_latitude);
  value.start_longitude = Number(value.start_longitude);
  value.skills = [...event.currentTarget.querySelectorAll('input[name="skills"]:checked')].map((node) => node.value);
  try {
    await api("/brigades/", { method: "POST", body: JSON.stringify(value) });
    toast("Бригада добавлена");
    await refresh();
  } catch (error) { toast(error.message, true); }
});

$("#plan-button").addEventListener("click", async () => {
  const button = $("#plan-button");
  const errorBox = $("#plan-error");
  errorBox.classList.add("hidden");
  button.disabled = true;
  button.innerHTML = "Оптимизируем…";
  try {
    const plan = await api("/plans/", { method: "POST", body: JSON.stringify({
      solver_name: $("#solver-name").value,
      time_limit_seconds: Number($("#time-limit").value),
      seed: Number($("#seed").value),
    }) });
    state.plans.unshift(plan);
    renderPlan(plan);
    toast("Маршруты рассчитаны");
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.classList.remove("hidden");
  } finally {
    button.disabled = false;
    button.innerHTML = "Рассчитать маршруты <span>→</span>";
  }
});

$("#demo-button").addEventListener("click", async () => {
  const button = $("#demo-button");
  button.disabled = true;
  const demoBrigades = [
    { name: "Бригада Центр-1", start_address: "Москва, Каланчёвская, 15", start_latitude: 55.7752, start_longitude: 37.6521, shift_start: "09:00", shift_end: "20:00", skills: ["connection", "local"], transport: "car" },
    { name: "Аварийная бригада", start_address: "Москва, Нижегородская, 32", start_latitude: 55.7315, start_longitude: 37.7066, shift_start: "09:00", shift_end: "22:00", skills: ["local", "emergency"], transport: "car" },
  ];
  const demoRequests = [
    { address: "Москва, Мясницкая, 18", latitude: 55.7631, longitude: 37.6354, service_minutes: 70, window_start: "10:00", window_end: "13:00", required_skill: "connection", priority: "normal" },
    { address: "Москва, Покровка, 31", latitude: 55.7593, longitude: 37.6534, service_minutes: 30, window_start: "11:00", window_end: "15:00", required_skill: "local", priority: "normal" },
    { address: "Москва, Волочаевская, 12", latitude: 55.7510, longitude: 37.6808, service_minutes: 80, window_start: "12:00", window_end: "15:00", required_skill: "emergency", priority: "urgent" },
    { address: "Москва, Бауманская, 44", latitude: 55.7723, longitude: 37.6787, service_minutes: 70, window_start: "14:00", window_end: "18:00", required_skill: "connection", priority: "normal" },
  ];
  try {
    await Promise.all(demoBrigades.map((item) => api("/brigades/", { method: "POST", body: JSON.stringify(item) })));
    await Promise.all(demoRequests.map((item) => api("/requests/", { method: "POST", body: JSON.stringify(item) })));
    toast("Демо-набор загружен");
    await refresh();
    location.hash = "#planning";
  } catch (error) { toast(error.message, true); }
  finally { button.disabled = false; }
});

function renderPlan(plan) {
  const solution = plan.solution;
  if (!solution) return;
  state.activePlan = plan;
  $("#plan-placeholder").classList.add("hidden");
  $("#plan-result").classList.remove("hidden");
  $("#plan-status").textContent = solution.status;
  $("#plan-runtime").textContent = `${solution.solver_name} · ${solution.metrics.runtime_seconds.toFixed(2)} c`;
  const total = solution.metrics.completed_jobs + solution.metrics.unassigned_jobs;
  $("#completion-rate").textContent = total ? `${Math.round(solution.metrics.completed_jobs / total * 100)}%` : "—";
  $("#result-summary").innerHTML = [
    ["Выполнено", solution.metrics.completed_jobs],
    ["Активных бригад", solution.metrics.active_engineers],
    ["В пути", `${solution.metrics.total_travel_minutes} мин`],
    ["Пробег", `${solution.metrics.total_distance_km.toFixed(1)} км`],
  ].map(([label, value]) => `<div><small>${label}</small><strong>${value}</strong></div>`).join("");
  $("#route-list").innerHTML = solution.routes.filter((route) => route.stops.length).map((route, index) => {
    const brigade = state.brigades.find((item) => item.id === route.engineer_id);
    return `<article class="route-card"><header><div><h4>${escapeHTML(brigade?.name || route.engineer_id)}</h4><button class="route-action" data-replan="brigade_unavailable" data-entity-id="${escapeHTML(route.engineer_id)}">Бригада недоступна</button></div><span>${route.total_distance_km.toFixed(1)} км</span></header><ol>${route.stops.map((stop) => {
      const request = state.requests.find((item) => item.id === stop.job_id);
      return `<li><strong>${escapeHTML(request?.address || stop.job_id)}</strong>${minutes(stop.service_start_minutes)}–${minutes(stop.service_end_minutes)} · дорога ${stop.travel_minutes} мин <button class="route-action" data-replan="cancel_request" data-entity-id="${escapeHTML(stop.job_id)}">Отменить</button></li>`;
    }).join("")}</ol></article>`;
  }).join("") || '<div class="empty">Нет активных маршрутов</div>';
  const unassigned = solution.unassigned || [];
  $("#unassigned").classList.toggle("hidden", unassigned.length === 0);
  $("#unassigned").innerHTML = `<strong>Не назначено: ${unassigned.length}</strong><br>${unassigned.map((item) => `${escapeHTML(state.requests.find((request) => request.id === item.job_id)?.address || item.job_id)} — ${escapeHTML(item.message)}`).join("<br>")}`;
  drawMap(solution);
}

function drawMap(solution) {
  if (!window.maplibregl) {
    $("#map").innerHTML = '<div class="empty">Карта недоступна без CDN, маршруты показаны справа.</div>';
    return;
  }
  if (state.map) state.map.remove();
  state.map = new maplibregl.Map({
    container: "map",
    style: "https://tiles.openfreemap.org/styles/liberty",
    center: [37.65, 55.76],
    zoom: 11,
    attributionControl: false,
  });
  state.map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  state.map.on("load", () => {
    const bounds = new maplibregl.LngLatBounds();
    solution.routes.forEach((route, index) => {
      if (!route.geometry?.coordinates?.length) return;
      const color = routeColors[index % routeColors.length];
      const sourceID = `route-${index}`;
      state.map.addSource(sourceID, { type: "geojson", data: { type: "Feature", properties: {}, geometry: route.geometry } });
      state.map.addLayer({ id: sourceID, type: "line", source: sourceID, paint: { "line-color": color, "line-width": 5, "line-opacity": .88 } });
      route.geometry.coordinates.forEach((coordinate) => bounds.extend(coordinate));
      route.stops.forEach((stop, stopIndex) => {
        const request = state.requests.find((item) => item.id === stop.job_id);
        if (!request) return;
        const element = document.createElement("div");
        element.style.cssText = `width:24px;height:24px;border-radius:50%;background:${color};border:3px solid #17211d;color:#17211d;font:700 10px Manrope;display:grid;place-items:center`;
        element.textContent = stopIndex + 1;
        new maplibregl.Marker({ element }).setLngLat([request.longitude, request.latitude]).setPopup(new maplibregl.Popup({ offset: 15 }).setHTML(`<strong>${escapeHTML(request.address)}</strong><br>${minutes(stop.service_start_minutes)}`)).addTo(state.map);
      });
    });
    if (!bounds.isEmpty()) state.map.fitBounds(bounds, { padding: 60, maxZoom: 14 });
  });
}

$$('[data-refresh]').forEach((button) => button.addEventListener("click", refresh));
document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-replan]");
  if (!button || !state.activePlan) return;
  const type = button.dataset.replan;
  const key = type === "cancel_request" ? "request_id" : "brigade_id";
  button.disabled = true;
  try {
    await api(`/plans/${state.activePlan.id}/events`, {
      method: "POST",
      body: JSON.stringify({ type, payload: { [key]: button.dataset.entityId } }),
    });
    toast("Событие применено, план перестроен");
    await refresh();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
});
refresh();
