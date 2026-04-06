"use client";

import { useEffect, useState } from "react";
import { getKeys, createKey, revokeKey } from "@/lib/api";

type ApiKey = {
  id: string;
  name: string;
  key_prefix: string;
  status: string;
  created_at: string;
  secret?: string;
};

export default function ApiKeysList() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [newSecret, setNewSecret] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const data = await getKeys();
      setKeys(data.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao carregar chaves");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate() {
    try {
      const key = await createKey("nova-chave");
      setNewSecret(key.secret);
      setKeys((prev) => [...prev, key]);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao criar chave");
    }
  }

  async function handleRevoke(id: string) {
    try {
      await revokeKey(id);
      setKeys((prev) =>
        prev.map((k) => (k.id === id ? { ...k, status: "revoked" } : k))
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao revogar chave");
    }
  }

  if (loading) return <p>Carregando…</p>;
  if (error) return <div role="alert">{error}</div>;

  return (
    <div>
      <button onClick={handleCreate}>Criar Nova Chave</button>
      {newSecret && (
        <p>
          Guarde esta chave (não será exibida novamente):{" "}
          <code>{newSecret}</code>
        </p>
      )}
      <ul>
        {keys.map((k) => (
          <li key={k.id}>
            <span>{k.name}</span>
            <span> — {k.key_prefix}</span>
            <span> — {k.status}</span>
            {k.status === "active" && (
              <button onClick={() => handleRevoke(k.id)}>Revogar</button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
