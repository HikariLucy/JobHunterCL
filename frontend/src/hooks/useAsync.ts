import { useCallback, useEffect, useRef, useState } from "react";

export interface AsyncState<T> {
  data: T | undefined;
  error: Error | undefined;
  loading: boolean;
  reload: () => Promise<void>;
  setData: (value: T) => void;
}

/** Carga datos al montar y cuando cambian `deps`; ignora respuestas obsoletas. */
export function useAsync<T>(load: () => Promise<T>, deps: readonly unknown[] = []): AsyncState<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<Error>();
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);

  const run = useCallback(load, deps);

  const reload = useCallback(async () => {
    const id = ++seq.current;
    setLoading(true);
    setError(undefined);
    try {
      const value = await run();
      if (id === seq.current) setData(value);
    } catch (e) {
      if (id === seq.current) setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      if (id === seq.current) setLoading(false);
    }
  }, [run]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, error, loading, reload, setData };
}
