import { Pause, Play, RotateCcw } from "lucide-react";
import type { Brigade, PlannedRoute } from "../../shared/types/domain";
import { formatDistance } from "../../shared/lib/format";

interface PlaybackBarProps {
  route: PlannedRoute;
  brigade?: Brigade;
  progress: number;
  isPlaying: boolean;
  speed: number;
  onPlayPause: () => void;
  onRestart: () => void;
  onSeek: (progress: number) => void;
  onSpeed: (speed: number) => void;
}

export function PlaybackBar({
  route,
  brigade,
  progress,
  isPlaying,
  speed,
  onPlayPause,
  onRestart,
  onSeek,
  onSpeed,
}: PlaybackBarProps) {
  return (
    <div className="playback-bar">
      <button type="button" className="play-button" onClick={onPlayPause} aria-label={isPlaying ? "Пауза" : "Воспроизвести"}>
        {isPlaying ? <Pause size={17} fill="currentColor" /> : <Play size={17} fill="currentColor" />}
      </button>
      <button type="button" className="restart-button" onClick={onRestart} aria-label="Начать сначала"><RotateCcw size={14} /></button>
      <div className="playback-route">
        <span>СИМУЛЯЦИЯ · {brigade?.name ?? "маршрут"}</span>
        <strong>{Math.round(progress * 100)}% пути <small>· {formatDistance(route.total_distance_km * progress)} км</small></strong>
      </div>
      <input
        className="progress-range"
        type="range"
        min="0"
        max="1"
        step="0.001"
        value={progress}
        onChange={(event) => onSeek(Number(event.target.value))}
        style={{ "--progress": `${progress * 100}%` } as React.CSSProperties}
        aria-label="Прогресс поездки"
      />
      <div className="speed-switch" aria-label="Скорость анимации">
        {[1, 2, 4].map((value) => <button type="button" className={speed === value ? "active" : ""} onClick={() => onSpeed(value)} key={value}>{value}×</button>)}
      </div>
    </div>
  );
}
