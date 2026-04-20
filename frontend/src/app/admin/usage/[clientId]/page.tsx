"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getAdminClientDetail, getClients } from "@/lib/api";

type ApiDetail = {
  api_id: string;
  api_name: string;
  total_requests: number;
  error_count: number;
  success_count: number;
  total_cost: number;
};

type Detail = {
  client_id: string;
  total_cost: number;
  total_requests: number;
  items: ApiDetail[];
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

export default function ClientUsageDetailPage() {
  const { clientId } = useParams<{ clientId: string }>();
  const router = useRouter();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [clientName, setClientName] = useState("");
  const [clientEmail, setClientEmail] = useState("");
  const [loading, setLoading] = useState(true);
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");

  function load() {
    setLoading(true);
    const params: Record<string, string> = {};
    if (since) params.since = new Date(since).toISOString();
    if (until) params.until = new Date(until).toISOString();
    getAdminClientDetail(clientId, Object.keys(params).length ? params : undefined)
      .then((res) => setDetail(res))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    getClients().then((res) => {
      const c = res.items.find((c) => c.id === clientId);
      if (c) { setClientName(c.name); setClientEmail(c.email); }
    });
    load();
  }, []);

  const totalErrors = detail?.items.reduce((s, i) => s + i.error_count, 0) ?? 0;
  const totalSuccess = detail?.items.reduce((s, i) => s + i.success_count, 0) ?? 0;
  const totalRequests = detail?.total_requests ?? 0;
  const errorRate = totalRequests > 0 ? (totalErrors / totalRequests) * 100 : 0;

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-start gap-4">
        <button
          onClick={() => router.push("/admin/usage")}
          className="mt-1 p-2 rounded-lg hover:bg-surface-container-low transition-colors text-on-surface-variant"
        >
          <span className="material-symbols-outlined">arrow_back</span>
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-1">
            <div className="w-10 h-10 rounded-full bg-secondary-fixed flex items-center justify-center text-secondary font-bold">
              {clientName.slice(0, 2).toUpperCase() || "??"}
            </div>
            <div>
              <h2 className="text-3xl font-extrabold tracking-tight text-on-surface font-headline">
                {clientName || clientId}
              </h2>
              {clientEmail && <p className="text-on-surface-variant text-sm">{clientEmail}</p>}
            </div>
          </div>
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

      {/* Summary cards */}
      {!loading && detail && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/10">
            <p className="text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-2">Total Requisições</p>
            <p className="text-3xl font-black text-on-surface font-headline">{totalRequests.toLocaleString()}</p>
          </div>
          <div className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/10">
            <p className="text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-2">Sucessos</p>
            <p className="text-3xl font-black text-green-600 font-headline">{totalSuccess.toLocaleString()}</p>
          </div>
          <div className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/10">
            <p className="text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-2">Erros</p>
            <p className={`text-3xl font-black font-headline ${totalErrors > 0 ? "text-error" : "text-on-surface-variant"}`}>
              {totalErrors > 0 ? totalErrors.toLocaleString() : "—"}
            </p>
            {errorRate > 0 && <p className="text-xs text-error mt-1">{errorRate.toFixed(1)}% das req.</p>}
          </div>
          <div className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/10">
            <p className="text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-2">Gasto Total</p>
            <p className="text-3xl font-black text-primary font-headline">
              R$ {detail.total_cost.toFixed(4)}
            </p>
            <p className="text-xs text-on-surface-variant mt-1">apenas req. com sucesso</p>
          </div>
        </div>
      )}

      {/* Per-API breakdown table */}
      <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 overflow-hidden">
        <div className="px-5 py-4 border-b border-outline-variant/10">
          <h3 className="text-lg font-bold font-headline">Detalhe por API</h3>
        </div>
        {loading ? (
          <Spinner />
        ) : !detail || detail.items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-on-surface-variant gap-3">
            <span className="material-symbols-outlined text-4xl">inbox</span>
            <p className="font-medium">Nenhum uso encontrado para este período.</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-[1fr_110px_90px_90px_150px] px-5 py-3 bg-surface-container-low/50 text-xs font-bold uppercase tracking-widest text-on-surface-variant/60">
              <div>API</div>
              <div className="text-right">Requisições</div>
              <div className="text-right">Sucesso</div>
              <div className="text-right">Erros</div>
              <div className="text-right">Gasto (só sucessos)</div>
            </div>
            <div className="divide-y divide-outline-variant/10">
              {detail.items.map((row) => {
                const apiErrorRate = row.total_requests > 0
                  ? (row.error_count / row.total_requests) * 100
                  : 0;
                return (
                  <div
                    key={row.api_id}
                    className="grid grid-cols-[1fr_110px_90px_90px_150px] items-center px-5 py-4 hover:bg-surface-container-low/30 transition-colors"
                  >
                    <div>
                      <p className="font-bold text-sm text-on-surface">{row.api_name}</p>
                      {apiErrorRate > 0 && (
                        <p className="text-[10px] text-error">{apiErrorRate.toFixed(1)}% erros</p>
                      )}
                    </div>
                    <p className="text-sm font-bold text-on-surface text-right tabular-nums">
                      {row.total_requests.toLocaleString()}
                    </p>
                    <p className="text-sm font-bold text-green-600 text-right tabular-nums">
                      {row.success_count.toLocaleString()}
                    </p>
                    <p className={`text-sm font-bold text-right tabular-nums ${row.error_count > 0 ? "text-error" : "text-on-surface-variant"}`}>
                      {row.error_count > 0 ? row.error_count.toLocaleString() : "—"}
                    </p>
                    <div className="text-right">
                      {row.total_cost > 0 ? (
                        <p className="text-sm font-black text-primary tabular-nums">R$ {row.total_cost.toFixed(4)}</p>
                      ) : (
                        <p className="text-xs text-on-surface-variant">—</p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
            {/* Total row */}
            <div className="grid grid-cols-[1fr_110px_90px_90px_150px] items-center px-5 py-4 bg-surface-container-low/50 border-t border-outline-variant/10">
              <p className="text-sm font-black uppercase tracking-wider text-on-surface-variant">Total</p>
              <p className="text-sm font-black text-on-surface text-right tabular-nums">
                {totalRequests.toLocaleString()}
              </p>
              <p className="text-sm font-black text-green-600 text-right tabular-nums">
                {totalSuccess.toLocaleString()}
              </p>
              <p className={`text-sm font-black text-right tabular-nums ${totalErrors > 0 ? "text-error" : "text-on-surface-variant"}`}>
                {totalErrors > 0 ? totalErrors.toLocaleString() : "—"}
              </p>
              <p className="text-sm font-black text-primary text-right tabular-nums">
                R$ {(detail.total_cost).toFixed(4)}
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
