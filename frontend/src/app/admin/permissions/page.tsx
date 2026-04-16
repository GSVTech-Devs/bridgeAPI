"use client";

import { useEffect, useState } from "react";
import { getClients, getApis, getPermissions, grantPermission, revokePermission } from "@/lib/api";

type Client = { id: string; name: string; email: string; status: string };
type Api = { id: string; name: string; base_url: string; status: string; auth_type: string };
type Permission = { client_id: string; api_id: string; client_name: string; api_name: string; status: string };

const apiIcons = ["payments", "analytics", "cloud_sync", "shield_lock", "dataset", "monitoring"];

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
    <section className="space-y-10">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <nav className="flex items-center gap-2 text-xs font-bold text-primary mb-2 tracking-widest uppercase">
            <span>Access Control</span>
            <span className="material-symbols-outlined text-[10px]">chevron_right</span>
            <span className="text-on-surface-variant opacity-60">Permissions Mapping</span>
          </nav>
          <h2 className="text-4xl font-extrabold tracking-tight text-on-surface font-headline">API Entitlements</h2>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => { setSelectedClient(""); setSelectedApi(""); }}
            className="px-6 py-2.5 rounded-xl bg-surface-container-high text-on-surface font-semibold text-sm hover:brightness-95 transition-all"
          >
            Reset Changes
          </button>
          <button
            onClick={() => {
              const fakeEvent = { preventDefault: () => {} } as React.FormEvent;
              handleGrant(fakeEvent);
            }}
            disabled={formLoading || !selectedClient || !selectedApi}
            className="px-8 py-2.5 rounded-xl bg-gradient-to-br from-primary to-primary-container text-white font-bold text-sm shadow-md shadow-primary/20 hover:scale-[1.02] transition-all disabled:opacity-50"
          >
            Apply Permissions
          </button>
        </div>
      </div>

      {error && <div role="alert" className="p-4 bg-error-container text-on-error-container rounded-xl text-sm">{error}</div>}

      <div className="grid grid-cols-12 gap-8 items-start">
        {/* Left: Client selection */}
        <div className="col-span-12 lg:col-span-4 space-y-4">
          <div className="bg-surface-container-low rounded-3xl p-6">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold text-on-surface">Select Client</h3>
              <span className="bg-surface-container-high px-3 py-1 rounded-full text-[10px] font-black text-primary">
                {clients.length} ACTIVE
              </span>
            </div>

            {formError && (
              <div role="alert" className="mb-4 p-3 bg-error-container rounded-lg text-on-error-container text-xs">
                {formError}
              </div>
            )}

            {loading ? (
              <div className="text-center py-8 text-on-surface-variant text-sm">Carregando…</div>
            ) : (
              <div className="space-y-3">
                {clients.map((c) => {
                  const active = selectedClient === c.id;
                  return (
                    <div
                      key={c.id}
                      onClick={() => setSelectedClient(c.id)}
                      className={`p-4 rounded-2xl flex items-center gap-4 cursor-pointer transition-all ${
                        active
                          ? "bg-surface-container-lowest ring-2 ring-primary ring-offset-4 ring-offset-surface-container-low"
                          : "hover:bg-surface-container-high/50"
                      }`}
                    >
                      <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${active ? "bg-primary/10 text-primary" : "bg-on-surface/5 text-on-surface-variant"}`}>
                        <span className="material-symbols-outlined">business</span>
                      </div>
                      <div className="flex-1">
                        <h4 className={`font-bold text-sm ${active ? "text-on-surface" : "text-on-surface-variant"}`}>
                          {c.name}
                        </h4>
                        <p className="text-xs text-on-surface-variant opacity-60">{c.email}</p>
                      </div>
                      {active && (
                        <span className="material-symbols-outlined text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>
                          check_circle
                        </span>
                      )}
                    </div>
                  );
                })}
                {clients.length === 0 && (
                  <p className="text-center text-sm text-on-surface-variant py-4">Nenhum cliente ativo</p>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right: API permissions matrix */}
        <div className="col-span-12 lg:col-span-8 space-y-6">
          {/* API filter */}
          <div className="flex items-center gap-4">
            <div className="flex-1 relative">
              <input
                className="w-full bg-surface-container-lowest border-none rounded-2xl py-4 pl-12 pr-4 text-sm shadow-sm ring-1 ring-outline-variant/10 focus:ring-2 focus:ring-primary transition-all outline-none"
                placeholder="Search API catalog..."
              />
              <span className="absolute inset-y-0 left-0 pl-4 flex items-center text-slate-400">
                <span className="material-symbols-outlined">filter_list</span>
              </span>
            </div>
          </div>

          {/* API rows */}
          <div className="overflow-hidden">
            <div className="grid grid-cols-12 px-6 mb-4 text-[10px] font-black uppercase tracking-widest text-on-surface-variant opacity-50">
              <div className="col-span-6">API Resource</div>
              <div className="col-span-3 text-center">Status</div>
              <div className="col-span-3 text-right">Action</div>
            </div>

            {loading ? (
              <div className="text-center py-8 text-on-surface-variant text-sm">Carregando…</div>
            ) : (
              <div className="space-y-4">
                {apis.map((api, i) => {
                  const permKey = `${selectedClient}-${api.id}`;
                  const hasAccess = activePerms.some((p) => p.client_id === selectedClient && p.api_id === api.id);
                  return (
                    <div key={api.id} className="grid grid-cols-12 items-center bg-surface-container-lowest p-6 rounded-3xl hover:bg-white transition-all shadow-sm">
                      <div className="col-span-6 flex items-center gap-4">
                        <div className="w-10 h-10 rounded-full bg-tertiary-fixed text-tertiary flex items-center justify-center">
                          <span className="material-symbols-outlined text-sm">{apiIcons[i % apiIcons.length]}</span>
                        </div>
                        <div>
                          <h4 className="font-bold text-base leading-tight">{api.name}</h4>
                          <p className="text-xs text-on-surface-variant">{api.auth_type}</p>
                        </div>
                      </div>
                      <div className="col-span-3 flex justify-center">
                        <div className={`flex items-center gap-2 bg-surface p-1 rounded-full border border-outline-variant/20`}>
                          <div className={`w-4 h-4 rounded-full ${hasAccess ? "bg-primary shadow-[0_0_8px_rgba(43,91,181,0.4)]" : "bg-outline-variant"}`} />
                          <span className={`text-[10px] font-bold pr-2 ${hasAccess ? "text-primary" : "text-on-surface-variant opacity-50"}`}>
                            {hasAccess ? "ENABLED" : "DISABLED"}
                          </span>
                        </div>
                      </div>
                      <div className="col-span-3 flex justify-end gap-2">
                        {hasAccess ? (
                          <button
                            onClick={() => handleRevoke(selectedClient, api.id)}
                            disabled={actionLoading === permKey || !selectedClient}
                            className="px-4 py-2 rounded-xl bg-error-container text-on-error-container text-[11px] font-bold hover:brightness-95 transition-all disabled:opacity-50"
                          >
                            REVOKE
                          </button>
                        ) : (
                          <button
                            onClick={() => setSelectedApi(api.id)}
                            disabled={!selectedClient}
                            className="px-4 py-2 rounded-xl bg-primary text-white text-[11px] font-black disabled:opacity-30 disabled:cursor-not-allowed hover:bg-primary-container transition-colors"
                          >
                            GRANT
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
                {apis.length === 0 && (
                  <div className="text-center py-8 text-on-surface-variant text-sm">Nenhuma API ativa</div>
                )}
              </div>
            )}
          </div>

          {/* Grant selected API button */}
          {selectedClient && selectedApi && (
            <div className="flex justify-end">
              <button
                onClick={() => { const fe = { preventDefault: () => {} } as React.FormEvent; handleGrant(fe); }}
                disabled={formLoading}
                className="px-8 py-3 rounded-xl bg-gradient-to-br from-primary to-primary-container text-white font-bold shadow-md hover:scale-[1.02] transition-all"
              >
                {formLoading ? "Concedendo…" : "Confirmar Grant"}
              </button>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
