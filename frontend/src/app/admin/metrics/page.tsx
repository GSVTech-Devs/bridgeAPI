"use client";

import { useEffect, useState } from "react";
import { getAdminMetrics, getAdminMetricsBreakdown, getAdminUsage, getAdminLogs } from "@/lib/api";
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
  error_rate: number;
};

type ClientApiUsageItem = {
  client_id: string;
  client_name: string;
  client_email: string;
  api_id: string;
  api_name: string;
  total_requests: number;
  total_cost: number;
};

type LogItem = {
  correlation_id: string;
  client_id: string;
  api_id: string;
  path: string;
  method: string;
  status_code: number;
  latency_ms: number;
  created_at: string | null;
};

export default function AdminMetricsPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [breakdown, setBreakdown] = useState<ApiBreakdownItem[]>([]);
  const [usage, setUsage] = useState<ClientApiUsageItem[]>([]);
  const [logs, setLogs] = useState<LogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getAdminMetrics(), getAdminMetricsBreakdown(), getAdminUsage(), getAdminLogs(0, 50)])
      .then(([m, b, u, l]) => {
        setMetrics(m);
        setBreakdown(b.items);
        setUsage(u.items);
        setLogs(l.items);
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
        Carregando métricas…
      </div>
    );
  }

  if (error) return <div role="alert" className="p-6 text-error bg-error-container rounded-xl">{error}</div>;
  if (!metrics) return null;

  const errorRate = metrics.error_rate;
  const successRate = Math.max(0, 100 - errorRate);

  const barData = [
    { name: "Total", value: metrics.total_requests },
    { name: "Faturáveis", value: metrics.billable_requests },
    { name: "Não faturáveis", value: metrics.non_billable_requests },
  ];

  const pieData = [
    { name: "Sucesso", value: successRate },
    { name: "Erros", value: errorRate },
  ];

  const clientNameMap: Record<string, string> = {};
  const apiNameMap: Record<string, string> = {};
  for (const u of usage) {
    clientNameMap[u.client_id] = u.client_name;
    apiNameMap[u.api_id] = u.api_name;
  }

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-4xl font-extrabold tracking-tight text-on-surface mb-2 font-headline">
            Métricas de Performance
          </h2>
          <p className="text-on-surface-variant font-medium">Real-time API usage and system health analysis.</p>
        </div>
      </div>

      {/* Bento metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="md:col-span-2 bg-surface-container-lowest p-8 rounded-xl border border-outline-variant/10 shadow-sm relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-6 text-primary/10 group-hover:scale-110 transition-transform duration-500">
            <span className="material-symbols-outlined" style={{ fontSize: "6rem" }}>trending_up</span>
          </div>
          <p className="text-sm font-bold uppercase tracking-widest text-on-surface-variant mb-2">Total API Requests</p>
          <div className="flex items-baseline gap-4">
            <h3 className="text-5xl font-black text-on-surface font-headline">
              {metrics.total_requests.toLocaleString()}
            </h3>
            <span className="text-green-600 font-bold flex items-center text-sm">
              <span className="material-symbols-outlined text-sm">arrow_upward</span> Billable: {metrics.billable_requests.toLocaleString()}
            </span>
          </div>
          <div className="mt-6 w-full h-2 bg-surface-container-low rounded-full overflow-hidden">
            <div
              className="h-full bg-primary"
              style={{ width: `${metrics.total_requests > 0 ? (metrics.billable_requests / metrics.total_requests) * 100 : 0}%` }}
            />
          </div>
        </div>
        <div className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/10 shadow-sm">
          <p className="text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-2">Avg. Latency</p>
          <h3 className="text-3xl font-black text-on-surface font-headline">{Math.round(metrics.avg_latency_ms)}ms</h3>
        </div>
        <div className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/10 shadow-sm">
          <p className="text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-2">Success Rate</p>
          <h3 className="text-3xl font-black text-on-surface font-headline">{successRate.toFixed(2)}%</h3>
          {successRate >= 99 && (
            <div className="flex items-center gap-1 mt-2">
              <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              <span className="text-[10px] text-green-600 font-bold">ALL SYSTEMS NOMINAL</span>
            </div>
          )}
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Bar chart */}
        <div className="lg:col-span-2 bg-surface-container-lowest p-8 rounded-xl border border-outline-variant/10">
          <div className="flex justify-between items-center mb-8">
            <h4 className="text-xl font-bold tracking-tight font-headline">Query Volume per Category</h4>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={barData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e6f6ff" />
              <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#414754" }} />
              <YAxis tick={{ fontSize: 12, fill: "#414754" }} />
              <Tooltip />
              <Bar dataKey="value" fill="#2b5ab5" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Per-API health breakdown */}
        <div className="bg-surface-container-lowest p-8 rounded-xl border border-outline-variant/10">
          <h4 className="text-xl font-bold tracking-tight mb-8 font-headline">Health by API</h4>
          {breakdown.length === 0 ? (
            <p className="text-sm text-on-surface-variant">No requests recorded yet.</p>
          ) : (
            <div className="space-y-6">
              {breakdown.map((item) => {
                const apiSuccessRate = Math.max(0, 100 - item.error_rate);
                const color = apiSuccessRate >= 95 ? "#2b5ab5" : apiSuccessRate >= 80 ? "#f59e0b" : "#ba1a1a";
                return (
                  <div key={item.api_id} className="space-y-2">
                    <div className="flex justify-between text-xs font-bold">
                      <span className="truncate max-w-[140px]" title={item.api_name}>{item.api_name}</span>
                      <span style={{ color }}>{apiSuccessRate.toFixed(1)}%</span>
                    </div>
                    <div className="h-1.5 w-full bg-surface-container-low rounded-full">
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${apiSuccessRate}%`, backgroundColor: color }}
                      />
                    </div>
                    <p className="text-[10px] text-on-surface-variant">{item.total_requests.toLocaleString()} requests</p>
                  </div>
                );
              })}
            </div>
          )}
          <div className="mt-8 pt-8 border-t border-outline-variant/10">
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <p className="text-[10px] font-bold text-on-surface-variant">ERROR RATIO</p>
                <p className="text-2xl font-black text-error font-headline">{errorRate.toFixed(2)}%</p>
              </div>
              <div className="h-10 w-10 bg-error-container rounded-lg flex items-center justify-center text-error">
                <span className="material-symbols-outlined">warning</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Success vs Errors pie + Recent Consults — side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Pie chart */}
        <div className="h-[420px] bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/10 flex flex-col">
          <h4 className="text-xl font-bold tracking-tight font-headline mb-4 shrink-0">Success vs Errors</h4>
          <div className="flex-1 min-h-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart margin={{ top: 20, right: 30, bottom: 20, left: 30 }}>
              <Pie
                data={pieData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label={({ name, value }) =>
                  `${String(name)}: ${Number(value).toFixed(1)}%`
                }
                labelLine
              >
                {pieData.map((_, i) => (
                  <Cell key={i} fill={i === 0 ? "#22c55e" : "#ba1a1a"} />
                ))}
              </Pie>
              <Legend verticalAlign="bottom" height={36} />
              <Tooltip formatter={(v: unknown) => `${(v as number).toFixed(1)}%`} />
            </PieChart>
          </ResponsiveContainer>
          </div>
        </div>

        {/* Recent Consults — scrollable */}
        <div className="h-[420px] bg-surface-container-lowest rounded-xl border border-outline-variant/10 overflow-hidden flex flex-col">
          <div className="px-5 py-4 border-b border-outline-variant/10 shrink-0">
            <h4 className="text-xl font-bold tracking-tight font-headline">Recent Consults</h4>
          </div>
          <div className="overflow-y-auto flex-1 divide-y divide-outline-variant/10">
            {logs.length === 0 ? (
              <p className="p-6 text-sm text-on-surface-variant">No consults recorded yet.</p>
            ) : (
              logs.map((log) => {
                const isError = log.status_code !== 200;
                const clientName = clientNameMap[log.client_id] ?? log.client_id.slice(0, 8);
                const apiName = apiNameMap[log.api_id] ?? log.api_id.slice(0, 8);
                return (
                  <div key={log.correlation_id} className="flex items-center gap-3 px-5 py-3 hover:bg-surface-container-low/30 transition-colors">
                    <span className={`shrink-0 w-12 text-center text-xs font-black rounded-md py-1 ${isError ? "bg-error-container text-error" : "bg-green-100 text-green-700"}`}>
                      {log.status_code}
                    </span>
                    <span className={`shrink-0 w-10 text-xs font-mono font-bold ${isError ? "text-error" : "text-on-surface-variant"}`}>
                      {log.method}
                    </span>
                    <span className="flex-1 font-mono text-xs text-on-surface truncate min-w-0">{log.path}</span>
                    <div className="shrink-0 text-right hidden sm:block">
                      <p className="text-xs font-bold text-on-surface">{clientName}</p>
                      <p className="text-[10px] text-primary font-medium">{apiName}</p>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Per-client per-API usage table */}
      <div className="space-y-4">
        <h4 className="text-xl font-bold tracking-tight font-headline">Usage by Client & API</h4>
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 overflow-hidden">
          {usage.length === 0 ? (
            <p className="p-6 text-sm text-on-surface-variant">No usage data recorded yet.</p>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container-low/50">
                  {["Client", "Email", "API", "Requests", "Accumulated Cost"].map((h) => (
                    <th key={h} className="px-5 py-3 text-xs font-bold uppercase tracking-widest text-on-surface-variant/60">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/10">
                {usage.map((row) => (
                  <tr key={`${row.client_id}-${row.api_id}`} className="hover:bg-surface-container-low/30 transition-colors">
                    <td className="px-5 py-4 text-sm font-bold text-on-surface">{row.client_name}</td>
                    <td className="px-5 py-4 text-xs text-on-surface-variant font-mono">{row.client_email}</td>
                    <td className="px-5 py-4">
                      <span className="px-2 py-1 rounded-lg bg-primary/10 text-primary text-xs font-bold">{row.api_name}</span>
                    </td>
                    <td className="px-5 py-4 text-sm font-bold text-on-surface tabular-nums">
                      {row.total_requests.toLocaleString()}
                    </td>
                    <td className="px-5 py-4 text-sm font-bold tabular-nums">
                      {row.total_cost > 0
                        ? <span className="text-primary">R$ {row.total_cost.toFixed(4)}</span>
                        : <span className="text-on-surface-variant text-xs">—</span>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
