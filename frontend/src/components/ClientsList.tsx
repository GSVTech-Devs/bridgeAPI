"use client";

import { useEffect, useState } from "react";
import { getClients, approveClient, rejectClient } from "@/lib/api";

type Client = {
  id: string;
  name: string;
  email: string;
  status: string;
};

export default function ClientsList() {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const data = await getClients();
      setClients(data.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao carregar clientes");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (loading) return <p>Carregando…</p>;
  if (error) return <div role="alert">{error}</div>;

  return (
    <ul>
      {clients.map((c) => (
        <li key={c.id}>
          <span>{c.name}</span>
          <span> — </span>
          <span>{c.status}</span>
          {c.status === "pending" && (
            <>
              <button onClick={() => approveClient(c.id)}>Aprovar</button>
              <button onClick={() => rejectClient(c.id)}>Rejeitar</button>
            </>
          )}
        </li>
      ))}
    </ul>
  );
}
