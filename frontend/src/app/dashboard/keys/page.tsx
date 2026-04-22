"use client";

import { useEffect, useState } from "react";
import { getCatalog, getKeys, createKey, revokeKey } from "@/lib/api";

type CatalogEntry = { id: string; name: string; slug?: string; base_url: string; status: string };
type Key = { id: string; api_id: string | null; name: string; key_prefix: string; api_key: string | null; status: string; created_at: string };

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  function handle() {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }
  return (
    <button
      onClick={handle}
      title="Copiar chave"
      className="bg-surface-container-highest hover:bg-surface-variant text-on-surface rounded-lg p-2.5 transition-colors flex-shrink-0"
    >
      <span className="material-symbols-outlined text-[20px]">
        {copied ? "check" : "content_copy"}
      </span>
    </button>
  );
}

export default function KeysPage() {
  const [catalog, setCatalog] = useState<CatalogEntry[]>([]);
  const [keys, setKeys] = useState<Key[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [visible, setVisible] = useState<Record<string, boolean>>({});
  const [creating, setCreating] = useState<string | null>(null);
  const [newKeyNames, setNewKeyNames] = useState<Record<string, string>>({});
  const [createErrors, setCreateErrors] = useState<Record<string, string>>({});
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getCatalog(), getKeys()])
      .then(([cat, keyData]) => {
        setCatalog(cat.items);
        setKeys(keyData.items);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  }, []);

  async function handleCreate(apiId: string, e: React.FormEvent) {
    e.preventDefault();
    const name = (newKeyNames[apiId] ?? "").trim();
    if (!name) return;
    setCreating(apiId);
    setCreateErrors((prev) => ({ ...prev, [apiId]: "" }));
    try {
      const created = await createKey(name, apiId);
      setVisible((prev) => ({ ...prev, [created.id]: false }));
      setKeys((prev) => [{ ...created, api_key: created.api_key }, ...prev]);
      setNewKeyNames((prev) => ({ ...prev, [apiId]: "" }));
    } catch (err: unknown) {
      setCreateErrors((prev) => ({
        ...prev,
        [apiId]: err instanceof Error ? err.message : "Erro ao criar chave",
      }));
    } finally {
      setCreating(null);
    }
  }

  async function handleRevoke(id: string) {
    setActionLoading(id);
    try {
      await revokeKey(id);
      setKeys((prev) => prev.map((k) => k.id === id ? { ...k, status: "revoked" } : k));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao revogar");
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-10">
        <h1 className="text-4xl font-headline font-extrabold tracking-tight text-on-surface mb-2">Minhas Chaves de API</h1>
        <p className="text-on-surface-variant text-base max-w-xl">
          Gere e gerencie chaves de acesso por API. Cada chave está vinculada a uma API específica para facilitar o monitoramento.
        </p>
      </div>

      {error && <div role="alert" className="mb-6 p-4 bg-error-container text-on-error-container rounded-xl text-sm">{error}</div>}

      {loading ? (
        <div className="flex items-center justify-center py-16 text-on-surface-variant gap-2">
          <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
          </svg>
          Carregando…
        </div>
      ) : catalog.length === 0 ? (
        <div className="text-center py-16 text-on-surface-variant">
          <span className="material-symbols-outlined text-5xl mb-4 block opacity-40">vpn_key</span>
          <p>Nenhuma API disponível. Aguarde aprovação de acesso.</p>
        </div>
      ) : (
        <div className="space-y-10">
          {catalog.map((api) => {
            const apiKeys = keys.filter((k) => k.api_id === api.id);
            const activeKeys = apiKeys.filter((k) => k.status === "active");
            const revokedKeys = apiKeys.filter((k) => k.status !== "active");
            const atLimit = activeKeys.length >= 5;

            return (
              <section key={api.id} className="bg-surface-container-lowest rounded-2xl border border-outline-variant/15 overflow-hidden">
                <div className="px-6 py-4 border-b border-outline-variant/10 flex items-center justify-between bg-surface-container-low/50">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
                      <span className="material-symbols-outlined text-primary text-[18px]" style={{ fontVariationSettings: "'FILL' 1" }}>api</span>
                    </div>
                    <div>
                      <span className="font-headline font-bold text-on-surface">{api.name}</span>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className={`w-1.5 h-1.5 rounded-full ${api.status === "active" ? "bg-emerald-500" : "bg-outline"}`} />
                        <span className="text-[10px] uppercase tracking-wider text-on-surface-variant font-semibold">
                          {api.status === "active" ? "Operational" : api.status}
                        </span>
                      </div>
                    </div>
                  </div>
                  <span className={`text-xs px-2.5 py-1 rounded-full font-mono ${atLimit ? "bg-error-container text-on-error-container font-bold" : "bg-surface-container text-on-surface-variant"}`}>
                    {activeKeys.length}/5 keys
                  </span>
                </div>

                <div className="p-6 space-y-6">
                  {createErrors[api.id] && (
                    <div role="alert" className="p-3 bg-error-container rounded-lg text-on-error-container text-sm">
                      {createErrors[api.id]}
                    </div>
                  )}
                  {atLimit ? (
                    <div className="flex items-center gap-3 p-3 bg-error-container/40 border border-error/20 rounded-xl text-sm text-on-error-container">
                      <span className="material-symbols-outlined text-[18px]">block</span>
                      Limite de 5 chaves ativas atingido. Revogue uma chave para criar outra.
                    </div>
                  ) : (
                    <form onSubmit={(e) => handleCreate(api.id, e)} className="flex gap-3">
                      <input
                        className="flex-1 bg-surface-container border border-outline-variant/30 rounded-xl py-3 px-4 text-sm text-on-surface focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all"
                        placeholder={`Nome da chave para ${api.name} (ex: Produção)`}
                        value={newKeyNames[api.id] ?? ""}
                        onChange={(e) => setNewKeyNames((prev) => ({ ...prev, [api.id]: e.target.value }))}
                        required
                      />
                      <button
                        type="submit"
                        disabled={creating === api.id}
                        className="primary-gradient text-white rounded-xl px-5 py-3 text-sm font-semibold hover:opacity-90 transition-all shadow-[0_4px_14px_0_rgba(43,91,181,0.2)] flex items-center gap-2 disabled:opacity-70"
                      >
                        <span className="material-symbols-outlined text-[16px]">add_circle</span>
                        {creating === api.id ? "Criando…" : "Gerar Chave"}
                      </button>
                    </form>
                  )}

                  {activeKeys.length > 0 && (
                    <div className="space-y-3">
                      {activeKeys.map((k) => {
                        const full = k.api_key;
                        const isVisible = visible[k.id] ?? false;
                        const displayValue = full
                          ? (isVisible ? full : "●".repeat(32))
                          : `${k.key_prefix}…`;
                        const copyValue = full ?? k.key_prefix;

                        return (
                          <div key={k.id} className="bg-tertiary-container rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-0.5">
                                <span className="font-bold text-sm text-on-surface">{k.name}</span>
                                <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-container-highest">
                                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.6)]" />
                                  <span className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">Active</span>
                                </span>
                              </div>
                              <p className="text-xs text-on-surface-variant">
                                Criado em {new Date(k.created_at).toLocaleDateString("pt-BR")}
                              </p>
                            </div>

                            <div className="bg-surface-container-lowest px-4 py-2.5 rounded-lg border border-outline-variant/15 flex items-center min-w-0 flex-1 max-w-sm overflow-x-auto">
                              <code className="font-mono text-on-surface text-sm whitespace-nowrap tracking-wider">
                                {displayValue}
                              </code>
                            </div>

                            <div className="flex items-center gap-2 flex-shrink-0">
                              {full && (
                                <button
                                  onClick={() => setVisible((prev) => ({ ...prev, [k.id]: !isVisible }))}
                                  title={isVisible ? "Ocultar chave" : "Exibir chave"}
                                  className="bg-surface-container-highest hover:bg-surface-variant text-on-surface rounded-lg p-2.5 transition-colors"
                                >
                                  <span className="material-symbols-outlined text-[20px]">
                                    {isVisible ? "visibility_off" : "visibility"}
                                  </span>
                                </button>
                              )}
                              <CopyButton value={copyValue} />
                              <button
                                onClick={() => handleRevoke(k.id)}
                                disabled={actionLoading === k.id}
                                className="bg-surface-container-highest hover:bg-error-container text-on-surface hover:text-error rounded-lg p-2.5 transition-colors"
                                title="Revogar chave"
                              >
                                <span className="material-symbols-outlined text-[20px]">
                                  {actionLoading === k.id ? "hourglass_empty" : "delete"}
                                </span>
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {revokedKeys.length > 0 && (
                    <details className="group">
                      <summary className="cursor-pointer text-xs text-on-surface-variant hover:text-on-surface transition-colors list-none flex items-center gap-1">
                        <span className="material-symbols-outlined text-[14px] group-open:rotate-90 transition-transform">chevron_right</span>
                        {revokedKeys.length} chave{revokedKeys.length !== 1 ? "s" : ""} revogada{revokedKeys.length !== 1 ? "s" : ""}
                      </summary>
                      <div className="space-y-2 mt-3">
                        {revokedKeys.map((k) => (
                          <div key={k.id} className="bg-surface-container-lowest rounded-xl p-4 flex items-center justify-between opacity-50">
                            <div>
                              <span className="text-sm font-bold text-on-surface">{k.name}</span>
                              <p className="text-xs text-on-surface-variant">{new Date(k.created_at).toLocaleDateString("pt-BR")}</p>
                            </div>
                            <code className="font-mono text-on-surface-variant text-sm">{k.key_prefix}…</code>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}

                  {apiKeys.length === 0 && (
                    <p className="text-sm text-on-surface-variant text-center py-2">
                      Nenhuma chave gerada para esta API ainda.
                    </p>
                  )}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
