"use client";

import { useEffect, useState } from "react";
import { getClientDashboard, getClientByApi, getClientStatusCodes, getLogs } from "@/lib/api";
import Link from "next/link";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";

type Metrics = {
  total_requests: number;
  error_rate: number;
  avg_latency_ms: number;
  total_cost: number;
  billable_requests: number;
  non_billable_requests: number;
};

type ApiBreakdownItem = {
  api_id: string;
  api_name: string;
  total_requests: number;
  error_count: number;
  success_count: number;
  total_cost: number;
};

type StatusCodeItem = {
  api_id: string;
  api_name: string;
  status_code: number;
  count: number;
};

type LogItem = {
  correlation_id: string;
  api_id: string;
  path: string;
  method: string;
  status_code: number;
  latency_ms: number;
};

function since(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString();
}

function statusBadgeColor(code: number) {
  if (code < 300) return "bg-emerald-50 text-emerald-700";
  if (code < 400) return "bg-yellow-50 text-yellow-700";
  return "bg-red-50 text-red-700";
}

function methodBadgeColor(method: string) {
  switch (method.toUpperCase()) {
    case "GET": return "bg-blue-50 text-blue-700";
    case "POST": return "bg-green-50 text-green-700";
    case "PUT":
    case "PATCH": return "bg-yellow-50 text-yellow-700";
    case "DELETE": return "bg-red-50 text-red-700";
    default: return "bg-surface-container text-on-surface-variant";
  }
}

function SectionCard({ icon, title, subtitle, children, action }: {
  icon: string;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/15 overflow-hidden">
      <div className="px-6 py-4 border-b border-outline-variant/10 flex items-center justify-between bg-surface-container-low/50">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
            <span className="material-symbols-outlined text-primary text-[18px]" style={{ fontVariationSettings: "'FILL' 1" }}>{icon}</span>
          </div>
          <div>
            <span className="font-headline font-bold text-on-surface">{title}</span>
            {subtitle && <p className="text-xs text-on-surface-variant mt-0.5">{subtitle}</p>}
          </div>
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [allTime, setAllTime] = useState<ApiBreakdownItem[]>([]);
  const [last30, setLast30] = useState<ApiBreakdownItem[]>([]);
  const [last15, setLast15] = useState<ApiBreakdownItem[]>([]);
  const [statusCodes, setStatusCodes] = useState<StatusCodeItem[]>([]);
  const [recentLogs, setRecentLogs] = useState<LogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      getClientDashboard(),
      getClientByApi(),
      getClientByApi({ since: since(30) }),
      getClientByApi({ since: since(15) }),
      getClientStatusCodes(),
      getLogs(0, 10),
    ])
      .then(([m, all, s30, s15, sc, logs]) => {
        setMetrics(m);
        setAllTime(all.items);
        setLast30(s30.items);
        setLast15(s15.items);
        setStatusCodes(sc.items);
        setRecentLogs(logs.items as LogItem[]);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  }, []);

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

  const barData = metrics
    ? [
        { name: "Total", value: metrics.total_requests },
        { name: "Faturáveis", value: metrics.billable_requests },
        { name: "Não faturáveis", value: metrics.non_billable_requests },
      ]
    : [];

  const pieData = metrics
    ? [
        { name: "Sucesso", value: Math.max(0, 100 - metrics.error_rate) },
        { name: "Erros", value: metrics.error_rate },
      ]
    : [];

  const byApiId = (arr: ApiBreakdownItem[]) =>
    Object.fromEntries(arr.map((x) => [x.api_id, x]));

  const all30 = byApiId(last30);
  const all15 = byApiId(last15);
  const apiIds = Array.from(new Set(allTime.map((x) => x.api_id)));
  const apiNameById = Object.fromEntries(allTime.map((x) => [x.api_id, x.api_name]));

  const statusByApi = statusCodes.reduce<Record<string, StatusCodeItem[]>>((acc, item) => {
    if (!acc[item.api_id]) acc[item.api_id] = [];
    acc[item.api_id].push(item);
    return acc;
  }, {});

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-10">
        <h2 className="font-headline text-3xl font-extrabold text-on-surface tracking-tight">Visão Geral</h2>
        <p className="text-on-surface-variant mt-1">Métricas em tempo real para o consumo da sua API.</p>
      </div>

      {error && (
        <div role="alert" className="mb-6 p-4 bg-error-container text-on-error-container rounded-xl text-sm">
          Não foi possível carregar as métricas: {error}
        </div>
      )}

      {metrics && (
        <div className="space-y-8">
          {/* Stat cards */}
          <div className="grid grid-cols-4 gap-5">
            {[
              { label: "Total de Solicitações", value: metrics.total_requests.toLocaleString(), icon: "data_usage", color: "text-primary", bg: "bg-primary/10" },
              { label: "Taxa de Sucesso", value: `${(100 - metrics.error_rate).toFixed(1)}%`, icon: "check_circle", color: "text-emerald-600", bg: "bg-emerald-50" },
              { label: "Latência Média", value: `${Math.round(metrics.avg_latency_ms)}ms`, icon: "timer", color: "text-tertiary", bg: "bg-tertiary/10" },
              { label: "Custo Total", value: `$${metrics.total_cost.toFixed(4)}`, icon: "payments", color: "text-primary", bg: "bg-primary/10" },
            ].map((card) => (
              <div key={card.label} className="bg-surface-container-lowest rounded-2xl border border-outline-variant/15 p-6 flex flex-col justify-between h-36">
                <div className="flex justify-between items-start">
                  <span className="text-sm text-on-surface-variant font-medium">{card.label}</span>
                  <div className={`w-8 h-8 rounded-lg ${card.bg} flex items-center justify-center`}>
                    <span className={`material-symbols-outlined text-[18px] ${card.color}`} style={{ fontVariationSettings: "'FILL' 1" }}>{card.icon}</span>
                  </div>
                </div>
                <div className="font-headline text-3xl font-extrabold text-on-surface tracking-tight">{card.value}</div>
              </div>
            ))}
          </div>

          {/* Charts */}
          <div className="grid grid-cols-3 gap-5">
            <div className="col-span-2">
            <SectionCard icon="bar_chart" title="Visão Geral das Requisições" subtitle="Total, faturáveis e não faturáveis">
              <div className="p-6 h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={barData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e6f6ff" />
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#414754" }} />
                    <YAxis tick={{ fontSize: 11, fill: "#414754" }} />
                    <Tooltip />
                    <Bar dataKey="value" fill="#2b5ab5" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </SectionCard>
            </div>

            <SectionCard icon="donut_large" title="Sucesso vs Erros" subtitle="Taxa de sucesso geral">
              <div className="p-6 h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ value }: { value: number }) => `${value.toFixed(1)}%`}>
                      <Cell fill="#22c55e" />
                      <Cell fill="#ba1a1a" />
                    </Pie>
                    <Legend />
                    <Tooltip formatter={(v: unknown) => `${(v as number).toFixed(1)}%`} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </SectionCard>
          </div>

          {/* Requests by API */}
          {apiIds.length > 0 && (
            <SectionCard icon="api" title="Requisições por API" subtitle="Total, últimos 30 e 15 dias com custo">
              <div className="overflow-auto max-h-[320px]">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-surface-container-lowest z-10">
                    <tr className="text-on-surface-variant text-xs uppercase tracking-wider">
                      <th className="text-left px-6 py-3 font-semibold">API</th>
                      <th className="text-right px-6 py-3 font-semibold">Total</th>
                      <th className="text-right px-6 py-3 font-semibold">Últimos 30d</th>
                      <th className="text-right px-6 py-3 font-semibold">Últimos 15d</th>
                      <th className="text-right px-6 py-3 font-semibold">Custo Total</th>
                      <th className="text-right px-6 py-3 font-semibold">Custo 30d</th>
                      <th className="text-right px-6 py-3 font-semibold">Custo 15d</th>
                    </tr>
                  </thead>
                  <tbody>
                    {apiIds.map((id) => {
                      const row = allTime.find((x) => x.api_id === id)!;
                      const r30 = all30[id];
                      const r15 = all15[id];
                      return (
                        <tr key={id} className="border-t border-outline-variant/10 hover:bg-surface-container-low/50 transition-colors">
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-2">
                              <div className="w-6 h-6 rounded bg-primary/10 flex items-center justify-center">
                                <span className="material-symbols-outlined text-primary text-[12px]" style={{ fontVariationSettings: "'FILL' 1" }}>api</span>
                              </div>
                              <span className="font-semibold text-on-surface">{row.api_name}</span>
                            </div>
                          </td>
                          <td className="px-6 py-4 text-right font-semibold text-on-surface">{row.total_requests.toLocaleString()}</td>
                          <td className="px-6 py-4 text-right text-on-surface-variant">{r30?.total_requests.toLocaleString() ?? "—"}</td>
                          <td className="px-6 py-4 text-right text-on-surface-variant">{r15?.total_requests.toLocaleString() ?? "—"}</td>
                          <td className="px-6 py-4 text-right font-semibold text-on-surface">${row.total_cost.toFixed(4)}</td>
                          <td className="px-6 py-4 text-right text-on-surface-variant">{r30 ? `$${r30.total_cost.toFixed(4)}` : "—"}</td>
                          <td className="px-6 py-4 text-right text-on-surface-variant">{r15 ? `$${r15.total_cost.toFixed(4)}` : "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </SectionCard>
          )}

          {/* Health + Status Codes */}
          {apiIds.length > 0 && (
            <div className="grid grid-cols-2 gap-5">
              <SectionCard icon="monitor_heart" title="Saúde por API" subtitle="Sucesso, erros e taxa de erro">
                <div className="overflow-auto max-h-[320px]">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-surface-container-lowest z-10">
                      <tr className="text-on-surface-variant text-xs uppercase tracking-wider">
                        <th className="text-left px-6 py-3 font-semibold">API</th>
                        <th className="text-right px-6 py-3 font-semibold">Sucesso</th>
                        <th className="text-right px-6 py-3 font-semibold">Erros</th>
                        <th className="text-right px-6 py-3 font-semibold">Taxa Erro</th>
                      </tr>
                    </thead>
                    <tbody>
                      {allTime.map((row) => {
                        const errorRate = row.total_requests > 0
                          ? (row.error_count / row.total_requests * 100)
                          : 0;
                        const isHighError = errorRate > 5;
                        return (
                          <tr key={row.api_id} className="border-t border-outline-variant/10 hover:bg-surface-container-low/50 transition-colors">
                            <td className="px-6 py-4 font-semibold text-on-surface">{row.api_name}</td>
                            <td className="px-6 py-4 text-right text-emerald-600 font-semibold">{row.success_count.toLocaleString()}</td>
                            <td className="px-6 py-4 text-right text-red-600 font-semibold">{row.error_count.toLocaleString()}</td>
                            <td className="px-6 py-4 text-right">
                              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold ${isHighError ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"}`}>
                                {isHighError && <span className="material-symbols-outlined text-[12px]">warning</span>}
                                {errorRate.toFixed(1)}%
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </SectionCard>

              <SectionCard icon="rule" title="Top Status Codes" subtitle="Top 5 códigos por API">
                <div className="overflow-auto max-h-[320px]">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-surface-container-lowest z-10">
                      <tr className="text-on-surface-variant text-xs uppercase tracking-wider">
                        <th className="text-left px-6 py-3 font-semibold">API</th>
                        <th className="text-center px-6 py-3 font-semibold">Status</th>
                        <th className="text-right px-6 py-3 font-semibold">Contagem</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(statusByApi).map(([apiId, codes]) =>
                        codes.map((item, i) => (
                          <tr key={`${apiId}-${item.status_code}`} className="border-t border-outline-variant/10 hover:bg-surface-container-low/50 transition-colors">
                            <td className="px-6 py-3 font-medium text-on-surface">{item.api_name}</td>
                            <td className="px-6 py-3 text-center">
                              <span className={`inline-block px-2 py-0.5 rounded-full font-mono text-xs font-bold ${statusBadgeColor(item.status_code)}`}>
                                {item.status_code}
                              </span>
                            </td>
                            <td className="px-6 py-3 text-right text-on-surface-variant">{item.count.toLocaleString()}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </SectionCard>
            </div>
          )}

          {/* Recent Consults */}
          <div className="h-[420px] bg-surface-container-lowest rounded-xl border border-outline-variant/10 overflow-hidden flex flex-col">
            <div className="px-5 py-4 border-b border-outline-variant/10 shrink-0 flex items-center justify-between">
              <h4 className="text-xl font-bold tracking-tight font-headline">Consultas Recentes</h4>
              <Link href="/dashboard/metrics" className="text-xs text-primary font-semibold hover:underline flex items-center gap-1">
                Ver todas
                <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
              </Link>
            </div>
            <div className="overflow-y-auto flex-1 divide-y divide-outline-variant/10">
              {recentLogs.length === 0 ? (
                <p className="p-6 text-sm text-on-surface-variant">Nenhuma consulta registrada ainda.</p>
              ) : (
                recentLogs.map((log) => {
                  const isError = log.status_code >= 400;
                  const apiName = apiNameById[log.api_id] ?? log.api_id?.slice(0, 8) ?? "—";
                  return (
                    <div key={log.correlation_id} className="flex items-center gap-3 px-5 py-3 hover:bg-surface-container-low/30 transition-colors">
                      <span className={`shrink-0 w-12 text-center text-xs font-black rounded-md py-1 ${isError ? "bg-error-container text-error" : "bg-green-100 text-green-700"}`}>
                        {log.status_code}
                      </span>
                      <span className={`shrink-0 w-14 text-xs font-mono font-bold ${isError ? "text-error" : "text-on-surface-variant"}`}>
                        {log.method}
                      </span>
                      <span className="flex-1 font-mono text-xs text-on-surface truncate min-w-0">{log.path}</span>
                      <div className="shrink-0 text-right hidden sm:block">
                        <p className="text-xs font-bold text-on-surface">{apiName}</p>
                        <p className="text-[10px] text-on-surface-variant font-mono">{Math.round(log.latency_ms)}ms</p>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
