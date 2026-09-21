import { ChevronDown, LoaderCircle, Play, Sparkles } from "lucide-react";
import type { RunPlanInput } from "../../shared/types/domain";

interface PlannerToolbarProps {
  settings: RunPlanInput;
  isPlanning: boolean;
  canPlan: boolean;
  onSettings: (settings: RunPlanInput) => void;
  onPlan: () => void;
}

export function PlannerToolbar({ settings, isPlanning, canPlan, onSettings, onPlan }: PlannerToolbarProps) {
  return (
    <div className="planner-toolbar">
      <div className="toolbar-title"><Sparkles size={15} /><span>Планировщик</span></div>
      <label className="toolbar-select">
        <span>Алгоритм</span>
        <select value={settings.solver_name} onChange={(event) => onSettings({ ...settings, solver_name: event.target.value })}>
          <option value="ortools">OR-Tools</option>
          <option value="improved_greedy">Improved greedy</option>
          <option value="greedy">Greedy</option>
          <option value="hgs">HGS</option>
        </select>
        <ChevronDown size={13} />
      </label>
      <label className="toolbar-number"><span>Лимит</span><input type="number" min="1" max="120" value={settings.time_limit_seconds} onChange={(event) => onSettings({ ...settings, time_limit_seconds: Number(event.target.value) })} /><small>сек</small></label>
      <label className="toolbar-number seed"><span>Seed</span><input type="number" value={settings.seed} onChange={(event) => onSettings({ ...settings, seed: Number(event.target.value) })} /></label>
      <button type="button" className="plan-button" disabled={!canPlan || isPlanning} onClick={onPlan}>
        {isPlanning ? <LoaderCircle size={17} className="spin" /> : <Play size={16} fill="currentColor" />}
        {isPlanning ? "Считаем…" : "Построить маршруты"}
      </button>
    </div>
  );
}
