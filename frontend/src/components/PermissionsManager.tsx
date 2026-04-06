"use client";

import { useEffect, useState } from "react";
import { getClients, getApis, grantPermission } from "@/lib/api";

type Client = { id: string; name: string };
type Api = { id: string; name: string };

export default function PermissionsManager() {
  const [clients, setClients] = useState<Client[]>([]);
  const [apis, setApis] = useState<Api[]>([]);
  const [selectedClient, setSelectedClient] = useState("");
  const [selectedApi, setSelectedApi] = useState("");
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getClients(), getApis()])
      .then(([c, a]) => {
        setClients(c.items);
        setApis(a.items);
        if (c.items.length) setSelectedClient(c.items[0].id);
        if (a.items.length) setSelectedApi(a.items[0].id);
      })
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Erro ao carregar dados")
      )
      .finally(() => setLoading(false));
  }, []);

  async function handleGrant() {
    setError(null);
    setSuccess(false);
    try {
      await grantPermission(selectedClient, selectedApi);
      setSuccess(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao conceder permissão");
    }
  }

  if (loading) return <p>Carregando…</p>;

  return (
    <div>
      <select
        value={selectedClient}
        onChange={(e) => setSelectedClient(e.target.value)}
        aria-label="Cliente"
      >
        {clients.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
      <select
        value={selectedApi}
        onChange={(e) => setSelectedApi(e.target.value)}
        aria-label="API"
      >
        {apis.map((a) => (
          <option key={a.id} value={a.id}>
            {a.name}
          </option>
        ))}
      </select>
      <button onClick={handleGrant}>Conceder</button>
      {success && <p>Permissão concedida com sucesso</p>}
      {error && <div role="alert">{error}</div>}
    </div>
  );
}
