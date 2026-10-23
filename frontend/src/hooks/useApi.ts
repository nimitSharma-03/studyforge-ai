import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '../services/api';

export interface ApiState<T> {
  data: T | undefined;
  error: ApiError | undefined;
  loading: boolean;
  reload: () => Promise<void>;
  setData: (value: T | undefined) => void;
}

function toApiError(err: unknown): ApiError {
  if (err instanceof ApiError) return err;
  return new ApiError(-1, 'client_error', err instanceof Error ? err.message : 'Something went wrong.');
}

/** Run an async API call on mount and whenever `deps` change; ignores stale responses. */
export function useApi<T>(fn: () => Promise<T>, deps: unknown[], enabled = true): ApiState<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<ApiError>();
  const [loading, setLoading] = useState(enabled);
  const requestId = useRef(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const run = useCallback(async () => {
    const id = ++requestId.current;
    setLoading(true);
    setError(undefined);
    try {
      const result = await fnRef.current();
      if (id === requestId.current) setData(result);
    } catch (err) {
      if (id === requestId.current) setError(toApiError(err));
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (enabled) void run();
    else setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled]);

  return { data, error, loading, reload: run, setData };
}

export { toApiError };
