"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getApis,
  getAdminAppLogs,
  getAdminTrace,
  type AppLogEntry,
  type TraceItem,
} from "@/lib/api";

type Api = { id: string; name: string };

function formatTime(dateStr: string | null): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

function formatClock(dateStr: string | null): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  return d.toLocaleTimeString("pt-BR", {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  }) + "." + String(d.getMilliseconds()).padStart(3, "0");
}

function levelColor(level: string | null): string {
  switch ((level ?? "").toUpperCase()) {
    case "CRITICAL":
    case "ERROR": return "bg-error text-on-error";
    case "WARNING": return "bg-amber-500 text-white";
    case "DEBUG": return "bg-surface-container-high text-on-surface-variant";
    default: return "bg-surface-container-high text-on-surface";
  }
}

function statusColor(code: number | null): string {
  if (code == null) return "bg-surface-container-high text-on-surface";
  if (code >= 500) return "bg-error text-on-error";
  if (code >= 400) return "bg-amber-500 text-white";
  return "bg-green-600 text-white";
}

function Spinner({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center py-16 text-on-surface-variant gap-2">
      <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
      </svg>
      {label}
    </div>
  );
}

export default function DebugPage() {
  const [apis, setApis] = useState<Api[]>([]);
  const [cidInput, setCidInput] = useState("");
  const [activeCid, setActiveCid] = useState<string | null>(null);
  const [trace, setTrace] = useState<TraceItem[]>([]);
  const [traceLoading, setTraceLoading] = useState(false);
  const [traceError, setTraceError] = useState<string | null>(null);

  const [recent, setRecent] = useState<AppLogEntry[]>([]);
  const [recentLoading, setRecentLoading] = useState(true);
  const [levelFilter, setLevelFilter] = useState<string>("");
  const [expanded, setExpanded] = useState<number | null>(null);

  const apiMap = Object.fromEntries(apis.map((a) => [a.id, a.name]));

  const loadTrace = useCallback(async (cid: string) => {
    const id = cid.trim();
    if (!id) return;
    setActiveCid(id);
    setCidInput(id);
    setTraceLoading(true);
    setTraceError(null);
    setExpanded(null);
    try {
      const res = await getAdminTrace(id);
      setTrace(res.items);
      if (res.items.length === 0) {
        setTraceError("Nenhum evento encontrado para este correlation ID.");
      }
    } catch (e) {
      setTraceError(e instanceof Error ? e.message : "Falha ao carregar a timeline.");
      setTrace([]);
    } finally {
      setTraceLoading(false);
    }
  }, []);

  const loadRecent = useCallback(async (level: string) => {
    setRecentLoading(true);
    try {
      const res = await getAdminAppLogs({ level: level || undefined, limit: 50 });
      setRecent(res.items);
    } finally {
      setRecentLoading(false);
    }
  }, []);

  useEffect(() => {
    getApis().then((r) => setApis(r.items)).catch(() => {});
    loadRecent("");
    // deep-link via ?cid=...
    if (typeof window !== "undefined") {
      const cid = new URLSearchParams(window.location.search).get("cid");
      if (cid) loadTrace(cid);
    }
  }, [loadRecent, loadTrace]);

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <div>
        <h2 className="text-4xl font-extrabold tracking-tight text-on-surface font-headline mb-2">
          Debug
        </h2>
        <p className="text-on-surface-variant font-medium">
          Timeline unificada (gateway + APIs) por correlation ID.
        </p>
      </div>

      {/* Busca por correlation ID */}
      <form
        onSubmit={(e) => { e.preventDefault(); loadTrace(cidInput); }}
        className="flex gap-3"
      >
        <div className="flex-1 relative">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant/60 text-[20px]">
            search
          </span>
          <input
            value={cidInput}
            onChange={(e) => setCidInput(e.target.value)}
            placeholder="Cole um correlation ID…"
            className="w-full pl-11 pr-4 py-3 rounded-xl bg-surface-container-lowest border border-outline-variant/20 font-mono text-sm text-on-surface focus:outline-none focus:border-primary"
          />
        </div>
        <button
          type="submit"
          className="px-6 py-3 rounded-xl bg-primary text-white font-bold text-sm hover:opacity-90 transition-opacity disabled:opacity-50"
          disabled={!cidInput.trim()}
        >
          Buscar
        </button>
      </form>

      {/* Timeline */}
      {activeCid && (
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 overflow-hidden">
          <div className="px-5 py-4 bg-surface-container-low/50 flex items-center justify-between">
            <div className="min-w-0">
              <p className="text-xs font-bold uppercase tracking-widest text-on-surface-variant/60">
                Timeline
              </p>
              <p className="font-mono text-sm text-on-surface truncate">{activeCid}</p>
            </div>
            {!traceLoading && trace.length > 0 && (
              <span className="text-xs text-on-surface-variant whitespace-nowrap">
                {trace.length} evento(s)
              </span>
            )}
          </div>

          {traceLoading ? (
            <Spinner label="Carregando timeline…" />
          ) : traceError ? (
            <div className="flex flex-col items-center justify-center py-14 text-on-surface-variant gap-3">
              <span className="material-symbols-outlined text-4xl opacity-50">search_off</span>
              <p className="font-medium">{traceError}</p>
            </div>
          ) : (
            <div className="divide-y divide-outline-variant/10">
              {trace.map((item, i) => {
                const isOpen = expanded === i;
                const isGateway = item.source === "gateway";
                const ts = item.timestamp ?? item.created_at;
                return (
                  <div key={i}>
                    <button
                      onClick={() => setExpanded(isOpen ? null : i)}
                      className="w-full grid grid-cols-[90px_70px_1fr_120px] items-center gap-2 px-5 py-3.5 hover:bg-surface-container-low/30 transition-colors text-left"
                    >
                      <span
                        className={`text-center text-[10px] font-black uppercase rounded-md py-1 ${
                          isGateway
                            ? "bg-primary/15 text-primary"
                            : "bg-tertiary/15 text-tertiary"
                        }`}
                      >
                        {item.source}
                      </span>

                      {isGateway ? (
                        <span className={`text-center text-xs font-black rounded-md py-1 ${statusColor(item.status_code)}`}>
                          {item.status_code ?? "—"}
                        </span>
                      ) : (
                        <span className={`text-center text-[10px] font-black rounded-md py-1 ${levelColor(item.level)}`}>
                          {item.level ?? "—"}
                        </span>
                      )}

                      <div className="min-w-0">
                        {isGateway ? (
                          <p className="font-mono text-sm text-on-surface truncate">
                            <span className="font-bold text-on-surface-variant">{item.method}</span>{" "}
                            {item.path}
                          </p>
                        ) : (
                          <p className="text-sm text-on-surface truncate">
                            <span className="font-mono font-bold text-tertiary">{item.event}</span>
                            {item.message ? <span className="text-on-surface-variant"> — {item.message}</span> : null}
                          </p>
                        )}
                        {item.error_code && (
                          <p className="text-xs font-bold text-error">{item.error_code}</p>
                        )}
                      </div>

                      <span className="text-xs font-mono text-on-surface-variant text-right tabular-nums">
                        {formatClock(ts)}
                      </span>
                    </button>

                    {isOpen && (
                      <div className="px-5 pb-4 bg-surface-container-low/20 text-xs text-on-surface-variant space-y-2">
                        <div className="grid grid-cols-2 gap-2 pt-2">
                          <span><span className="font-bold">Fonte:</span> {item.source}</span>
                          <span><span className="font-bold">Quando:</span> {formatTime(ts)}</span>
                          {isGateway && item.latency_ms != null && (
                            <span><span className="font-bold">Latência:</span> {Math.round(item.latency_ms)}ms</span>
                          )}
                          {item.proxy_id && <span><span className="font-bold">Proxy:</span> {item.proxy_id}</span>}
                          {item.captcha_provider && <span><span className="font-bold">Captcha:</span> {item.captcha_provider}</span>}
                        </div>
                        {item.message && !isGateway && (
                          <pre className="bg-surface-container rounded-lg p-3 font-mono text-on-surface whitespace-pre-wrap break-all">
                            {item.message}
                          </pre>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Logs recentes (descoberta) */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-bold text-on-surface">Logs recentes das APIs</h3>
          <div className="flex gap-2">
            {["", "ERROR", "WARNING", "INFO"].map((lvl) => (
              <button
                key={lvl || "all"}
                onClick={() => { setLevelFilter(lvl); loadRecent(lvl); }}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                  levelFilter === lvl
                    ? "bg-primary text-white"
                    : "bg-surface-container-low text-on-surface hover:bg-surface-container-high"
                }`}
              >
                {lvl || "Todos"}
              </button>
            ))}
          </div>
        </div>

        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 overflow-hidden">
          {recentLoading ? (
            <Spinner label="Carregando logs…" />
          ) : recent.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-14 text-on-surface-variant gap-3">
              <span className="material-symbols-outlined text-4xl opacity-50">inbox</span>
              <p className="font-medium">Nenhum log estruturado recebido ainda.</p>
              <p className="text-xs">As APIs enviam logs via a bridge-sdk (POST /ingest/logs).</p>
            </div>
          ) : (
            <div className="divide-y divide-outline-variant/10">
              {recent.map((log, i) => (
                <button
                  key={i}
                  onClick={() => loadTrace(log.correlation_id)}
                  className="w-full grid grid-cols-[70px_1fr_140px_160px] items-center gap-2 px-5 py-3 hover:bg-surface-container-low/30 transition-colors text-left"
                >
                  <span className={`text-center text-[10px] font-black rounded-md py-1 ${levelColor(log.level)}`}>
                    {log.level}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm text-on-surface truncate">
                      <span className="font-mono font-bold text-tertiary">{log.event}</span>
                      {log.message ? <span className="text-on-surface-variant"> — {log.message}</span> : null}
                    </p>
                    <p className="text-xs text-on-surface-variant/70 font-mono truncate">
                      {log.correlation_id}
                      {log.error_code ? <span className="text-error font-bold"> · {log.error_code}</span> : null}
                    </p>
                  </div>
                  <span className="text-xs text-primary font-medium truncate">
                    {apiMap[log.api_id] ?? log.api_id}
                  </span>
                  <span className="text-xs text-on-surface-variant text-right">
                    {formatTime(log.timestamp ?? log.created_at)}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
