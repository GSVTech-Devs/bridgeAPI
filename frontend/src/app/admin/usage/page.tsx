"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getAdminClientsSummary } from "@/lib/api";

type ClientSummary = {
  client_id: string;
  client_name: string;
  client_email: string;
  total_requests: number;
  error_count: number;
  success_count: number;
  total_cost: number;
};

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

export default function UsagePage() {
  const router = useRouter();
  const [items, setItems] = useState<ClientSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");

  function load() {
    setLoading(true);
    const params: Record<string, string> = {};
    if (since) params.since = new Date(since).toISOString();
    if (until) params.until = new Date(until).toISOString();
    getAdminClientsSummary(Object.keys(params).length ? params : undefined)
      .then((res) => setItems(res.items))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  const totalPlatformCost = items.reduce((s, i) => s + i.total_cost, 0);

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <div className="flex justify-between items-end flex-wrap gap-4">
        <div>
          <h2 className="text-4xl font-extrabold tracking-tight text-on-surface font-headline mb-2">
            Uso por Cliente
          </h2>
          <p className="text-on-surface-variant font-medium">
            Gasto acumulado e consumo de requisições por usuário.
          </p>
        </div>

        {/* Date filters */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">De</label>
            <input
              type="datetime-local"
              value={since}
              onChange={(e) => setSince(e.target.value)}
              className="bg-surface-container-low border-none rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary-container"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Até</label>
            <input
              type="datetime-local"
              value={until}
              onChange={(e) => setUntil(e.target.value)}
              className="bg-surface-container-low border-none rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary-container"
            />
          </div>
          <button
            onClick={load}
            className="self-end px-5 py-2 primary-gradient text-white font-bold rounded-lg text-sm hover:brightness-110 transition-all"
          >
            Filtrar
          </button>
          {(since || until) && (
            <button
              onClick={() => { setSince(""); setUntil(""); }}
              className="self-end px-3 py-2 text-sm text-on-surface-variant hover:text-error transition-colors"
            >
              Limpar
            </button>
          )}
        </div>
      </div>

      {/* Summary stat */}
      {!loading && items.length > 0 && (
        <div className="grid grid-cols-3 gap-6">
          <div className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/10">
            <p className="text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-2">Clientes Ativos</p>
            <p className="text-3xl font-black text-on-surface font-headline">{items.length}</p>
          </div>
          <div className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/10">
            <p className="text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-2">Total Requisições</p>
            <p className="text-3xl font-black text-on-surface font-headline">
              {items.reduce((s, i) => s + i.total_requests, 0).toLocaleString()}
            </p>
          </div>
          <div className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/10">
            <p className="text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-2">Receita Total</p>
            <p className="text-3xl font-black text-primary font-headline">R$ {totalPlatformCost.toFixed(2)}</p>
          </div>
        </div>
      )}

      {/* Client table */}
      <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 overflow-hidden">
        {loading ? (
          <Spinner />
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-on-surface-variant gap-3">
            <span className="material-symbols-outlined text-4xl">inbox</span>
            <p className="font-medium">Nenhum dado de uso encontrado.</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-[1fr_100px_80px_80px_140px_40px] px-5 py-3 bg-surface-container-low/50 text-xs font-bold uppercase tracking-widest text-on-surface-variant/60">
              <div>Cliente</div>
              <div className="text-right">Requisições</div>
              <div className="text-right">Sucesso</div>
              <div className="text-right">Erros</div>
              <div className="text-right">Gasto Total</div>
              <div />
            </div>
            <div className="divide-y divide-outline-variant/10">
              {items.map((item) => {
                const errorRate = item.total_requests > 0
                  ? (item.error_count / item.total_requests) * 100
                  : 0;
                return (
                  <button
                    key={item.client_id}
                    onClick={() => router.push(`/admin/usage/${item.client_id}`)}
                    className="w-full grid grid-cols-[1fr_100px_80px_80px_140px_40px] items-center px-5 py-4 hover:bg-surface-container-low/40 transition-colors text-left group"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-9 h-9 shrink-0 rounded-full bg-secondary-fixed flex items-center justify-center text-secondary font-bold text-sm">
                        {item.client_name.slice(0, 2).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <p className="font-bold text-sm text-on-surface truncate">{item.client_name}</p>
                        <p className="text-xs text-on-surface-variant truncate">{item.client_email}</p>
                      </div>
                    </div>
                    <p className="text-sm font-bold text-on-surface text-right tabular-nums">
                      {item.total_requests.toLocaleString()}
                    </p>
                    <p className="text-sm font-bold text-green-600 text-right tabular-nums">
                      {item.success_count.toLocaleString()}
                    </p>
                    <p className={`text-sm font-bold text-right tabular-nums ${item.error_count > 0 ? "text-error" : "text-on-surface-variant"}`}>
                      {item.error_count > 0 ? item.error_count.toLocaleString() : "—"}
                    </p>
                    <div className="text-right">
                      {item.total_cost > 0 ? (
                        <p className="text-sm font-black text-primary tabular-nums">R$ {item.total_cost.toFixed(4)}</p>
                      ) : (
                        <p className="text-xs text-on-surface-variant">—</p>
                      )}
                      {errorRate > 0 && (
                        <p className="text-[10px] text-error">{errorRate.toFixed(1)}% erros</p>
                      )}
                    </div>
                    <span className="material-symbols-outlined text-sm text-on-surface-variant justify-self-end opacity-0 group-hover:opacity-100 transition-opacity">
                      chevron_right
                    </span>
                  </button>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
