/**
 * Small hooks the pages share.
 *
 * Routing is hash-based on purpose: no router package could be installed in this
 * environment, and a hash route needs no server rewrite rules when the built bundle is
 * served as static files.
 */

import { useCallback, useEffect, useRef, useState } from "react";

export type Route = { page: string; param: string | null; tab: string | null };

function parseHash(): Route {
  const raw = window.location.hash.replace(/^#\/?/, "");
  const [page = "", param = "", tab = ""] = raw.split("/");
  return {
    page: page || "dashboard",
    param: param ? decodeURIComponent(param) : null,
    tab: tab ? decodeURIComponent(tab) : null,
  };
}

/** Current hash route plus a navigate function; browser back/forward keep working. */
export function useHashRoute(): [Route, (page: string, param?: string, tab?: string) => void] {
  const [route, setRoute] = useState<Route>(parseHash);

  useEffect(() => {
    const onChange = () => setRoute(parseHash());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  const navigate = useCallback((page: string, param?: string, tab?: string) => {
    const parts = [page];
    if (param) parts.push(encodeURIComponent(param));
    if (param && tab) parts.push(encodeURIComponent(tab));
    window.location.hash = `#/${parts.join("/")}`;
  }, []);

  return [route, navigate];
}

export type AsyncState<T> = {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
};

/**
 * Run a fetch on mount and whenever `deps` change, discarding results from a request
 * that has already been superseded so fast filter changes cannot render stale data.
 */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);
  const attempt = useRef(0);

  useEffect(() => {
    const current = ++attempt.current;
    setLoading(true);
    loader()
      .then((result) => {
        if (current !== attempt.current) return;
        setData(result);
        setError(null);
      })
      .catch((cause: unknown) => {
        if (current !== attempt.current) return;
        setError(cause instanceof Error ? cause.message : "Request failed");
      })
      .finally(() => {
        if (current === attempt.current) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  const reload = useCallback(() => setNonce((value) => value + 1), []);
  return { data, error, loading, reload };
}

/** Re-run `callback` on an interval, but only while `active` is true. */
export function usePolling(callback: () => void, active: boolean, intervalMs = 2500): void {
  const latest = useRef(callback);
  latest.current = callback;
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => latest.current(), intervalMs);
    return () => window.clearInterval(timer);
  }, [active, intervalMs]);
}
