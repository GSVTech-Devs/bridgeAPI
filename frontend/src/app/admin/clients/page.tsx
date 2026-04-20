"use client";

import { useEffect, useState } from "react";
import { getClients, approveClient, rejectClient, blockClient, unblockClient } from "@/lib/api";

type Client = { id: string; name: string; email: string; status: string };

const statusConfig: Record<string, { dot: string; label: string }> = {
  active:   { dot: "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]", label: "Active" },
  pending:  { dot: "bg-amber-500 animate-pulse", label: "Pending Approval" },
  rejected: { dot: "bg-error shadow-[0_0_8px_rgba(186,26,26,0.4)]", label: "Rejected" },
  blocked:  { dot: "bg-slate-400", label: "Blocked" },
};

function Spinner() {
  return (
    <div className="flex items-center justify-center py-20 text-on-surface-variant gap-2">
      <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
      </svg>
      Carregando…
    </div>
  );
}

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  async function load() {
    try {
      const data = await getClients();
      setClients(data.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao carregar");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleApprove(id: string) {
    setActionLoading(id + "-approve");
    try {
      await approveClient(id);
      setClients((prev) => prev.map((c) => c.id === id ? { ...c, status: "active" } : c));
    } finally { setActionLoading(null); }
  }

  async function handleReject(id: string) {
    setActionLoading(id + "-reject");
    try {
      await rejectClient(id);
      setClients((prev) => prev.map((c) => c.id === id ? { ...c, status: "rejected" } : c));
    } finally { setActionLoading(null); }
  }

  async function handleBlock(id: string) {
    setActionLoading(id + "-block");
    try {
      await blockClient(id);
      setClients((prev) => prev.map((c) => c.id === id ? { ...c, status: "blocked" } : c));
    } finally { setActionLoading(null); }
  }

  async function handleUnblock(id: string) {
    setActionLoading(id + "-unblock");
    try {
      await unblockClient(id);
      setClients((prev) => prev.map((c) => c.id === id ? { ...c, status: "active" } : c));
    } finally { setActionLoading(null); }
  }

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Page header + stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="md:col-span-2 space-y-2">
          <h2 className="text-4xl font-extrabold tracking-tight text-on-surface font-headline">Client Management</h2>
          <p className="text-on-surface-variant max-w-md">
            Orchestrate access levels, monitor status, and manage developer credentials.
          </p>
        </div>
        <div className="bg-surface-container-lowest p-6 rounded-xl flex flex-col justify-between">
          <span className="text-xs font-bold text-outline uppercase tracking-wider">Active Clients</span>
          <div className="flex items-end justify-between">
            <span className="text-3xl font-black text-primary">
              {clients.filter((c) => c.status === "active").length}
            </span>
            <span className="text-xs text-green-600 bg-green-100 px-2 py-0.5 rounded-full">Live</span>
          </div>
        </div>
        <div className="bg-surface-container-lowest p-6 rounded-xl flex flex-col justify-between">
          <span className="text-xs font-bold text-outline uppercase tracking-wider">Pending Tasks</span>
          <div className="flex items-end justify-between">
            <span className="text-3xl font-black text-tertiary">
              {clients.filter((c) => c.status === "pending").length}
            </span>
            <span className="material-symbols-outlined text-tertiary">pending_actions</span>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-surface-container-lowest rounded-xl overflow-hidden">
        {/* Filters bar */}
        <div className="px-6 py-4 flex items-center justify-between gap-4 bg-surface-container-low/30">
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-outline text-lg">filter_list</span>
            <input
              className="pl-10 pr-4 py-2 bg-white rounded-lg border border-outline-variant/30 focus:border-primary focus:ring-0 text-sm w-72 transition-all outline-none"
              placeholder="Filter by name or email..."
            />
          </div>
          <button className="flex items-center gap-2 px-6 py-2 bg-gradient-to-br from-primary to-primary-container text-white rounded-lg font-bold text-sm hover:scale-[1.02] transition-all shadow-sm">
            <span className="material-symbols-outlined text-sm">person_add</span>
            Onboard Client
          </button>
        </div>

        {loading && <Spinner />}
        {error && <div role="alert" className="p-6 text-error bg-error-container/20">{error}</div>}

        {!loading && !error && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-surface-container-low/50">
                    {["Client & Company", "Email", "Status", "Actions"].map((h) => (
                      <th key={h} className="px-6 py-4 text-xs font-bold text-outline uppercase tracking-widest">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-outline-variant/10">
                  {clients.length === 0 && (
                    <tr>
                      <td colSpan={4} className="text-center py-12 text-on-surface-variant">
                        Nenhum cliente cadastrado
                      </td>
                    </tr>
                  )}
                  {clients.map((c) => {
                    const cfg = statusConfig[c.status] ?? { dot: "bg-outline", label: c.status };
                    const initials = c.name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();
                    return (
                      <tr key={c.id} className="hover:bg-surface-container-low/20 transition-colors group">
                        <td className="px-6 py-5">
                          <div className="flex items-center gap-3">
                            <div className="h-10 w-10 rounded-full bg-secondary-fixed flex items-center justify-center text-secondary font-bold text-sm">
                              {initials}
                            </div>
                            <span className="text-sm font-bold text-on-surface">{c.name}</span>
                          </div>
                        </td>
                        <td className="px-6 py-5 text-sm text-outline">{c.email}</td>
                        <td className="px-6 py-5">
                          <div className="flex items-center gap-1.5">
                            <span className={`h-2 w-2 rounded-full ${cfg.dot}`} />
                            <span className="text-sm font-medium text-on-surface">{cfg.label}</span>
                          </div>
                        </td>
                        <td className="px-6 py-5">
                          <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            {(c.status === "pending" || c.status === "rejected") && (
                              <button
                                onClick={() => handleApprove(c.id)}
                                disabled={actionLoading === c.id + "-approve"}
                                className="px-3 py-1 bg-tertiary text-white rounded-md text-xs font-bold shadow-sm hover:brightness-110 transition-all disabled:opacity-50"
                              >
                                {actionLoading === c.id + "-approve" ? "…" : "Approve"}
                              </button>
                            )}
                            {c.status === "pending" && (
                              <button
                                onClick={() => handleReject(c.id)}
                                disabled={actionLoading === c.id + "-reject"}
                                className="px-3 py-1 bg-error-container text-on-error-container rounded-md text-xs font-bold hover:brightness-95 transition-all disabled:opacity-50"
                              >
                                {actionLoading === c.id + "-reject" ? "…" : "Reject"}
                              </button>
                            )}
                            {c.status === "active" && (
                              <button
                                onClick={() => handleBlock(c.id)}
                                disabled={actionLoading === c.id + "-block"}
                                className="px-3 py-1 bg-error-container text-on-error-container rounded-md text-xs font-bold hover:brightness-95 transition-all disabled:opacity-50"
                              >
                                {actionLoading === c.id + "-block" ? "…" : "Block"}
                              </button>
                            )}
                            {c.status === "blocked" && (
                              <button
                                onClick={() => handleUnblock(c.id)}
                                disabled={actionLoading === c.id + "-unblock"}
                                className="px-3 py-1 bg-tertiary text-white rounded-md text-xs font-bold shadow-sm hover:brightness-110 transition-all disabled:opacity-50"
                              >
                                {actionLoading === c.id + "-unblock" ? "…" : "Unblock"}
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {/* Pagination footer */}
            <div className="px-6 py-4 flex items-center justify-between border-t border-outline-variant/10">
              <span className="text-xs font-medium text-outline">
                Showing {clients.length} client{clients.length !== 1 ? "s" : ""}
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
