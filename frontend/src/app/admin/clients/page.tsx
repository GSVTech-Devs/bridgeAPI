"use client";

import { useEffect, useState } from "react";
import { getClients, approveClient, rejectClient } from "@/lib/api";

type Client = { id: string; name: string; email: string; status: string };

const statusBadge: Record<string, string> = {
  active:   "badge-green",
  pending:  "badge-yellow",
  rejected: "badge-red",
};

const statusLabel: Record<string, string> = {
  active:   "Ativo",
  pending:  "Pendente",
  rejected: "Rejeitado",
};

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

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Clientes</h1>
        <p className="text-gray-500 mt-1">Gerencie e aprove os clientes da plataforma.</p>
      </div>

      <div className="card p-0 overflow-hidden">
        {loading && (
          <div className="flex items-center justify-center py-16 text-gray-400">
            <svg className="animate-spin w-6 h-6 mr-2" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
            </svg>
            Carregando…
          </div>
        )}
        {error && <div role="alert" className="p-6 text-red-600 bg-red-50">{error}</div>}
        {!loading && !error && (
          <table className="table-auto w-full">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Email</th>
                <th>Status</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {clients.length === 0 && (
                <tr><td colSpan={4} className="text-center py-10 text-gray-400">Nenhum cliente cadastrado</td></tr>
              )}
              {clients.map((c) => (
                <tr key={c.id}>
                  <td className="font-medium text-gray-900">{c.name}</td>
                  <td className="text-gray-500">{c.email}</td>
                  <td>
                    <span className={statusBadge[c.status] ?? "badge-gray"}>
                      {statusLabel[c.status] ?? c.status}
                    </span>
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      {c.status === "pending" && (
                        <>
                          <button
                            onClick={() => handleApprove(c.id)}
                            disabled={actionLoading === c.id + "-approve"}
                            className="btn-success btn-sm"
                          >
                            Aprovar
                          </button>
                          <button
                            onClick={() => handleReject(c.id)}
                            disabled={actionLoading === c.id + "-reject"}
                            className="btn-danger btn-sm"
                          >
                            Rejeitar
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
