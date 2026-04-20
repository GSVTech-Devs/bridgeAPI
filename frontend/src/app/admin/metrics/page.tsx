"use client";

import { useEffect, useState } from "react";
import { getAdminMetrics, getAdminMetricsBreakdown } from "@/lib/api";
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

export default function AdminMetricsPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [breakdown, setBreakdown] = useState<ApiBreakdownItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getAdminMetrics(), getAdminMetricsBreakdown()])
      .then(([m, b]) => {
        setMetrics(m);
        setBreakdown(b.items);
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

      {/* Success vs Errors pie */}
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <h4 className="text-xl font-bold tracking-tight font-headline">Success vs Errors</h4>
        </div>
        <div className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/10">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                {pieData.map((_, i) => (
                  <Cell key={i} fill={i === 0 ? "#22c55e" : "#ba1a1a"} />
                ))}
              </Pie>
              <Legend />
              <Tooltip formatter={(v: unknown) => `${(v as number).toFixed(1)}%`} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
