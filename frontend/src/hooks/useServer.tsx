import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { api } from '../services/api';
import type { Health } from '../types/api';
import { DEFAULT_MAX_UPLOAD_MB } from '../config';

type ServerStatus = 'checking' | 'waking' | 'online' | 'degraded' | 'offline';

interface ServerState {
  status: ServerStatus;
  health?: Health;
  maxUploadMb: number;
  llmEnabled: boolean;
  recheck: () => void;
}

const ServerContext = createContext<ServerState>({
  status: 'checking',
  maxUploadMb: DEFAULT_MAX_UPLOAD_MB,
  llmEnabled: false,
  recheck: () => undefined,
});

/**
 * Tracks backend availability. Hosted free-tier instances sleep when idle, so a slow first
 * response is reported as "waking" rather than as an error, and checks are retried for ~90 s.
 */
export function ServerProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<ServerStatus>('checking');
  const [health, setHealth] = useState<Health>();
  const attempt = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  const check = useCallback(async () => {
    const id = ++attempt.current;
    clearTimeout(timer.current);
    const slow = setTimeout(() => {
      if (id === attempt.current) setStatus((s) => (s === 'checking' ? 'waking' : s));
    }, 2500);
    const started = Date.now();
    const tryOnce = async (): Promise<void> => {
      try {
        const h = await api.health();
        if (id !== attempt.current) return;
        setHealth(h);
        setStatus(h.status === 'ok' ? 'online' : 'degraded');
      } catch {
        if (id !== attempt.current) return;
        if (Date.now() - started < 90_000) {
          setStatus('waking');
          timer.current = setTimeout(() => void tryOnce(), 4000);
        } else {
          setStatus('offline');
        }
      }
    };
    await tryOnce();
    clearTimeout(slow);
  }, []);

  useEffect(() => {
    void check();
    return () => clearTimeout(timer.current);
  }, [check]);

  const recheck = useCallback(() => {
    setStatus('checking');
    void check();
  }, [check]);

  return (
    <ServerContext.Provider
      value={{
        status,
        health,
        maxUploadMb: health?.max_upload_mb ?? DEFAULT_MAX_UPLOAD_MB,
        llmEnabled: health?.llm_enabled ?? false,
        recheck,
      }}
    >
      {children}
    </ServerContext.Provider>
  );
}

export const useServer = () => useContext(ServerContext);
