"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getStatusOverview,
  getStatusEvents,
  statusStreamUrl,
  type StatusOverviewItem,
  type StatusEvent,
} from "@/lib/api";
import { getToken } from "@/lib/auth";

function formatTime(dateStr: string | null): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", hour: "2-digit",
    minute: "2-digit", second: "2-digit",
  });
}

function fmtUptime(s: number | null): string {
  if (s == null) return "—";
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function statusPill(s: string): string {
  switch (s) {
    case "healthy": return "bg-green-600 text-white";
    case "degraded": return "bg-amber-500 text-white";
    case "down": return "bg-error text-on-error";
    default: return "bg-surface-container-high text-on-surface-variant";
  }
}

function statusLabel(s: string): string {
  switch (s) {
    case "healthy": return "Saudável";
    case "degraded": return "Degradado";
    case "down": return "Fora do ar";
    case "unknown": return "Sem sinal";
    default: return s;
  }
}

function checkDetail(check: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(check)) {
    if (k === "status") continue;
    parts.push(`${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`);
  }
  return parts.join(" · ");
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

export default function StatusPage() {
  const [items, setItems] = useState<StatusOverviewItem[]>([]);
  const [events, setEvents] = useState<StatusEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [live, setLive] = useState(false);

  const refresh = useCallback(async () => {
    const [ov, ev] = await Promise.all([getStatusOverview(), getStatusEvents()]);
    setItems(ov.items);
    setEvents(ev.items);
  }, []);

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, [refresh]);

  // Tempo real via SSE; reidrata os eventos sempre que o overview muda.
  useEffect(() => {
    const token = getToken();
    if (!token || typeof window === "undefined") return;
    const es = new EventSource(statusStreamUrl(token));
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as { items: StatusOverviewItem[] };
        setItems(data.items);
        setLive(true);
      } catch {
        /* ignora frames malformados */
      }
    };
    es.onerror = () => setLive(false);
    return () => es.close();
  }, []);

  const counts = items.reduce(
    (acc, i) => { acc[i.status] = (acc[i.status] ?? 0) + 1; return acc; },
    {} as Record<string, number>
  );

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-4xl font-extrabold tracking-tight text-on-surface font-headline mb-2">
            Status
          </h2>
          <p className="text-on-surface-variant font-medium">
            Saúde das APIs em tempo real (proxy, captcha e alvo).
          </p>
        </div>
        <span className={`flex items-center gap-2 text-xs font-bold ${live ? "text-green-500" : "text-on-surface-variant"}`}>
          <span className={`w-2 h-2 rounded-full ${live ? "bg-green-500 animate-pulse" : "bg-on-surface-variant/40"}`} />
          {live ? "ao vivo" : "—"}
        </span>
      </div>

      {/* resumo */}
      {!loading && items.length > 0 && (
        <div className="flex gap-3 flex-wrap">
          {(["healthy", "degraded", "down", "unknown"] as const).map((s) => (
            <div key={s} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-container-low">
              <span className={`w-2.5 h-2.5 rounded-full ${statusPill(s).split(" ")[0]}`} />
              <span className="text-sm font-bold text-on-surface">{counts[s] ?? 0}</span>
              <span className="text-xs text-on-surface-variant">{statusLabel(s)}</span>
            </div>
          ))}
        </div>
      )}

      {/* cards de APIs */}
      {loading ? (
        <Spinner label="Carregando status…" />
      ) : items.length === 0 ? (
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 flex flex-col items-center justify-center py-16 text-on-surface-variant gap-3">
          <span className="material-symbols-outlined text-4xl opacity-50">monitor_heart</span>
          <p className="font-medium">Nenhuma API reportou status ainda.</p>
          <p className="text-xs">As APIs enviam readiness via a bridge-sdk (POST /ingest/status).</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((api) => (
            <div
              key={api.api_id}
              className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 p-5 space-y-4"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-bold text-on-surface truncate">
                    {api.api_name ?? api.api_id}
                  </p>
                  <p className="text-xs text-on-surface-variant">
                    {api.sdk_version ? `sdk ${api.sdk_version}` : "sdk —"} · up {fmtUptime(api.uptime_s)}
                  </p>
                </div>
                <span className={`text-[10px] font-black uppercase rounded-md px-2 py-1 whitespace-nowrap ${statusPill(api.status)}`}>
                  {statusLabel(api.status)}
                </span>
              </div>

              {Object.keys(api.checks).length > 0 && (
                <div className="space-y-1.5">
                  {Object.entries(api.checks).map(([name, check]) => (
                    <div key={name} className="flex items-center gap-2 text-xs">
                      <span className={`w-2 h-2 rounded-full shrink-0 ${statusPill(check.status).split(" ")[0]}`} />
                      <span className="font-mono font-bold text-on-surface">{name}</span>
                      <span className="text-on-surface-variant truncate">{checkDetail(check)}</span>
                    </div>
                  ))}
                </div>
              )}

              <p className="text-[11px] text-on-surface-variant/70">
                {api.stale ? "⚠ sem heartbeat recente · " : ""}
                visto {formatTime(api.last_seen)}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* transições recentes */}
      <div className="space-y-4">
        <h3 className="text-lg font-bold text-on-surface">Transições recentes</h3>
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 overflow-hidden">
          {events.length === 0 ? (
            <div className="py-10 text-center text-on-surface-variant text-sm">
              Nenhuma mudança de status registrada.
            </div>
          ) : (
            <div className="divide-y divide-outline-variant/10">
              {events.map((ev, i) => (
                <div key={i} className="flex items-center gap-3 px-5 py-3 text-sm">
                  <span className="font-medium text-on-surface min-w-0 flex-1 truncate">
                    {ev.api_name ?? ev.api_id}
                  </span>
                  <span className={`text-[10px] font-black uppercase rounded px-2 py-0.5 ${statusPill(ev.from_status)}`}>
                    {statusLabel(ev.from_status)}
                  </span>
                  <span className="material-symbols-outlined text-base text-on-surface-variant">arrow_forward</span>
                  <span className={`text-[10px] font-black uppercase rounded px-2 py-0.5 ${statusPill(ev.to_status)}`}>
                    {statusLabel(ev.to_status)}
                  </span>
                  <span className="text-xs text-on-surface-variant whitespace-nowrap">
                    {formatTime(ev.at)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
