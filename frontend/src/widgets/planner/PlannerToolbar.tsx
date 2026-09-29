import { LoaderCircle, Play, Sparkles } from "lucide-react";

interface PlannerToolbarProps {
  isPlanning: boolean;
  canPlan: boolean;
  onPlan: () => void;
}

export function PlannerToolbar({ isPlanning, canPlan, onPlan }: PlannerToolbarProps) {
  return (
    <div className="planner-toolbar">
      <div className="toolbar-title">
        <Sparkles size={15} />
        <span><strong>Маршруты на день</strong><small>окна, навыки и дороги учтутся автоматически</small></span>
      </div>
      <button type="button" className="plan-button" disabled={!canPlan || isPlanning} onClick={onPlan}>
        {isPlanning ? <LoaderCircle size={17} className="spin" /> : <Play size={16} fill="currentColor" />}
        {isPlanning ? "Считаем…" : "Построить маршруты"}
      </button>
    </div>
  );
}
