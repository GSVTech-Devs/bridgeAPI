"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getJobs,
  getJob,
  type JobListItem,
  type JobDetail,
} from "@/lib/api";

const PER_PAGE = 20;

function formatTime(dateStr: string | null): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", hour: "2-digit",
    minute: "2-digit", second: "2-digit",
  });
}

function statusPill(s: string): string {
  switch (s) {
    case "done": return "bg-green-600 text-white";
    case "running": return "bg-amber-500 text-white";
    case "failed": return "bg-error text-on-error";
    case "timeout": return "bg-error text-on-error";
    default: return "bg-surface-container-high text-on-surface-variant";
  }
}

function statusLabel(s: string): string {
  switch (s) {
    case "done": return "Concluído";
    case "running": return "Executando";
    case "failed": return "Falhou";
    case "timeout": return "Timeout";
    default: return s;
  }
}

function webhookPill(s: string | null): string {
  switch (s) {
    case "delivered": return "bg-green-600 text-white";
    case "pending": return "bg-amber-500 text-white";
    case "failed": return "bg-error text-on-error";
    default: return "bg-surface-container-high text-on-surface-variant";
  }
}

function webhookLabel(s: string | null): string {
  switch (s) {
    case "delivered": return "entregue";
    case "pending": return "pendente";
    case "failed": return "falhou";
    default: return "—";
  }
}

function Spinner({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center py-16 text-on-surface-variant gap-2">
      <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
      </svg>
      {label}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex gap-3 text-sm py-1.5">
      <span className="text-on-surface-variant w-40 shrink-0">{label}</span>
      <span className="text-on-surface font-medium break-all min-w-0">{value}</span>
    </div>
  );
}

function JobDetailDrawer({ job, onClose }: { job: JobDetail; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40" />
      <div
        className="relative w-full max-w-xl bg-surface h-full overflow-y-auto p-8 space-y-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-xl font-bold text-on-surface">Detalhe do job</h3>
            <p className="text-xs font-mono text-on-surface-variant mt-1">{job.id}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-surface-container-low transition-colors"
          >
            <span className="material-symbols-outlined text-on-surface-variant">close</span>
          </button>
        </div>

        <div className="flex gap-2">
          <span className={`text-[10px] font-black uppercase rounded-md px-2 py-1 ${statusPill(job.status)}`}>
            {statusLabel(job.status)}
          </span>
          {job.callback_url && (
            <span className={`text-[10px] font-black uppercase rounded-md px-2 py-1 ${webhookPill(job.webhook_status)}`}>
              webhook: {webhookLabel(job.webhook_status)}
            </span>
          )}
        </div>

        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 p-5">
          <DetailRow label="Correlation ID" value={<span className="font-mono">{job.correlation_id}</span>} />
          <DetailRow label="API" value={<span className="font-mono">{job.api_id}</span>} />
          <DetailRow label="Conta" value={<span className="font-mono">{job.account_id}</span>} />
          <DetailRow label="HTTP resultado" value={job.result_status_code ?? "—"} />
          <DetailRow label="Erro" value={job.error_code ?? "—"} />
          <DetailRow label="Custo" value={job.cost != null ? `$${job.cost.toFixed(4)}` : "—"} />
          <DetailRow label="Latência" value={job.latency_ms != null ? `${Math.round(job.latency_ms)} ms` : "—"} />
          <DetailRow label="Callback URL" value={job.callback_url ?? "—"} />
          <DetailRow label="Criado" value={formatTime(job.created_at)} />
          <DetailRow label="Concluído" value={formatTime(job.completed_at)} />
        </div>

        <div>
          <p className="text-xs font-bold text-on-surface-variant uppercase tracking-wide mb-2">
            Corpo da resposta
          </p>
          <pre className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 p-4 text-xs font-mono text-on-surface overflow-x-auto max-h-96 whitespace-pre-wrap">
            {job.result_body ?? "— sem corpo —"}
          </pre>
        </div>
      </div>
    </div>
  );
}

export default function JobsPage() {
  const [items, setItems] = useState<JobListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<JobDetail | null>(null);

  const refresh = useCallback(async () => {
    const data = await getJobs(page, PER_PAGE);
    setItems(data.items);
    setTotal(data.total);
  }, [page]);

  useEffect(() => {
    setLoading(true);
    refresh().finally(() => setLoading(false));
  }, [refresh]);

  const openDetail = async (id: string) => {
    const job = await getJob(id);
    setSelected(job);
  };

  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-4xl font-extrabold tracking-tight text-on-surface font-headline mb-2">
            Jobs
          </h2>
          <p className="text-on-surface-variant font-medium">
            Execuções assíncronas (consultas que excederam o limite síncrono).
          </p>
        </div>
        <button
          onClick={() => refresh()}
          className="flex items-center gap-2 text-sm font-bold text-primary hover:opacity-80 transition-opacity"
        >
          <span className="material-symbols-outlined text-[20px]">refresh</span>
          Atualizar
        </button>
      </div>

      {loading ? (
        <Spinner label="Carregando jobs…" />
      ) : items.length === 0 ? (
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 flex flex-col items-center justify-center py-16 text-on-surface-variant gap-3">
          <span className="material-symbols-outlined text-4xl opacity-50">schedule</span>
          <p className="font-medium">Nenhum job ainda.</p>
          <p className="text-xs">Jobs surgem quando uma consulta excede o limite síncrono.</p>
        </div>
      ) : (
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-on-surface-variant border-b border-outline-variant/10">
                <th className="px-5 py-3 font-bold">Status</th>
                <th className="px-5 py-3 font-bold">Correlation ID</th>
                <th className="px-5 py-3 font-bold">HTTP</th>
                <th className="px-5 py-3 font-bold">Webhook</th>
                <th className="px-5 py-3 font-bold">Custo</th>
                <th className="px-5 py-3 font-bold">Criado</th>
                <th className="px-5 py-3 font-bold">Concluído</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/10">
              {items.map((job) => (
                <tr
                  key={job.id}
                  onClick={() => openDetail(job.id)}
                  className="hover:bg-surface-container-low cursor-pointer transition-colors"
                >
                  <td className="px-5 py-3">
                    <span className={`text-[10px] font-black uppercase rounded-md px-2 py-1 ${statusPill(job.status)}`}>
                      {statusLabel(job.status)}
                    </span>
                  </td>
                  <td className="px-5 py-3 font-mono text-xs text-on-surface-variant truncate max-w-[200px]">
                    {job.correlation_id}
                  </td>
                  <td className="px-5 py-3 text-on-surface">{job.result_status_code ?? "—"}</td>
                  <td className="px-5 py-3">
                    {job.webhook_status ? (
                      <span className={`text-[10px] font-black uppercase rounded px-2 py-0.5 ${webhookPill(job.webhook_status)}`}>
                        {webhookLabel(job.webhook_status)}
                      </span>
                    ) : (
                      <span className="text-on-surface-variant">—</span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-on-surface">
                    {job.cost != null ? `$${job.cost.toFixed(4)}` : "—"}
                  </td>
                  <td className="px-5 py-3 text-on-surface-variant whitespace-nowrap">{formatTime(job.created_at)}</td>
                  <td className="px-5 py-3 text-on-surface-variant whitespace-nowrap">{formatTime(job.completed_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && totalPages > 1 && (
        <div className="flex items-center justify-center gap-4">
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="px-4 py-2 rounded-lg bg-surface-container-low text-sm font-bold disabled:opacity-40 hover:bg-surface-container transition-colors"
          >
            Anterior
          </button>
          <span className="text-sm text-on-surface-variant">
            Página {page} de {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="px-4 py-2 rounded-lg bg-surface-container-low text-sm font-bold disabled:opacity-40 hover:bg-surface-container transition-colors"
          >
            Próxima
          </button>
        </div>
      )}

      {selected && <JobDetailDrawer job={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
