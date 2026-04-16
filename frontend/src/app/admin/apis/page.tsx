"use client";

import { useEffect, useState } from "react";
import { getApis, createApi, enableApi, disableApi } from "@/lib/api";

type Api = { id: string; name: string; base_url: string; status: string; auth_type: string };

const initialForm = { name: "", base_url: "", auth_type: "api_key", master_key: "", description: "" };

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
    setActionLoading(api.id);
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
    <div className="space-y-8">
      {/* Page header */}
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-4xl font-extrabold font-headline tracking-tighter text-on-surface">API Catalog</h2>
          <p className="text-on-surface-variant mt-2 text-lg">Manage, monitor and connect your technical assets through Bridge.</p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="primary-gradient text-white px-6 py-3 rounded-xl font-bold flex items-center gap-2 hover:scale-[1.02] transition-transform shadow-lg shadow-primary/20"
        >
          <span className="material-symbols-outlined">add_circle</span>
          {showForm ? "Cancelar" : "Register New API"}
        </button>
      </div>

      {formSuccess && (
        <div className="p-4 bg-green-100 text-green-800 rounded-xl text-sm font-medium">
          API cadastrada com sucesso!
        </div>
      )}

      {/* Registration form */}
      {showForm && (
        <section className="bg-surface-container-lowest rounded-xl p-10 border border-outline-variant/15 relative overflow-hidden">
          <div className="max-w-4xl mx-auto">
            <div className="mb-8 flex items-center gap-4">
              <div className="w-12 h-12 rounded-2xl primary-gradient flex items-center justify-center text-white shadow-lg">
                <span className="material-symbols-outlined text-2xl">add_link</span>
              </div>
              <div>
                <h3 className="text-2xl font-extrabold font-headline text-on-surface">Register New API</h3>
                <p className="text-on-surface-variant">Configure your endpoint transformation and pricing structure.</p>
              </div>
            </div>

            {formError && (
              <div role="alert" className="mb-6 p-3 bg-error-container rounded-lg text-on-error-container text-sm">
                {formError}
              </div>
            )}

            <form onSubmit={handleCreate} className="grid grid-cols-2 gap-x-10 gap-y-6">
              <div className="space-y-2">
                <label className="block text-sm font-bold text-on-surface-variant">API Name</label>
                <input
                  className="w-full bg-surface-container-low border-none rounded-xl py-4 px-5 text-on-surface placeholder:text-outline-variant focus:ring-2 focus:ring-primary-container transition-all outline-none text-sm"
                  placeholder="e.g. Real-Time Finance Connector"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="block text-sm font-bold text-on-surface-variant">Endpoint URL</label>
                <input
                  className="w-full bg-surface-container-low border-none rounded-xl py-4 px-5 text-on-surface placeholder:text-outline-variant focus:ring-2 focus:ring-primary-container transition-all outline-none text-sm"
                  placeholder="https://api.provider.com/v1"
                  value={form.base_url}
                  onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value }))}
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="block text-sm font-bold text-on-surface-variant">Auth Type</label>
                <select
                  className="w-full bg-surface-container-low border-none rounded-xl py-4 px-5 text-on-surface focus:ring-2 focus:ring-primary-container transition-all outline-none text-sm"
                  value={form.auth_type}
                  onChange={(e) => setForm((f) => ({ ...f, auth_type: e.target.value }))}
                >
                  <option value="api_key">API Key</option>
                  <option value="bearer">Bearer Token</option>
                  <option value="basic">Basic Auth</option>
                  <option value="none">Sem autenticação</option>
                </select>
              </div>
              <div className="space-y-2">
                <label className="block text-sm font-bold text-on-surface-variant">Master Key / Token</label>
                <div className="relative">
                  <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant text-[20px]">vpn_key</span>
                  <input
                    className="w-full bg-surface-container-low border-none rounded-xl py-4 pl-12 pr-5 text-on-surface focus:ring-2 focus:ring-primary-container transition-all outline-none font-mono text-sm"
                    type="password"
                    placeholder="••••••••••••••••"
                    value={form.master_key}
                    onChange={(e) => setForm((f) => ({ ...f, master_key: e.target.value }))}
                    required
                  />
                </div>
              </div>
              <div className="col-span-2 space-y-2">
                <label className="block text-sm font-bold text-on-surface-variant">Description (optional)</label>
                <input
                  className="w-full bg-surface-container-low border-none rounded-xl py-4 px-5 text-on-surface placeholder:text-outline-variant focus:ring-2 focus:ring-primary-container transition-all outline-none text-sm"
                  placeholder="Breve descrição da API"
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                />
              </div>
              <div className="col-span-2 flex justify-end gap-4 pt-2">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="px-8 py-4 rounded-xl font-bold text-on-surface-variant hover:bg-surface-container-high transition-colors"
                >
                  Discard
                </button>
                <button
                  type="submit"
                  disabled={formLoading}
                  className="primary-gradient text-white px-12 py-4 rounded-xl font-extrabold shadow-xl shadow-primary/30 hover:scale-[1.03] transition-transform disabled:opacity-70"
                >
                  {formLoading ? "Cadastrando…" : "Deploy API Bridge"}
                </button>
              </div>
            </form>
          </div>
          <div className="absolute -top-24 -right-24 w-64 h-64 bg-primary/5 rounded-full blur-3xl" />
        </section>
      )}

      {/* APIs table */}
      <div className="bg-surface-container-lowest rounded-xl overflow-hidden">
        <div className="px-6 py-5 flex items-center justify-between">
          <h3 className="font-bold text-xl font-headline">Connected Endpoints</h3>
          <span className="text-sm text-primary font-bold">Live Status</span>
        </div>

        {loading && <Spinner />}
        {error && <div role="alert" className="p-6 text-error bg-error-container/20">{error}</div>}

        {!loading && !error && (
          <div className="space-y-2 px-4 pb-4">
            {/* Header row */}
            <div className="grid grid-cols-4 px-4 py-3 text-xs font-bold uppercase tracking-wider text-on-surface-variant/60">
              <div>API Service</div>
              <div>Base URL</div>
              <div>Status</div>
              <div className="text-right">Actions</div>
            </div>

            {apis.length === 0 && (
              <div className="text-center py-10 text-on-surface-variant">Nenhuma API cadastrada</div>
            )}

            {apis.map((api) => (
              <div
                key={api.id}
                className="grid grid-cols-4 items-center px-4 py-5 bg-surface-container-low rounded-xl hover:bg-surface-container-high transition-colors group"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                    <span className="material-symbols-outlined text-[20px]">dataset</span>
                  </div>
                  <div>
                    <p className="font-bold text-sm">{api.name}</p>
                    <p className="text-xs text-on-surface-variant">{api.auth_type}</p>
                  </div>
                </div>
                <div className="font-mono text-xs text-on-surface-variant truncate pr-4">{api.base_url}</div>
                <div>
                  <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${
                    api.status === "active" ? "bg-green-100 text-green-700" : "bg-surface-variant text-on-surface-variant"
                  }`}>
                    {api.status === "active" ? "Active" : "Inactive"}
                  </span>
                </div>
                <div className="text-right opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => handleToggle(api)}
                    disabled={actionLoading === api.id}
                    className={`p-2 rounded-lg text-sm font-bold transition-colors ${
                      api.status === "active"
                        ? "hover:bg-error-container text-error"
                        : "hover:bg-green-100 text-green-700"
                    }`}
                  >
                    <span className="material-symbols-outlined text-sm">
                      {actionLoading === api.id ? "hourglass_empty" : api.status === "active" ? "toggle_off" : "toggle_on"}
                    </span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
