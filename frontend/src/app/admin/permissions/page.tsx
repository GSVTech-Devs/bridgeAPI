"use client";

import { useEffect, useState } from "react";
import { getClients, getApis, getPermissions, grantPermission, revokePermission } from "@/lib/api";

type Client = { id: string; name: string; email: string; status: string };
type Api = { id: string; name: string; base_url: string; status: string; auth_type: string };
type Permission = { client_id: string; api_id: string; client_name: string; api_name: string; status: string };

export default function PermissionsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [apis, setApis] = useState<Api[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedClient, setSelectedClient] = useState("");
  const [selectedApi, setSelectedApi] = useState("");
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  async function load() {
    try {
      const [clientsData, apisData, permsData] = await Promise.all([
        getClients(),
        getApis(),
        getPermissions(),
      ]);
      setClients(clientsData.items.filter((c) => c.status === "active"));
      setApis(apisData.items.filter((a) => a.status === "active"));
      setPermissions(permsData.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao carregar");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleGrant(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedClient || !selectedApi) return;
    setFormLoading(true);
    setFormError(null);
    try {
      await grantPermission(selectedClient, selectedApi);
      await load();
      setSelectedClient("");
      setSelectedApi("");
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Erro ao conceder acesso");
    } finally {
      setFormLoading(false);
    }
  }

  async function handleRevoke(clientId: string, apiId: string) {
    const key = `${clientId}-${apiId}`;
    setActionLoading(key);
    try {
      await revokePermission(clientId, apiId);
      setPermissions((prev) =>
        prev.map((p) =>
          p.client_id === clientId && p.api_id === apiId ? { ...p, status: "revoked" } : p
        )
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao revogar");
    } finally {
      setActionLoading(null);
    }
  }

  const activePerms = permissions.filter((p) => p.status === "active");

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Permissões</h1>
        <p className="text-gray-500 mt-1">Conceda e revogue acesso de clientes às APIs.</p>
      </div>

      {/* Grant form */}
      <div className="card mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Conceder Acesso</h2>
        {formError && (
          <div role="alert" className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {formError}
          </div>
        )}
        <form onSubmit={handleGrant} className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1">
            <label className="label">Cliente</label>
            <select
              className="input"
              value={selectedClient}
              onChange={(e) => setSelectedClient(e.target.value)}
              required
            >
              <option value="">Selecione um cliente…</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>{c.name} — {c.email}</option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <label className="label">API</label>
            <select
              className="input"
              value={selectedApi}
              onChange={(e) => setSelectedApi(e.target.value)}
              required
            >
              <option value="">Selecione uma API…</option>
              {apis.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <button type="submit" disabled={formLoading || !selectedClient || !selectedApi} className="btn-primary">
              {formLoading ? "Concedendo…" : "Conceder"}
            </button>
          </div>
        </form>
      </div>

      {/* Permissions table */}
      <div className="card p-0 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">Acessos ativos</h2>
        </div>
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
                <th>Cliente</th>
                <th>API</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {activePerms.length === 0 && (
                <tr><td colSpan={3} className="text-center py-10 text-gray-400">Nenhuma permissão ativa</td></tr>
              )}
              {activePerms.map((p) => (
                <tr key={`${p.client_id}-${p.api_id}`}>
                  <td className="font-medium text-gray-900">{p.client_name}</td>
                  <td>
                    <span className="badge-gray">{p.api_name}</span>
                  </td>
                  <td>
                    <button
                      onClick={() => handleRevoke(p.client_id, p.api_id)}
                      disabled={actionLoading === `${p.client_id}-${p.api_id}`}
                      className="btn-danger btn-sm"
                    >
                      {actionLoading === `${p.client_id}-${p.api_id}` ? "…" : "Revogar"}
                    </button>
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
