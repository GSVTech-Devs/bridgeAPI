"use client";

import { useEffect, useState } from "react";
import { getKeys, createKey, revokeKey } from "@/lib/api";

type Key = { id: string; name: string; key_prefix: string; status: string; created_at: string };
type NewKey = Key & { secret: string };

export default function KeysPage() {
  const [keys, setKeys] = useState<Key[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newKeyName, setNewKeyName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [revealedKey, setRevealedKey] = useState<NewKey | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  async function load() {
    try {
      const data = await getKeys();
      setKeys(data.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao carregar");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newKeyName.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      const key = await createKey(newKeyName.trim());
      setRevealedKey(key);
      setKeys((prev) => [key, ...prev]);
      setNewKeyName("");
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : "Erro ao criar chave");
    } finally {
      setCreating(false);
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

  const activeKeys = keys.filter((k) => k.status === "active");
  const revokedKeys = keys.filter((k) => k.status !== "active");

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-10 flex items-end justify-between">
        <div>
          <h1 className="text-4xl font-headline font-extrabold tracking-tight text-on-surface mb-2">My API Keys</h1>
          <p className="text-on-surface-variant text-base max-w-xl">
            Manage your active access tokens. Keep these keys secure and rotate them regularly.
          </p>
        </div>
      </div>

      {/* Revealed key modal */}
      {revealedKey && (
        <div className="mb-8 p-5 bg-green-50 border border-green-200 rounded-xl">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <span className="material-symbols-outlined text-green-700 text-[20px]">info</span>
                <p className="font-semibold text-green-800">Chave criada! Copie agora — não será exibida novamente.</p>
              </div>
              <code className="text-sm bg-white border border-green-300 rounded-lg px-4 py-3 block mt-2 break-all text-on-surface font-mono">
                {revealedKey.secret}
              </code>
            </div>
            <button onClick={() => setRevealedKey(null)} className="text-green-600 hover:text-green-800 ml-4 flex-shrink-0 p-1">
              <span className="material-symbols-outlined text-[20px]">close</span>
            </button>
          </div>
        </div>
      )}

      {/* Create form */}
      <div className="mb-12">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-surface-container-high flex items-center justify-center">
              <span className="material-symbols-outlined text-primary">vpn_key</span>
            </div>
            <h2 className="text-2xl font-headline font-bold text-on-surface tracking-tight">Generate New Key</h2>
          </div>
        </div>

        {createError && (
          <div role="alert" className="mb-4 p-3 bg-error-container rounded-lg text-on-error-container text-sm">
            {createError}
          </div>
        )}

        <form onSubmit={handleCreate} className="flex gap-3">
          <input
            className="flex-1 bg-surface-container-lowest border border-outline-variant/30 rounded-xl py-3.5 px-5 text-sm text-on-surface focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all"
            placeholder="Nome da chave (ex: Produção, Dev...)"
            value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
            required
          />
          <button
            type="submit"
            disabled={creating}
            className="bg-gradient-to-br from-primary to-primary-container text-white rounded-xl px-6 py-3.5 text-sm font-semibold hover:from-primary-container hover:to-primary transition-all shadow-[0_4px_14px_0_rgba(43,91,181,0.2)] flex items-center gap-2 disabled:opacity-70"
          >
            <span className="material-symbols-outlined text-[18px]">add_circle</span>
            {creating ? "Criando…" : "Gerar Nova Chave"}
          </button>
        </form>
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
      ) : (
        <>
          {/* Active keys */}
          {activeKeys.length > 0 && (
            <section className="mb-12">
              <h2 className="text-xl font-headline font-bold text-on-surface tracking-tight mb-6">Active Keys</h2>
              <div className="space-y-4">
                {activeKeys.map((k) => (
                  <div
                    key={k.id}
                    className="bg-tertiary-container rounded-xl p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-6 shadow-sm"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-1">
                        <span className="text-on-surface font-bold text-base font-headline">{k.name}</span>
                        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-surface-container-highest">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.6)]" />
                          <span className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">Active</span>
                        </div>
                      </div>
                      <p className="text-xs text-on-surface-variant font-medium">
                        Created {new Date(k.created_at).toLocaleDateString("pt-BR")}
                      </p>
                    </div>
                    <div className="bg-surface-container-lowest px-4 py-3 rounded-lg border border-outline-variant/15 flex items-center min-w-0 flex-1 max-w-xs">
                      <code className="font-mono text-on-surface tracking-widest text-sm truncate">{k.key_prefix}…</code>
                    </div>
                    <div className="flex items-center gap-2">
                      <button className="bg-surface-container-highest hover:bg-surface-variant text-on-surface rounded-lg p-2.5 transition-colors" title="Copy Prefix">
                        <span className="material-symbols-outlined text-[20px]">content_copy</span>
                      </button>
                      <button
                        onClick={() => handleRevoke(k.id)}
                        disabled={actionLoading === k.id}
                        className="bg-surface-container-highest hover:bg-error-container text-on-surface hover:text-error rounded-lg p-2.5 transition-colors"
                        title="Revoke Key"
                      >
                        <span className="material-symbols-outlined text-[20px]">
                          {actionLoading === k.id ? "hourglass_empty" : "delete"}
                        </span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Revoked keys */}
          {revokedKeys.length > 0 && (
            <section>
              <h2 className="text-xl font-headline font-bold text-on-surface-variant tracking-tight mb-6">Revoked Keys</h2>
              <div className="space-y-4">
                {revokedKeys.map((k) => (
                  <div
                    key={k.id}
                    className="bg-surface-container-lowest rounded-xl p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-6 opacity-60"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-1">
                        <span className="text-on-surface font-bold text-base font-headline">{k.name}</span>
                        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-surface-container-high">
                          <span className="w-1.5 h-1.5 rounded-full bg-error" />
                          <span className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">Revoked</span>
                        </div>
                      </div>
                      <p className="text-xs text-on-surface-variant">{new Date(k.created_at).toLocaleDateString("pt-BR")}</p>
                    </div>
                    <div className="bg-surface-container-low px-4 py-3 rounded-lg border border-outline-variant/15 flex items-center max-w-xs flex-1">
                      <code className="font-mono text-on-surface-variant tracking-widest text-sm truncate">{k.key_prefix}…</code>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {keys.length === 0 && (
            <div className="text-center py-16 text-on-surface-variant">
              <span className="material-symbols-outlined text-5xl mb-4 block opacity-40">vpn_key</span>
              <p>Nenhuma chave criada ainda.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
