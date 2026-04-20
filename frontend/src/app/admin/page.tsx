"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getAdminMetrics, getClients, getApis, getAdminLogs } from "@/lib/api";

type DashboardData = {
  totalClients: number;
  totalRequests: number;
  successRate: number;
  activeApis: number;
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

const actionCards = [
  {
    href: "/admin/clients",
    icon: "group",
    title: "Manage Clientes",
    desc: "View and edit partner access",
    gradient: true,
  },
  {
    href: "/admin/apis",
    icon: "api",
    title: "Explore APIs",
    desc: "Configure bridge endpoints",
    gradient: false,
  },
  {
    href: "/admin/permissions",
    icon: "vpn_key",
    title: "Permissions",
    desc: "Security & authentication",
    gradient: false,
  },
  {
    href: "/admin/metrics",
    icon: "analytics",
    title: "Analytics",
    desc: "Deep usage insights",
    gradient: false,
  },
];

function statusIcon(statusCode: number) {
  if (statusCode >= 500) return { icon: "report", isError: true };
  if (statusCode !== 200) return { icon: "warning", isError: true };
  return { icon: "dns", isError: false };
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return "—";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} minute${mins > 1 ? "s" : ""} ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hour${hrs > 1 ? "s" : ""} ago`;
  return `${Math.floor(hrs / 24)} days ago`;
}

export default function AdminPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [logs, setLogs] = useState<LogItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    Promise.all([
      getClients(),
      getAdminMetrics({ since: today.toISOString() }),
      getApis(),
      getAdminLogs(0, 5),
    ])
      .then(([clients, metrics, apis, logsRes]) => {
        const activeApis = apis.items.filter((a) => a.status === "active").length;
        const errorRate = metrics.error_rate;
        setData({
          totalClients: clients.total,
          totalRequests: metrics.total_requests,
          successRate: Math.max(0, 100 - errorRate),
          activeApis,
        });
        setLogs(logsRes.items);
      })
      .finally(() => setLoading(false));
  }, []);

  const metricCards = data
    ? [
        { label: "Total Clients", value: data.totalClients.toLocaleString() },
        { label: "API Calls Today", value: data.totalRequests.toLocaleString() },
        { label: "Success Rate", value: `${data.successRate.toFixed(2)}%`, dot: true },
        { label: "Active APIs", value: String(data.activeApis), tag: "Live" },
      ]
    : [
        { label: "Total Clients", value: "—" },
        { label: "API Calls Today", value: "—" },
        { label: "Success Rate", value: "—", dot: false },
        { label: "Active APIs", value: "—", tag: "Live" },
      ];

  return (
    <div>
      <div className="mb-10">
        <h1 className="text-4xl font-extrabold font-headline tracking-tight text-on-surface mb-2">
          Welcome back, Architect.
        </h1>
        <p className="text-on-surface-variant max-w-2xl">
          Monitor your bridge performance and system health across all integrated endpoints in real-time.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12">
        {metricCards.map((card, i) => (
          <div
            key={i}
            className={`bg-surface-container-lowest p-6 rounded-xl relative overflow-hidden group ${i === 2 ? "border-b-4 border-primary" : ""}`}
          >
            <div className="absolute -right-4 -top-4 w-24 h-24 bg-primary/5 rounded-full group-hover:scale-150 transition-transform duration-500" />
            <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-4">{card.label}</p>
            <div className="flex items-end gap-3">
              {loading ? (
                <span className="text-4xl font-black font-headline text-on-surface animate-pulse">…</span>
              ) : (
                <span className="text-4xl font-black font-headline text-on-surface">{card.value}</span>
              )}
              {"dot" in card && card.dot && (
                <div className="w-2 h-2 rounded-full bg-secondary mb-3 shadow-[0_0_8px_rgba(0,95,175,0.5)]" />
              )}
              {"tag" in card && card.tag && (
                <span className="text-slate-400 font-bold text-sm mb-1">{card.tag}</span>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
        {actionCards.map((card) => (
          <Link
            key={card.href}
            href={card.href}
            className={`p-8 rounded-xl text-left flex flex-col justify-between h-48 transition-all ${
              card.gradient
                ? "bg-gradient-to-br from-primary to-primary-container text-white hover:shadow-xl hover:shadow-primary/20"
                : "bg-surface-container-low text-on-surface hover:bg-surface-container-high"
            }`}
          >
            <span className={`material-symbols-outlined text-4xl ${card.gradient ? "" : "text-primary"}`}>
              {card.icon}
            </span>
            <div>
              <h3 className={`text-xl font-bold font-headline mb-1 ${card.gradient ? "" : "text-primary"}`}>
                {card.title}
              </h3>
              <p className={`text-sm ${card.gradient ? "text-white/70" : "text-on-surface-variant"}`}>
                {card.desc}
              </p>
            </div>
          </Link>
        ))}
      </div>

      <div>
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-bold font-headline">Recent Activity</h3>
          <Link href="/admin/metrics" className="text-sm font-bold text-primary flex items-center gap-1">
            View All <span className="material-symbols-outlined text-sm">arrow_forward</span>
          </Link>
        </div>
        <div className="space-y-1">
          {loading ? (
            <div className="p-4 text-on-surface-variant text-sm animate-pulse">Loading activity…</div>
          ) : logs.length === 0 ? (
            <div className="p-4 text-on-surface-variant text-sm">No recent requests.</div>
          ) : (
            logs.map((log) => {
              const { icon, isError } = statusIcon(log.status_code);
              return (
                <div key={log.correlation_id} className="flex items-center gap-4 p-4 hover:bg-surface-container-low transition-colors rounded-xl">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${isError ? "bg-error-container" : "bg-surface-container-high"}`}>
                    <span className={`material-symbols-outlined text-xl ${isError ? "text-error" : "text-primary"}`}>
                      {icon}
                    </span>
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-semibold">
                      <span className="font-mono">{log.method}</span>{" "}
                      <span className={isError ? "text-error" : "text-primary"}>{log.path}</span>
                      {" "}→{" "}
                      <span className={isError ? "text-error font-bold" : "font-bold"}>{log.status_code}</span>
                    </p>
                    <p className="text-xs text-on-surface-variant">
                      {formatRelativeTime(log.created_at)} • {Math.round(log.latency_ms)}ms • client: {log.client_id}
                    </p>
                  </div>
                  <span className="text-xs font-mono text-on-surface-variant bg-surface px-2 py-1 rounded">
                    {log.correlation_id.slice(0, 8)}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
