import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { pointAlongRoute } from "../../shared/lib/geometry";
import type { Coordinate } from "../../shared/types/domain";

const BASE_DURATION_MS = 11_000;

export function useRoutePlayback(coordinates: Coordinate[], routeKey: string) {
  const [progress, setProgress] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeedState] = useState(2);
  const progressRef = useRef(0);
  const previousFrameRef = useRef<number | null>(null);

  useEffect(() => {
    progressRef.current = 0;
    setProgress(0);
    setIsPlaying(coordinates.length > 1);
    previousFrameRef.current = null;
  }, [coordinates.length, routeKey]);

  useEffect(() => {
    if (!isPlaying || coordinates.length < 2) return;
    let frameId = 0;

    const frame = (timestamp: number) => {
      if (previousFrameRef.current === null) previousFrameRef.current = timestamp;
      const delta = timestamp - previousFrameRef.current;
      previousFrameRef.current = timestamp;
      const next = Math.min(1, progressRef.current + (delta * speed) / BASE_DURATION_MS);
      progressRef.current = next;
      setProgress(next);
      if (next >= 1) {
        setIsPlaying(false);
        previousFrameRef.current = null;
        return;
      }
      frameId = requestAnimationFrame(frame);
    };

    frameId = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(frameId);
  }, [coordinates.length, isPlaying, speed]);

  const playPause = useCallback(() => {
    if (progressRef.current >= 1) {
      progressRef.current = 0;
      setProgress(0);
    }
    previousFrameRef.current = null;
    setIsPlaying((value) => !value);
  }, []);

  const restart = useCallback(() => {
    progressRef.current = 0;
    previousFrameRef.current = null;
    setProgress(0);
    setIsPlaying(coordinates.length > 1);
  }, [coordinates.length]);

  const seek = useCallback((value: number) => {
    const next = Math.min(1, Math.max(0, value));
    progressRef.current = next;
    previousFrameRef.current = null;
    setProgress(next);
  }, []);

  const setSpeed = useCallback((value: number) => {
    setSpeedState(value);
    previousFrameRef.current = null;
  }, []);

  return {
    progress,
    isPlaying,
    speed,
    position: useMemo(() => pointAlongRoute(coordinates, progress), [coordinates, progress]),
    playPause,
    restart,
    seek,
    setSpeed,
  };
}
