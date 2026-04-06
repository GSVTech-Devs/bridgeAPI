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

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Minhas Chaves</h1>
        <p className="text-gray-500 mt-1">Gerencie as chaves de acesso às APIs.</p>
      </div>

      {/* Create form */}
      <div className="card mb-6">
        <h2 className="font-semibold text-gray-900 mb-3">Nova chave</h2>
        {createError && (
          <div role="alert" className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {createError}
          </div>
        )}
        <form onSubmit={handleCreate} className="flex gap-3">
          <input
            className="input flex-1"
            placeholder="Nome da chave (ex: Produção, Dev...)"
            value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
            required
          />
          <button type="submit" disabled={creating} className="btn-primary flex-shrink-0">
            {creating ? "Criando…" : "Criar chave"}
          </button>
        </form>
      </div>

      {/* Secret reveal modal */}
      {revealedKey && (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-xl">
          <div className="flex items-start justify-between">
            <div>
              <p className="font-semibold text-green-800 mb-1">Chave criada! Copie agora — não será exibida novamente.</p>
              <code className="text-sm bg-white border border-green-300 rounded px-3 py-1.5 block mt-2 break-all text-gray-800">
                {revealedKey.secret}
              </code>
            </div>
            <button onClick={() => setRevealedKey(null)} className="text-green-600 hover:text-green-800 ml-4 flex-shrink-0">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Keys table */}
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
                <th>Prefixo</th>
                <th>Status</th>
                <th>Criado em</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {keys.length === 0 && (
                <tr><td colSpan={5} className="text-center py-10 text-gray-400">Nenhuma chave criada</td></tr>
              )}
              {keys.map((k) => (
                <tr key={k.id}>
                  <td className="font-medium text-gray-900">{k.name}</td>
                  <td>
                    <code className="text-sm bg-gray-100 rounded px-2 py-0.5 text-gray-700">{k.key_prefix}…</code>
                  </td>
                  <td>
                    <span className={k.status === "active" ? "badge-green" : "badge-red"}>
                      {k.status === "active" ? "Ativa" : "Revogada"}
                    </span>
                  </td>
                  <td className="text-gray-500 text-sm">
                    {new Date(k.created_at).toLocaleDateString("pt-BR")}
                  </td>
                  <td>
                    {k.status === "active" && (
                      <button
                        onClick={() => handleRevoke(k.id)}
                        disabled={actionLoading === k.id}
                        className="btn-danger btn-sm"
                      >
                        {actionLoading === k.id ? "…" : "Revogar"}
                      </button>
                    )}
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
