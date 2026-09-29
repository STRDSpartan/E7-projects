import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

/** Charge une ressource GET ; `reload()` la relit (après une action). */
export function useResource<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!path) return;
    try {
      setData(await api.get<T>(path));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [path]);

  useEffect(() => {
    setData(null);
    void reload();
  }, [reload]);

  return { data, error, reload, setData };
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
}
