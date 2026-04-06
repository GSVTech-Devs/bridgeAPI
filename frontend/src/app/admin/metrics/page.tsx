"use client";

import { useEffect, useState } from "react";
import { getAdminMetrics } from "@/lib/api";
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

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-3xl font-bold text-gray-900 mt-1">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

export default function AdminMetricsPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAdminMetrics()
      .then(setMetrics)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-gray-400">
        <svg className="animate-spin w-6 h-6 mr-2" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
        </svg>
        Carregando métricas…
      </div>
    );
  }

  if (error) return <div role="alert" className="p-6 text-red-600 bg-red-50 rounded-xl">{error}</div>;
  if (!metrics) return null;

  const barData = [
    { name: "Total", value: metrics.total_requests },
    { name: "Faturáveis", value: metrics.billable_requests },
    { name: "Não faturáveis", value: metrics.non_billable_requests },
  ];

  const errorRate = metrics.error_rate * 100;
  const pieData = [
    { name: "Sucesso", value: Math.max(0, 100 - errorRate) },
    { name: "Erros", value: errorRate },
  ];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Métricas Globais</h1>
        <p className="text-gray-500 mt-1">Visão consolidada de uso da plataforma.</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-8">
        <StatCard label="Total de requisições" value={metrics.total_requests.toLocaleString()} />
        <StatCard label="Taxa de erro" value={`${(metrics.error_rate * 100).toFixed(1)}%`} />
        <StatCard label="Latência média" value={`${Math.round(metrics.avg_latency_ms)} ms`} />
        <StatCard label="Custo total" value={`R$ ${metrics.total_cost.toFixed(4)}`} />
        <StatCard label="Faturáveis" value={metrics.billable_requests.toLocaleString()} />
        <StatCard label="Não faturáveis" value={metrics.non_billable_requests.toLocaleString()} />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="font-semibold text-gray-900 mb-4">Requisições por categoria</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={barData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h2 className="font-semibold text-gray-900 mb-4">Taxa de sucesso vs erros</h2>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                {pieData.map((_, i) => (
                  <Cell key={i} fill={i === 0 ? "#22c55e" : "#ef4444"} />
                ))}
              </Pie>
              <Legend />
              <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
