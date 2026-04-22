"use client";

import { useEffect, useState } from "react";
import { getClientByApi, getClientByKey, getLogs } from "@/lib/api";
import { useTheme } from "@/contexts/ThemeContext";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

type ApiItem = {
  api_id: string;
  api_name: string;
  total_requests: number;
  error_count: number;
  success_count: number;
  total_cost: number;
};

type LogItem = {
  correlation_id: string;
  api_id: string;
  key_id: string;
  key_name: string | null;
  path: string;
  method: string;
  status_code: number;
  latency_ms: number;
  response_body: string | null;
  created_at: string | null;
};

type KeyItem = {
  key_id: string;
  key_name: string;
  key_prefix: string;
  total_requests: number;
};

function statusBadge(code: number) {
  if (code < 300) return "bg-emerald-50 text-emerald-700 border border-emerald-200";
  if (code < 400) return "bg-yellow-50 text-yellow-700 border border-yellow-200";
  return "bg-error-container text-error border border-error/20";
}

function statusDot(code: number) {
  if (code < 300) return "bg-emerald-500";
  if (code < 400) return "bg-yellow-500";
  return "bg-error";
}

function methodColor(method: string) {
  switch (method.toUpperCase()) {
    case "GET": return "text-tertiary";
    case "POST": return "text-primary";
    case "PUT":
    case "PATCH": return "text-yellow-600";
    case "DELETE": return "text-error";
    default: return "text-on-surface-variant";
  }
}

function formatDate(iso: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function computeVolumeData(
  logs: LogItem[],
  timeFilter: string,
  dateFrom: string | null,
  dateTo: string | null,
) {
  const now = new Date();

  if (dateFrom || dateTo) {
    const from = dateFrom ? new Date(`${dateFrom}T00:00:00.000Z`) : new Date(now.getTime() - 30 * 86400000);
    const to = dateTo ? new Date(`${dateTo}T23:59:59.999Z`) : now;
    const diffDays = Math.ceil((to.getTime() - from.getTime()) / 86400000);

    if (diffDays <= 1) {
      const buckets = Array.from({ length: 24 }, (_, i) => ({
        time: `${i.toString().padStart(2, "0")}h`,
        count: 0,
      }));
      logs.forEach((log) => {
        if (!log.created_at) return;
        const d = new Date(log.created_at);
        if (d < from || d > to) return;
        buckets[d.getUTCHours()].count++;
      });
      return buckets;
    }

    const days = Math.min(diffDays, 90);
    const buckets = Array.from({ length: days }, (_, i) => {
      const d = new Date(from.getTime() + i * 86400000);
      return { time: d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }), count: 0 };
    });
    logs.forEach((log) => {
      if (!log.created_at) return;
      const d = new Date(log.created_at);
      if (d < from || d > to) return;
      const idx = Math.floor((d.getTime() - from.getTime()) / 86400000);
      if (idx >= 0 && idx < days) buckets[idx].count++;
    });
    return buckets;
  }

  if (timeFilter === "24h") {
    const buckets = Array.from({ length: 24 }, (_, i) => {
      const d = new Date(now.getTime() - (23 - i) * 3600000);
      return { time: `${d.getHours().toString().padStart(2, "0")}h`, count: 0 };
    });
    logs.forEach((log) => {
      if (!log.created_at) return;
      const hoursAgo = (now.getTime() - new Date(log.created_at).getTime()) / 3600000;
      if (hoursAgo > 24) return;
      const idx = 23 - Math.floor(hoursAgo);
      if (idx >= 0 && idx < 24) buckets[idx].count++;
    });
    return buckets;
  }

  const days = timeFilter === "7d" ? 7 : 30;
  const buckets = Array.from({ length: days }, (_, i) => {
    const d = new Date(now.getTime() - (days - 1 - i) * 86400000);
    return { time: d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }), count: 0 };
  });
  logs.forEach((log) => {
    if (!log.created_at) return;
    const daysAgo = (now.getTime() - new Date(log.created_at).getTime()) / 86400000;
    if (daysAgo > days) return;
    const idx = days - 1 - Math.floor(daysAgo);
    if (idx >= 0 && idx < days) buckets[idx].count++;
  });
  return buckets;
}

function cssVar(name: string): string {
  if (typeof window === "undefined") return "#000";
  return `rgb(${getComputedStyle(document.documentElement).getPropertyValue(`--color-${name}`).trim()})`;
}

function TimeFilter({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const opts = [
    { label: "24h", value: "24h" },
    { label: "7d", value: "7d" },
    { label: "30d", value: "30d" },
  ];
  return (
    <div className="flex bg-surface-container-lowest p-1 rounded-lg border border-outline-variant/15">
      {opts.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
            value === o.value
              ? "bg-surface-container-low text-primary font-bold shadow-sm"
              : "text-on-surface-variant hover:bg-surface"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function LogRow({ log }: { log: LogItem }) {
  const [open, setOpen] = useState(false);
  const isError = log.status_code >= 400;

  return (
    <>
      <tr
        className={`hover:bg-surface/50 transition-colors cursor-pointer ${isError ? "bg-error-container/5" : ""}`}
        onClick={() => log.response_body ? setOpen((v) => !v) : undefined}
      >
        <td className="px-6 py-4 font-mono">
          <span className={`font-bold mr-2 ${methodColor(log.method)}`}>{log.method}</span>
          <span className="text-on-surface">{log.path}</span>
        </td>
        <td className="px-6 py-4">
          <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-bold ${statusBadge(log.status_code)}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${statusDot(log.status_code)} mr-1.5`} />
            {log.status_code}
          </span>
        </td>
        <td className="px-6 py-4 text-on-surface-variant">{Math.round(log.latency_ms)}ms</td>
        <td className="px-6 py-4">
          {log.key_name ? (
            <span className="inline-flex items-center gap-1 px-2 py-1 rounded bg-surface-container text-on-surface-variant text-xs font-mono">
              <span className="material-symbols-outlined text-[12px]">vpn_key</span>
              {log.key_name}
            </span>
          ) : (
            <span className="text-outline text-xs">—</span>
          )}
        </td>
        <td className="px-6 py-4 text-right text-outline text-xs">{formatDate(log.created_at)}</td>
        <td className="px-6 py-4 text-right">
          {log.response_body && (
            <span className="material-symbols-outlined text-[16px] text-on-surface-variant transition-transform" style={{ display: "inline-block", transform: open ? "rotate(180deg)" : "rotate(0deg)" }}>
              expand_more
            </span>
          )}
        </td>
      </tr>
      {open && log.response_body && (
        <tr>
          <td colSpan={6} className="px-6 pb-4 bg-surface-container-low/50">
            <pre className="text-xs font-mono text-on-surface-variant whitespace-pre-wrap break-all bg-surface-container rounded-lg p-4 max-h-48 overflow-y-auto">
              {(() => {
                try { return JSON.stringify(JSON.parse(log.response_body!), null, 2); }
                catch { return log.response_body; }
              })()}
            </pre>
          </td>
        </tr>
      )}
    </>
  );
}

const TODAY = new Date().toISOString().split("T")[0];

function periodToSince(period: string): string {
  const hours = period === "24h" ? 24 : period === "7d" ? 7 * 24 : 30 * 24;
  return new Date(Date.now() - hours * 3_600_000).toISOString();
}

function getTimeRange(
  timeFilter: string,
  dateFrom: string | null,
  dateTo: string | null,
): { since: string | undefined; until: string | undefined } {
  if (dateFrom || dateTo) {
    return {
      since: dateFrom ? `${dateFrom}T00:00:00.000Z` : undefined,
      until: dateTo ? `${dateTo}T23:59:59.999Z` : undefined,
    };
  }
  return { since: periodToSince(timeFilter), until: undefined };
}

export default function MetricsPage() {
  const { theme } = useTheme();
  const [apis, setApis] = useState<ApiItem[]>([]);
  const [selectedApi, setSelectedApi] = useState<ApiItem | null>(null);
  const [filteredMetrics, setFilteredMetrics] = useState<ApiItem | null>(null);
  const [logs, setLogs] = useState<LogItem[]>([]);
  const [keyBreakdown, setKeyBreakdown] = useState<KeyItem[]>([]);
  const [timeFilter, setTimeFilter] = useState("7d");
  const [dateFrom, setDateFrom] = useState<string | null>(null);
  const [dateTo, setDateTo] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [logsLoading, setLogsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasDateRange = dateFrom !== null || dateTo !== null;

  // Derived from logs
  const avgLatency = logs.length > 0
    ? Math.round(logs.reduce((s, l) => s + l.latency_ms, 0) / logs.length)
    : null;
  const maxLatency = logs.length > 0 ? Math.round(Math.max(...logs.map((l) => l.latency_ms))) : null;
  const volumeData = computeVolumeData(logs, timeFilter, dateFrom, dateTo);

  const latencyColor =
    avgLatency === null ? "text-on-surface-variant"
    : avgLatency < 150 ? "text-emerald-500"
    : avgLatency < 400 ? "text-primary"
    : avgLatency < 800 ? "text-yellow-500"
    : "text-error";

  // Initial load — all-time API list (for the top cards)
  useEffect(() => {
    getClientByApi()
      .then((data) => {
        setApis(data.items);
        if (data.items.length > 0) setSelectedApi(data.items[0]);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  }, []);

  // Re-fetch filtered summary metrics when API selection or time range changes
  useEffect(() => {
    if (!selectedApi) return;
    const { since, until } = getTimeRange(timeFilter, dateFrom, dateTo);
    getClientByApi({ since, until })
      .then((data) => {
        const match = data.items.find((a) => a.api_id === selectedApi.api_id);
        setFilteredMetrics(match ?? null);
      })
      .catch(() => setFilteredMetrics(null));
  }, [selectedApi, timeFilter, dateFrom, dateTo]);

  // Re-fetch logs + key breakdown when API selection or time range changes
  useEffect(() => {
    if (!selectedApi) return;
    setLogsLoading(true);
    const { since, until } = getTimeRange(timeFilter, dateFrom, dateTo);
    Promise.all([
      getLogs(0, 200, selectedApi.api_id, since, until),
      getClientByKey({ api_id: selectedApi.api_id, since, until }),
    ])
      .then(([logsData, keyData]) => {
        setLogs(logsData.items);
        setKeyBreakdown(keyData.items);
      })
      .catch(() => { setLogs([]); setKeyBreakdown([]); })
      .finally(() => setLogsLoading(false));
  }, [selectedApi, timeFilter, dateFrom, dateTo]);

  function clearDates() {
    setDateFrom(null);
    setDateTo(null);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-on-surface-variant gap-2">
        <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
        </svg>
        Carregando…
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-10">
      {/* Header */}
      <div>
        <h2 className="font-headline text-3xl font-extrabold text-on-surface tracking-tight">Logs & Métricas</h2>
        <p className="text-on-surface-variant mt-1">Status e volume agregado por API.</p>
      </div>

      {error && (
        <div role="alert" className="p-4 bg-error-container text-on-error-container rounded-xl text-sm">{error}</div>
      )}

      {/* API Cards */}
      {apis.length === 0 ? (
        <div className="text-center py-16 text-on-surface-variant">
          <span className="material-symbols-outlined text-5xl mb-4 block opacity-40">analytics</span>
          <p>Nenhuma API com dados ainda.</p>
        </div>
      ) : (
        <>
          <section>
            <div className="flex items-end justify-between mb-6">
              <div>
                <h3 className="font-headline text-xl font-bold text-on-surface">API Health Overview</h3>
                <p className="text-sm text-on-surface-variant mt-1">Clique em uma API para ver detalhes.</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {apis.map((api) => {
                const isSelected = selectedApi?.api_id === api.api_id;
                const hasErrors = api.error_count > 0;
                const errorRate = api.total_requests > 0 ? (api.error_count / api.total_requests * 100) : 0;

                return (
                  <div
                    key={api.api_id}
                    onClick={() => setSelectedApi(api)}
                    className={`bg-surface-container-lowest rounded-xl p-6 border relative overflow-hidden cursor-pointer hover:bg-surface-container-low transition-all duration-200 ${
                      isSelected
                        ? "border-l-4 border-l-primary ring-2 ring-primary/10 border-outline-variant/15"
                        : "border-outline-variant/15"
                    }`}
                  >
                    {/* Status dot */}
                    <div className="absolute top-4 right-4">
                      {hasErrors ? (
                        <span className="relative inline-flex h-3 w-3">
                          <span className="relative inline-flex rounded-full h-3 w-3 bg-error" />
                        </span>
                      ) : (
                        <span className="relative flex h-3 w-3">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                          <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500" />
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-4 mb-6">
                      <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${hasErrors ? "bg-error-container text-error" : "bg-surface text-primary"}`}>
                        <span className="material-symbols-outlined text-2xl" style={{ fontVariationSettings: "'FILL' 1" }}>api</span>
                      </div>
                      <div>
                        <h3 className="font-headline font-bold text-lg text-on-surface">{api.api_name}</h3>
                        <span className={`text-xs font-semibold uppercase tracking-wider ${hasErrors ? "text-error" : "text-emerald-600"}`}>
                          {hasErrors ? `${errorRate.toFixed(1)}% erros` : "Operacional"}
                        </span>
                      </div>
                    </div>

                    <div className="flex justify-between items-end">
                      <div>
                        <span className="text-xs text-outline block mb-1">Total Requests</span>
                        <span className="font-headline font-bold text-2xl text-on-surface">{api.total_requests.toLocaleString()}</span>
                      </div>
                      <div className="text-right">
                        <span className="text-xs text-outline block mb-1">Custo Total</span>
                        <span className="font-headline font-semibold text-lg text-on-surface">${api.total_cost.toFixed(4)}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Detail Panel */}
          {selectedApi && (
            <section className="bg-surface-container-low rounded-2xl p-8 lg:p-10">
              {/* Detail Header */}
              <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-10 gap-6">
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <h2 className="font-headline text-2xl font-bold text-on-surface tracking-tight">{selectedApi.api_name}</h2>
                    <span className="px-2 py-1 bg-surface-container-lowest text-primary text-xs font-bold rounded border border-outline-variant/15 tracking-wider">ACTIVE</span>
                  </div>
                  <p className="text-sm text-on-surface-variant">Detalhamento de tráfego, uso financeiro e logs recentes.</p>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <div className={`transition-opacity ${hasDateRange ? "opacity-40 pointer-events-none" : ""}`}>
                    <TimeFilter value={timeFilter} onChange={(v) => { setTimeFilter(v); clearDates(); }} />
                  </div>
                  <div className={`flex items-center gap-2 bg-surface-container-lowest border rounded-lg px-3 py-1.5 transition-colors ${hasDateRange ? "border-primary ring-1 ring-primary/20" : "border-outline-variant/20"}`}>
                    <span className="material-symbols-outlined text-on-surface-variant text-[16px]">date_range</span>
                    <input
                      type="date"
                      value={dateFrom ?? ""}
                      max={dateTo ?? TODAY}
                      onChange={(e) => setDateFrom(e.target.value || null)}
                      className="bg-transparent border-none text-sm text-on-surface outline-none w-32 cursor-pointer"
                      title="Data inicial"
                    />
                    <span className="text-on-surface-variant text-xs font-medium">–</span>
                    <input
                      type="date"
                      value={dateTo ?? ""}
                      min={dateFrom ?? undefined}
                      max={TODAY}
                      onChange={(e) => setDateTo(e.target.value || null)}
                      className="bg-transparent border-none text-sm text-on-surface outline-none w-32 cursor-pointer"
                      title="Data final"
                    />
                    {hasDateRange && (
                      <button
                        onClick={clearDates}
                        className="text-on-surface-variant hover:text-on-surface transition-colors ml-1"
                        title="Limpar período"
                      >
                        <span className="material-symbols-outlined text-[16px]">close</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Metric Cards */}
              {(() => {
                const m = filteredMetrics ?? selectedApi;
                return (
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
                    <div className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/15 flex flex-col justify-between">
                      <span className="text-sm text-on-surface-variant font-medium mb-4">Total Requests</span>
                      <span className="font-headline text-3xl font-extrabold text-on-surface tracking-tight">
                        {m.total_requests.toLocaleString()}
                      </span>
                    </div>

                    <div className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/15 flex flex-col justify-between border-b-4 border-b-emerald-500">
                      <span className="text-sm text-on-surface-variant font-medium mb-4">Sucesso</span>
                      <div className="flex items-baseline gap-2">
                        <span className="font-headline text-3xl font-extrabold text-on-surface tracking-tight">
                          {m.success_count.toLocaleString()}
                        </span>
                        <span className="text-xs text-on-surface-variant font-medium">
                          {m.total_requests > 0
                            ? `${(m.success_count / m.total_requests * 100).toFixed(1)}%`
                            : "—"}
                        </span>
                      </div>
                    </div>

                    <div className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/15 flex flex-col justify-between border-b-4 border-b-error">
                      <span className="text-sm text-on-surface-variant font-medium mb-4">Erros</span>
                      <div className="flex items-baseline gap-2">
                        <span className={`font-headline text-3xl font-extrabold tracking-tight ${m.error_count > 0 ? "text-error" : "text-on-surface"}`}>
                          {m.error_count.toLocaleString()}
                        </span>
                        <span className={`text-xs font-medium ${m.error_count > 0 ? "text-error" : "text-on-surface-variant"}`}>
                          {m.total_requests > 0
                            ? `${(m.error_count / m.total_requests * 100).toFixed(1)}%`
                            : "—"}
                        </span>
                      </div>
                    </div>

                    <div className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/15 flex flex-col justify-between bg-gradient-to-br from-surface-container-lowest to-surface-variant">
                      <span className="text-sm text-on-surface-variant font-medium mb-4 flex items-center gap-2">
                        <span className="material-symbols-outlined text-primary text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>account_balance_wallet</span>
                        Total Gasto
                      </span>
                      <span className="font-headline text-3xl font-extrabold text-primary tracking-tight">
                        ${m.total_cost.toFixed(4)}
                      </span>
                    </div>
                  </div>
                );
              })()}

              {/* Volume + Latency Cards */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">
                {/* Request Volume Chart */}
                <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/15 p-6">
                  <div className="flex items-center gap-2 mb-5">
                    <span className="material-symbols-outlined text-primary text-[18px]" style={{ fontVariationSettings: "'FILL' 1" }}>bar_chart</span>
                    <h3 className="font-headline font-bold text-base text-on-surface">Volume de Requests</h3>
                    <span className="ml-auto text-[10px] text-on-surface-variant uppercase tracking-wider font-semibold">
                      {hasDateRange
                        ? [dateFrom, dateTo].filter(Boolean).join(" – ")
                        : timeFilter === "24h" ? "por hora" : "por dia"}
                    </span>
                  </div>
                  {logs.length === 0 ? (
                    <div className="h-40 flex items-center justify-center text-on-surface-variant text-sm">Sem dados</div>
                  ) : (
                    <ResponsiveContainer width="100%" height={160}>
                      <BarChart key={`${theme}-${dateFrom}-${dateTo}-${timeFilter}`} data={volumeData} barSize={timeFilter === "24h" ? 6 : 10} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke={cssVar("outline-variant")} vertical={false} opacity={0.5} />
                        <XAxis
                          dataKey="time"
                          tick={{ fontSize: 10, fill: cssVar("on-surface-variant") }}
                          tickLine={false}
                          axisLine={false}
                          interval={timeFilter === "24h" ? 3 : timeFilter === "7d" ? 0 : 4}
                        />
                        <YAxis
                          tick={{ fontSize: 10, fill: cssVar("on-surface-variant") }}
                          tickLine={false}
                          axisLine={false}
                          allowDecimals={false}
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: cssVar("surface-container-high"),
                            border: "none",
                            borderRadius: "8px",
                            fontSize: "12px",
                            color: cssVar("on-surface"),
                          }}
                          cursor={{ fill: cssVar("surface-container"), radius: 4 }}
                        />
                        <Bar dataKey="count" fill={cssVar("primary")} radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </div>

                {/* Average Latency Card */}
                <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/15 p-6 flex flex-col">
                  <div className="flex items-center gap-2 mb-5">
                    <span className="material-symbols-outlined text-primary text-[18px]" style={{ fontVariationSettings: "'FILL' 1" }}>timer</span>
                    <h3 className="font-headline font-bold text-base text-on-surface">Latência Média</h3>
                  </div>

                  {avgLatency === null ? (
                    <div className="flex-1 flex items-center justify-center text-on-surface-variant text-sm">Sem dados</div>
                  ) : (
                    <div className="flex-1 flex flex-col justify-between">
                      <div>
                        <div className="flex items-baseline gap-2 mb-1">
                          <span className={`font-headline font-extrabold text-5xl tracking-tight ${latencyColor}`}>
                            {avgLatency}
                          </span>
                          <span className="text-on-surface-variant font-medium text-lg">ms</span>
                        </div>
                        <span className={`text-xs font-bold uppercase tracking-wider ${latencyColor}`}>
                          {avgLatency < 150 ? "Excelente" : avgLatency < 400 ? "Bom" : avgLatency < 800 ? "Moderado" : "Lento"}
                        </span>
                      </div>

                      <div className="mt-6 space-y-3">
                        <div className="flex justify-between items-center text-sm">
                          <span className="text-on-surface-variant">Máxima registrada</span>
                          <span className="font-mono font-bold text-on-surface">{maxLatency}ms</span>
                        </div>
                        <div className="flex justify-between items-center text-sm">
                          <span className="text-on-surface-variant">Baseado em</span>
                          <span className="font-mono font-bold text-on-surface">{logs.length} requests</span>
                        </div>
                        <div className="h-2 bg-surface-container rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${
                              avgLatency < 150 ? "bg-emerald-500"
                              : avgLatency < 400 ? "bg-primary"
                              : avgLatency < 800 ? "bg-yellow-500"
                              : "bg-error"
                            }`}
                            style={{ width: `${Math.min(100, (avgLatency / 1000) * 100)}%` }}
                          />
                        </div>
                        <div className="flex justify-between text-[10px] text-on-surface-variant">
                          <span>0ms</span>
                          <span>500ms</span>
                          <span>1000ms</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Per-key breakdown card */}
              {keyBreakdown.length > 0 && (
                <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/15 overflow-hidden mb-6">
                  <div className="px-6 py-4 border-b border-outline-variant/15 bg-surface/50 flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary text-[18px]" style={{ fontVariationSettings: "'FILL' 1" }}>vpn_key</span>
                    <h3 className="font-headline font-bold text-base text-on-surface">Requests por Chave</h3>
                  </div>
                  <div className="divide-y divide-outline-variant/10">
                    {keyBreakdown.map((k) => {
                      const maxReq = keyBreakdown[0]?.total_requests || 1;
                      const pct = Math.round((k.total_requests / maxReq) * 100);
                      return (
                        <div key={k.key_id} className="px-6 py-3 flex items-center gap-4">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-semibold text-sm text-on-surface truncate">{k.key_name}</span>
                              <span className="font-mono text-xs text-outline">{k.key_prefix}…</span>
                            </div>
                            <div className="h-1.5 bg-surface-container rounded-full overflow-hidden">
                              <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${pct}%` }} />
                            </div>
                          </div>
                          <span className="font-headline font-bold text-on-surface text-sm flex-shrink-0">
                            {k.total_requests.toLocaleString()}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Logs Table */}
              <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/15 overflow-hidden">
                <div className="p-6 border-b border-outline-variant/15 flex justify-between items-center bg-surface/50">
                  <h3 className="font-headline font-bold text-lg text-on-surface">Logs Recentes</h3>
                  <div className="flex items-center gap-4">
                    {logsLoading && (
                      <svg className="animate-spin w-4 h-4 text-on-surface-variant" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                      </svg>
                    )}
                    <span className="text-xs text-on-surface-variant">
                      {logs.length} registros · clique na linha para ver resposta
                    </span>
                  </div>
                </div>

                {logs.length === 0 && !logsLoading ? (
                  <p className="p-8 text-sm text-on-surface-variant text-center">Nenhum log encontrado para esta API.</p>
                ) : (
                  <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
                    <table className="w-full text-left border-collapse text-sm">
                      <thead className="sticky top-0 z-10 bg-surface text-xs font-semibold text-outline tracking-wider uppercase">
                        <tr>
                          <th className="px-6 py-4">Método & Endpoint</th>
                          <th className="px-6 py-4">Status</th>
                          <th className="px-6 py-4">Duração</th>
                          <th className="px-6 py-4">Chave</th>
                          <th className="px-6 py-4 text-right">Timestamp</th>
                          <th className="px-6 py-4" />
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-surface-container-low">
                        {logs.map((log) => (
                          <LogRow key={log.correlation_id} log={log} />
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
