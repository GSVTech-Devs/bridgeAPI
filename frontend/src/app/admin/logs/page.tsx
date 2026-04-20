"use client";

import { useEffect, useState } from "react";
import { getApis, getAdminErrorLogs, getClients } from "@/lib/api";

type Api = { id: string; name: string; status: string };
type Client = { id: string; name: string; email: string };

type ErrorLog = {
  correlation_id: string;
  client_id: string;
  api_id: string;
  key_id: string;
  path: string;
  method: string;
  status_code: number;
  latency_ms: number;
  request_body: string | null;
  response_body: string | null;
  created_at: string | null;
};

function formatTime(dateStr: string | null): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

function statusColor(code: number) {
  if (code >= 500) return "bg-error text-on-error";
  if (code >= 400) return "bg-amber-500 text-white";
  return "bg-surface-container-high text-on-surface";
}

function Spinner() {
  return (
    <div className="flex items-center justify-center py-20 text-on-surface-variant gap-2">
      <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
      </svg>
      Carregando logs…
    </div>
  );
}

export default function LogsPage() {
  const [apis, setApis] = useState<Api[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [logs, setLogs] = useState<ErrorLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeApiId, setActiveApiId] = useState<string>("all");
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getApis(), getAdminErrorLogs(), getClients()])
      .then(([apisRes, logsRes, clientsRes]) => {
        setApis(apisRes.items);
        setLogs(logsRes.items);
        setClients(clientsRes.items);
      })
      .finally(() => setLoading(false));
  }, []);

  const apisWithErrors = apis.filter((a) => logs.some((l) => l.api_id === a.id));

  const filtered = activeApiId === "all"
    ? logs
    : logs.filter((l) => l.api_id === activeApiId);

  const apiMap = Object.fromEntries(apis.map((a) => [a.id, a.name]));
  const clientMap = Object.fromEntries(clients.map((c) => [c.id, { name: c.name, email: c.email }]));

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <div>
        <h2 className="text-4xl font-extrabold tracking-tight text-on-surface font-headline mb-2">
          Logs de Erro
        </h2>
        <p className="text-on-surface-variant font-medium">
          Requisições com status diferente de 200, separadas por API.
        </p>
      </div>

      {/* API tabs */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setActiveApiId("all")}
          className={`px-4 py-2 rounded-lg text-sm font-bold transition-colors ${
            activeApiId === "all"
              ? "bg-primary text-white"
              : "bg-surface-container-low text-on-surface hover:bg-surface-container-high"
          }`}
        >
          Todas ({logs.length})
        </button>
        {apisWithErrors.map((api) => {
          const count = logs.filter((l) => l.api_id === api.id).length;
          return (
            <button
              key={api.id}
              onClick={() => setActiveApiId(api.id)}
              className={`px-4 py-2 rounded-lg text-sm font-bold transition-colors ${
                activeApiId === api.id
                  ? "bg-primary text-white"
                  : "bg-surface-container-low text-on-surface hover:bg-surface-container-high"
              }`}
            >
              {api.name} ({count})
            </button>
          );
        })}
      </div>

      {/* Log table */}
      <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 overflow-hidden">
        {loading ? (
          <Spinner />
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-on-surface-variant gap-3">
            <span className="material-symbols-outlined text-4xl text-green-500">check_circle</span>
            <p className="font-medium">Nenhum erro registrado.</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-[80px_80px_1fr_120px_160px_40px] px-5 py-3 bg-surface-container-low/50 text-xs font-bold uppercase tracking-widest text-on-surface-variant/60">
              <div>Status</div>
              <div>Método</div>
              <div>Path / API</div>
              <div>Latência</div>
              <div>Data</div>
              <div />
            </div>
            <div className="divide-y divide-outline-variant/10">
              {filtered.map((log) => {
                const isOpen = expanded === log.correlation_id;
                return (
                  <div key={log.correlation_id}>
                    <button
                      onClick={() => setExpanded(isOpen ? null : log.correlation_id)}
                      className="w-full grid grid-cols-[80px_80px_1fr_120px_160px_40px] items-center px-5 py-4 hover:bg-surface-container-low/30 transition-colors text-left"
                    >
                      <span className={`w-12 text-center text-xs font-black rounded-md py-1 ${statusColor(log.status_code)}`}>
                        {log.status_code}
                      </span>
                      <span className="text-xs font-mono font-bold text-on-surface-variant">
                        {log.method}
                      </span>
                      <div className="min-w-0 pr-4">
                        <p className="font-mono text-sm text-on-surface truncate">{log.path}</p>
                        <p className="text-xs text-primary font-medium">{apiMap[log.api_id] ?? log.api_id}</p>
                      </div>
                      <span className="text-sm tabular-nums text-on-surface-variant">
                        {Math.round(log.latency_ms)}ms
                      </span>
                      <span className="text-xs text-on-surface-variant">
                        {formatTime(log.created_at)}
                      </span>
                      <span className="material-symbols-outlined text-sm text-on-surface-variant justify-self-end">
                        {isOpen ? "expand_less" : "expand_more"}
                      </span>
                    </button>

                    {isOpen && (
                      <div className="px-5 pb-5 space-y-4 bg-surface-container-low/20">
                        <div className="grid grid-cols-2 gap-2 text-xs text-on-surface-variant pt-2">
                          <span>
                            <span className="font-bold">Cliente:</span>{" "}
                            {clientMap[log.client_id]?.name ?? log.client_id}
                          </span>
                          <span>
                            <span className="font-bold">Email:</span>{" "}
                            {clientMap[log.client_id]?.email ?? "—"}
                          </span>
                          <span><span className="font-bold">Key:</span> {log.key_id}</span>
                          <span><span className="font-bold">Correlation ID:</span> {log.correlation_id}</span>
                        </div>

                        {log.request_body && log.request_body.trim() && (
                          <div className="space-y-1">
                            <p className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Request Body</p>
                            <pre className="bg-surface-container rounded-lg p-4 text-xs font-mono text-on-surface overflow-x-auto whitespace-pre-wrap break-all">
                              {log.request_body}
                            </pre>
                          </div>
                        )}

                        <div className="space-y-1">
                          <p className="text-xs font-bold text-error uppercase tracking-wider">Server Response</p>
                          <pre className="bg-error-container/30 rounded-lg p-4 text-xs font-mono text-on-surface overflow-x-auto whitespace-pre-wrap break-all">
                            {log.response_body?.trim() || "(empty response body)"}
                          </pre>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
