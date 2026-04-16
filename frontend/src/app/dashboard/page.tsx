"use client";

import { useEffect, useState } from "react";
import { getClientDashboard } from "@/lib/api";
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

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getClientDashboard()
      .then(setMetrics)
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
        { name: "Sucesso", value: Math.max(0, 100 - metrics.error_rate * 100) },
        { name: "Erros", value: metrics.error_rate * 100 },
      ]
    : [];

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-10 flex justify-between items-end">
        <div>
          <h2 className="font-headline text-3xl font-extrabold text-on-surface tracking-tight">Overview</h2>
          <p className="text-on-surface-variant mt-1">Real-time metrics for your API consumption.</p>
        </div>
        <div className="flex gap-3">
          <button className="bg-surface-container-high text-on-surface px-4 py-2 rounded-lg text-sm font-medium hover:bg-surface-container-highest transition-colors">
            Last 30 Days
          </button>
          <button className="primary-gradient text-white px-4 py-2 rounded-lg text-sm font-medium shadow-[0_4px_14px_0_rgba(43,91,181,0.39)]">
            Export Report
          </button>
        </div>
      </div>

      {error && (
        <div role="alert" className="mb-6 p-4 bg-error-container text-on-error-container rounded-xl text-sm">
          Não foi possível carregar as métricas: {error}
        </div>
      )}

      {metrics && (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-4 gap-6 mb-10">
            {[
              { label: "Total Requests", value: metrics.total_requests.toLocaleString(), icon: "data_usage", color: "text-primary" },
              { label: "Success Rate", value: `${(100 - metrics.error_rate * 100).toFixed(1)}%`, icon: "check_circle", color: "text-green-500" },
              { label: "Avg Latency", value: `${Math.round(metrics.avg_latency_ms)}ms`, icon: "timer", color: "text-tertiary" },
              { label: "Total Cost", value: `$${metrics.total_cost.toFixed(4)}`, icon: "payments", color: "text-primary" },
            ].map((card) => (
              <div key={card.label} className="bg-surface-container-lowest p-6 rounded-xl flex flex-col justify-between h-36">
                <div className="flex justify-between items-start">
                  <span className="text-sm text-on-surface-variant">{card.label}</span>
                  <span className={`material-symbols-outlined text-xl ${card.color}`}>{card.icon}</span>
                </div>
                <div>
                  <div className="font-headline text-3xl font-extrabold text-on-surface tracking-tight">{card.value}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Charts */}
          <div className="grid grid-cols-3 gap-6 mb-10">
            <div className="col-span-2 bg-surface-container-lowest p-6 rounded-xl h-72 flex flex-col">
              <h3 className="font-headline font-bold text-lg text-on-surface mb-4">Requests Over Time</h3>
              <div className="flex-1">
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
            </div>

            <div className="bg-surface-container-lowest p-6 rounded-xl flex flex-col">
              <h3 className="font-headline font-bold text-lg text-on-surface mb-4">Sucesso vs Erros</h3>
              <div className="flex-1">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={75} label>
                      <Cell fill="#22c55e" />
                      <Cell fill="#ba1a1a" />
                    </Pie>
                    <Legend />
                    <Tooltip formatter={(v: unknown) => `${(v as number).toFixed(1)}%`} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Quick links */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Link
          href="/dashboard/catalog"
          className="bg-surface-container-lowest p-6 rounded-xl flex items-center gap-4 hover:bg-surface-container-low transition-colors group"
        >
          <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
            <span className="material-symbols-outlined">api</span>
          </div>
          <div>
            <p className="font-semibold text-on-surface group-hover:text-primary transition-colors">Catálogo de APIs</p>
            <p className="text-sm text-on-surface-variant">Veja as APIs disponíveis para você</p>
          </div>
        </Link>
        <Link
          href="/dashboard/keys"
          className="bg-surface-container-lowest p-6 rounded-xl flex items-center gap-4 hover:bg-surface-container-low transition-colors group"
        >
          <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
            <span className="material-symbols-outlined">vpn_key</span>
          </div>
          <div>
            <p className="font-semibold text-on-surface group-hover:text-primary transition-colors">Minhas Chaves</p>
            <p className="text-sm text-on-surface-variant">Gerencie suas chaves de API</p>
          </div>
        </Link>
      </div>
    </div>
  );
}
