"use client";

import { useEffect, useState } from "react";
import { getApis, createApi, enableApi, disableApi } from "@/lib/api";

type Api = { id: string; name: string; base_url: string; status: string; auth_type: string };

const statusBadge: Record<string, string> = {
  active:   "badge-green",
  inactive: "badge-red",
};

const statusLabel: Record<string, string> = {
  active:   "Ativa",
  inactive: "Inativa",
};

const initialForm = { name: "", base_url: "", auth_type: "api_key", master_key: "", description: "" };

export default function ApisPage() {
  const [apis, setApis] = useState<Api[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(initialForm);
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState(false);

  async function load() {
    try {
      const data = await getApis();
      setApis(data.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao carregar");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleToggle(api: Api) {
    const key = api.id + "-toggle";
    setActionLoading(key);
    try {
      if (api.status === "active") {
        await disableApi(api.id);
        setApis((prev) => prev.map((a) => a.id === api.id ? { ...a, status: "inactive" } : a));
      } else {
        await enableApi(api.id);
        setApis((prev) => prev.map((a) => a.id === api.id ? { ...a, status: "active" } : a));
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro na operação");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormLoading(true);
    setFormError(null);
    try {
      const api = await createApi(form);
      setApis((prev) => [...prev, api]);
      setForm(initialForm);
      setShowForm(false);
      setFormSuccess(true);
      setTimeout(() => setFormSuccess(false), 3000);
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Erro ao cadastrar");
    } finally {
      setFormLoading(false);
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">APIs</h1>
          <p className="text-gray-500 mt-1">Cadastre e gerencie as APIs externas da plataforma.</p>
        </div>
        <button onClick={() => setShowForm((v) => !v)} className="btn-primary">
          {showForm ? "Cancelar" : "+ Nova API"}
        </button>
      </div>

      {formSuccess && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
          API cadastrada com sucesso!
        </div>
      )}

      {/* Registration form */}
      {showForm && (
        <div className="card mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Nova API</h2>
          {formError && (
            <div role="alert" className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {formError}
            </div>
          )}
          <form onSubmit={handleCreate} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Nome</label>
              <input
                className="input"
                placeholder="Ex: OpenWeather"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                required
              />
            </div>
            <div>
              <label className="label">Base URL</label>
              <input
                className="input"
                placeholder="https://api.exemplo.com/v1"
                value={form.base_url}
                onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value }))}
                required
              />
            </div>
            <div>
              <label className="label">Tipo de autenticação</label>
              <select
                className="input"
                value={form.auth_type}
                onChange={(e) => setForm((f) => ({ ...f, auth_type: e.target.value }))}
              >
                <option value="api_key">API Key</option>
                <option value="bearer">Bearer Token</option>
                <option value="basic">Basic Auth</option>
                <option value="none">Sem autenticação</option>
              </select>
            </div>
            <div>
              <label className="label">Master Key / Token</label>
              <input
                className="input"
                type="password"
                placeholder="Chave secreta da API"
                value={form.master_key}
                onChange={(e) => setForm((f) => ({ ...f, master_key: e.target.value }))}
                required
              />
            </div>
            <div className="md:col-span-2">
              <label className="label">Descrição (opcional)</label>
              <input
                className="input"
                placeholder="Breve descrição da API"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              />
            </div>
            <div className="md:col-span-2 flex justify-end gap-3">
              <button type="button" onClick={() => setShowForm(false)} className="btn-secondary">
                Cancelar
              </button>
              <button type="submit" disabled={formLoading} className="btn-primary">
                {formLoading ? "Cadastrando…" : "Cadastrar API"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* APIs table */}
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
                <th>Base URL</th>
                <th>Auth</th>
                <th>Status</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {apis.length === 0 && (
                <tr><td colSpan={5} className="text-center py-10 text-gray-400">Nenhuma API cadastrada</td></tr>
              )}
              {apis.map((api) => (
                <tr key={api.id}>
                  <td className="font-medium text-gray-900">{api.name}</td>
                  <td className="text-gray-500 text-sm font-mono">{api.base_url}</td>
                  <td>
                    <span className="badge-gray">{api.auth_type}</span>
                  </td>
                  <td>
                    <span className={statusBadge[api.status] ?? "badge-gray"}>
                      {statusLabel[api.status] ?? api.status}
                    </span>
                  </td>
                  <td>
                    <button
                      onClick={() => handleToggle(api)}
                      disabled={actionLoading === api.id + "-toggle"}
                      className={api.status === "active" ? "btn-danger btn-sm" : "btn-success btn-sm"}
                    >
                      {actionLoading === api.id + "-toggle"
                        ? "…"
                        : api.status === "active" ? "Desativar" : "Ativar"}
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
