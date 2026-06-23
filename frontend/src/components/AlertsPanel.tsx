"use client";

import { useCallback, useEffect, useState } from "react";
import type { Alert, AlertListResponse } from "@/lib/api";

function formatTime(dateStr: string | null): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", hour: "2-digit",
    minute: "2-digit", second: "2-digit",
  });
}

const TYPE_LABEL: Record<string, string> = {
  api_down: "API fora do ar",
  api_degraded: "API degradada",
  captcha_low_balance: "Saldo de captcha baixo",
  captcha_failing: "Captcha falhando",
  proxy_failing: "Proxy falhando",
};

const TYPE_ICON: Record<string, string> = {
  api_down: "cloud_off",
  api_degraded: "warning",
  captcha_low_balance: "account_balance_wallet",
  captcha_failing: "verified_user",
  proxy_failing: "lan",
};

function severityPill(s: string): string {
  return s === "critical" ? "bg-error text-on-error" : "bg-amber-500 text-white";
}

function statusPill(s: string): string {
  switch (s) {
    case "active": return "bg-error text-on-error";
    case "acknowledged": return "bg-surface-container-high text-on-surface-variant";
    case "resolved": return "bg-green-600 text-white";
    default: return "bg-surface-container-high text-on-surface-variant";
  }
}

function statusLabel(s: string): string {
  switch (s) {
    case "active": return "Ativo";
    case "acknowledged": return "Reconhecido";
    case "resolved": return "Resolvido";
    default: return s;
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

type Props = {
  title: string;
  subtitle: string;
  getAlerts: (status?: string, page?: number, perPage?: number) => Promise<AlertListResponse>;
  ackAlert: (id: string) => Promise<Alert>;
};

export function AlertsPanel({ title, subtitle, getAlerts, ackAlert }: Props) {
  const [items, setItems] = useState<Alert[]>([]);
  const [activeCount, setActiveCount] = useState(0);
  const [onlyOpen, setOnlyOpen] = useState(true);
  const [loading, setLoading] = useState(true);
  const [acking, setAcking] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    // onlyOpen mostra ativos; o filtro de "resolvidos" usa o histórico completo.
    const data = await getAlerts(onlyOpen ? "active" : undefined, 1, 100);
    setItems(data.items);
    setActiveCount(data.active_count);
  }, [getAlerts, onlyOpen]);

  useEffect(() => {
    setLoading(true);
    refresh().finally(() => setLoading(false));
  }, [refresh]);

  const onAck = async (id: string) => {
    setAcking(id);
    try {
      await ackAlert(id);
      await refresh();
    } finally {
      setAcking(null);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h2 className="text-4xl font-extrabold tracking-tight text-on-surface font-headline mb-2">
            {title}
          </h2>
          <p className="text-on-surface-variant font-medium">{subtitle}</p>
        </div>
        <div className="flex items-center gap-3">
          {activeCount > 0 && (
            <span className="flex items-center gap-2 text-xs font-bold text-error">
              <span className="w-2 h-2 rounded-full bg-error animate-pulse" />
              {activeCount} {activeCount === 1 ? "ativo" : "ativos"}
            </span>
          )}
          <button
            onClick={() => setOnlyOpen((v) => !v)}
            className="text-sm font-bold text-primary hover:opacity-80 transition-opacity"
          >
            {onlyOpen ? "Ver histórico" : "Só ativos"}
          </button>
        </div>
      </div>

      {loading ? (
        <Spinner label="Carregando alertas…" />
      ) : items.length === 0 ? (
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 flex flex-col items-center justify-center py-16 text-on-surface-variant gap-3">
          <span className="material-symbols-outlined text-4xl opacity-50">notifications_off</span>
          <p className="font-medium">
            {onlyOpen ? "Nenhum alerta ativo." : "Nenhum alerta registrado."}
          </p>
          <p className="text-xs">Alertas surgem quando uma API cai ou o saldo de captcha fica baixo.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((a) => (
            <div
              key={a.id}
              className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 p-5 flex items-start gap-4"
            >
              <span className={`material-symbols-outlined text-[22px] mt-0.5 ${a.severity === "critical" ? "text-error" : "text-amber-500"}`}>
                {TYPE_ICON[a.type] ?? "notifications"}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <span className="font-bold text-on-surface">{TYPE_LABEL[a.type] ?? a.type}</span>
                  <span className={`text-[10px] font-black uppercase rounded px-2 py-0.5 ${severityPill(a.severity)}`}>
                    {a.severity === "critical" ? "crítico" : "aviso"}
                  </span>
                  <span className={`text-[10px] font-black uppercase rounded px-2 py-0.5 ${statusPill(a.status)}`}>
                    {statusLabel(a.status)}
                  </span>
                </div>
                <p className="text-sm text-on-surface-variant">{a.message}</p>
                <p className="text-[11px] text-on-surface-variant/70 mt-1">
                  {a.api_name ? `${a.api_name} · ` : ""}
                  criado {formatTime(a.created_at)}
                  {a.resolved_at ? ` · resolvido ${formatTime(a.resolved_at)}` : ""}
                </p>
              </div>
              {a.status === "active" && (
                <button
                  onClick={() => onAck(a.id)}
                  disabled={acking === a.id}
                  className="shrink-0 text-xs font-bold px-3 py-2 rounded-lg bg-surface-container-low text-on-surface hover:bg-surface-container transition-colors disabled:opacity-40"
                >
                  {acking === a.id ? "…" : "Reconhecer"}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
