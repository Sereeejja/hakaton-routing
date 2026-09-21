import { Check, Clock3, MapPin, Navigation, Users, X } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { coordinateLabel } from "../../shared/lib/format";
import type {
  CreateBrigadeInput,
  CreateRequestInput,
  PointDraft,
  PointKind,
} from "../../shared/types/domain";

interface PointEditorProps {
  draft: PointDraft;
  isSaving: boolean;
  onChangeKind: (kind: PointKind) => void;
  onCreateRequest: (input: CreateRequestInput) => Promise<void>;
  onCreateBrigade: (input: CreateBrigadeInput) => Promise<void>;
  onClose: () => void;
}

const availableSkills = [
  { value: "connection", label: "Подключение" },
  { value: "local", label: "Локальные" },
  { value: "emergency", label: "Авария" },
];

export function PointEditor({
  draft,
  isSaving,
  onChangeKind,
  onCreateRequest,
  onCreateBrigade,
  onClose,
}: PointEditorProps) {
  const [skills, setSkills] = useState(["connection", "local"]);

  useEffect(() => setSkills(["connection", "local"]), [draft.latitude, draft.longitude]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    if (draft.kind === "request") {
      await onCreateRequest({
        address: String(form.get("address")),
        latitude: draft.latitude,
        longitude: draft.longitude,
        service_minutes: Number(form.get("service_minutes")),
        window_start: String(form.get("window_start")),
        window_end: String(form.get("window_end")),
        required_skill: String(form.get("required_skill")),
        required_transport: form.get("required_transport") ? String(form.get("required_transport")) : null,
        priority: String(form.get("priority")),
      });
      return;
    }
    await onCreateBrigade({
      name: String(form.get("name")),
      start_address: String(form.get("start_address")),
      start_latitude: draft.latitude,
      start_longitude: draft.longitude,
      shift_start: String(form.get("shift_start")),
      shift_end: String(form.get("shift_end")),
      skills,
      transport: String(form.get("transport")),
    });
  };

  const toggleSkill = (skill: string) => {
    setSkills((current) => current.includes(skill) ? current.filter((item) => item !== skill) : [...current, skill]);
  };

  return (
    <aside className="inspector point-editor">
      <header className="inspector-header">
        <div><span>НОВАЯ ТОЧКА</span><h2>Что здесь находится?</h2></div>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Закрыть"><X size={18} /></button>
      </header>

      <div className="kind-switch" role="tablist">
        <button type="button" className={draft.kind === "request" ? "active" : ""} onClick={() => onChangeKind("request")}>
          <MapPin size={16} /><span>Заявка<small>куда приехать</small></span>
        </button>
        <button type="button" className={draft.kind === "brigade" ? "active" : ""} onClick={() => onChangeKind("brigade")}>
          <Users size={16} /><span>Старт<small>откуда выехать</small></span>
        </button>
      </div>

      <div className="coordinate-card">
        <Navigation size={16} />
        <div><span>ТОЧКА НА КАРТЕ</span><strong>{coordinateLabel(draft.latitude, draft.longitude)}</strong></div>
        <Check size={15} />
      </div>

      <form className="editor-form" onSubmit={submit}>
        {draft.kind === "request" ? (
          <>
            <label className="field-label">Название или адрес
              <input name="address" required defaultValue={`Точка ${draft.latitude.toFixed(4)}, ${draft.longitude.toFixed(4)}`} autoFocus />
            </label>
            <div className="field-grid">
              <label className="field-label"><Clock3 size={13} /> Окно с
                <input name="window_start" type="time" required defaultValue="10:00" />
              </label>
              <label className="field-label">до
                <input name="window_end" type="time" required defaultValue="14:00" />
              </label>
            </div>
            <div className="field-grid">
              <label className="field-label">Работа, мин
                <input name="service_minutes" type="number" min="1" required defaultValue="45" />
              </label>
              <label className="field-label">Приоритет
                <select name="priority" defaultValue="normal"><option value="normal">Обычный</option><option value="urgent">Срочный</option></select>
              </label>
            </div>
            <label className="field-label">Тип работы
              <select name="required_skill" defaultValue="connection">
                {availableSkills.map((skill) => <option value={skill.value} key={skill.value}>{skill.label}</option>)}
              </select>
            </label>
            <label className="field-label">Нужный транспорт
              <select name="required_transport" defaultValue="">
                <option value="">Любой</option><option value="car">Автомобиль</option><option value="walk">Пешком</option><option value="bicycle">Велосипед</option>
              </select>
            </label>
          </>
        ) : (
          <>
            <label className="field-label">Название бригады
              <input name="name" required defaultValue={`Бригада ${Math.floor(Math.random() * 90) + 10}`} autoFocus />
            </label>
            <label className="field-label">Название точки старта
              <input name="start_address" required defaultValue={`База ${draft.latitude.toFixed(4)}, ${draft.longitude.toFixed(4)}`} />
            </label>
            <div className="field-grid">
              <label className="field-label"><Clock3 size={13} /> Смена с
                <input name="shift_start" type="time" required defaultValue="09:00" />
              </label>
              <label className="field-label">до
                <input name="shift_end" type="time" required defaultValue="20:00" />
              </label>
            </div>
            <label className="field-label">Транспорт
              <select name="transport" defaultValue="car"><option value="car">Автомобиль</option><option value="walk">Пешком</option><option value="bicycle">Велосипед</option></select>
            </label>
            <fieldset className="skills-field">
              <legend>Навыки бригады</legend>
              <div>{availableSkills.map((skill) => (
                <button type="button" className={skills.includes(skill.value) ? "active" : ""} onClick={() => toggleSkill(skill.value)} key={skill.value}>
                  {skills.includes(skill.value) && <Check size={12} />}{skill.label}
                </button>
              ))}</div>
            </fieldset>
          </>
        )}
        <div className="editor-tip">
          <span>{draft.kind === "request" ? "B" : "A"}</span>
          <p><strong>{draft.kind === "request" ? "Это точка назначения" : "Это точка отправления"}</strong>{draft.kind === "request" ? "Алгоритм определит бригаду и порядок визита." : "Отсюда бригада начнёт свой маршрут."}</p>
        </div>
        <button className="save-point-button" type="submit" disabled={isSaving || (draft.kind === "brigade" && skills.length === 0)}>
          {isSaving ? "Сохраняем…" : draft.kind === "request" ? "Добавить заявку" : "Добавить старт бригады"}
          <span>→</span>
        </button>
      </form>
    </aside>
  );
}
