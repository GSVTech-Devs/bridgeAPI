"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getApiDocsAdmin, syncApiDocs, setApiDocVisible, clearApiDocs,
  type DocOperation,
} from "@/lib/api";

function methodPill(method: string): string {
  switch (method.toUpperCase()) {
    case "GET": return "bg-emerald-100 text-emerald-700";
    case "POST": return "bg-blue-100 text-blue-700";
    case "PUT": return "bg-amber-100 text-amber-700";
    case "PATCH": return "bg-violet-100 text-violet-700";
    case "DELETE": return "bg-rose-100 text-rose-700";
    default: return "bg-surface-container-high text-on-surface-variant";
  }
}

export default function ApiDocsPanel({ apiId, hasOpenApi }: { apiId: string; hasOpenApi: boolean }) {
  const [items, setItems] = useState<DocOperation[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await getApiDocsAdmin(apiId);
      setItems(r.items);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Erro ao carregar documentação");
    } finally {
      setLoading(false);
    }
  }, [apiId]);
  useEffect(() => { load(); }, [load]);

  async function sync() {
    setSyncing(true); setErr(null); setMsg(null);
    try {
      const r = await syncApiDocs(apiId);
      setMsg(`Sincronizado: ${r.created} novas, ${r.updated} atualizadas, ${r.removed} removidas.`);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Falha ao sincronizar");
    } finally { setSyncing(false); }
  }

  async function clear() {
    setClearing(true); setErr(null); setMsg(null);
    try {
      const r = await clearApiDocs(apiId);
      setMsg(`Documentação importada removida: ${r.removed} operações.`);
      setConfirmClear(false);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Falha ao limpar a documentação");
    } finally { setClearing(false); }
  }

  async function toggle(op: DocOperation) {
    // Optimista: reflete o toggle antes da resposta.
    setItems((prev) => prev.map((o) => o.id === op.id ? { ...o, visible: !o.visible } : o));
    try {
      await setApiDocVisible(apiId, op.id, !op.visible);
    } catch (e) {
      setItems((prev) => prev.map((o) => o.id === op.id ? { ...o, visible: op.visible } : o));
      setErr(e instanceof Error ? e.message : "Falha ao atualizar visibilidade");
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-lg font-bold text-on-surface flex items-center gap-2">
          <span className="material-symbols-outlined text-[20px]">menu_book</span> Documentação do cliente
        </h4>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => setConfirmClear(true)}
            disabled={clearing || syncing || items.length === 0}
            title={items.length === 0 ? "Não há documentação importada para limpar" : "Remove as operações importadas (use para doc personalizada)"}
            className="px-4 py-2 rounded-lg bg-surface-container-high text-error font-bold text-xs hover:bg-error/10 disabled:opacity-50">
            {clearing ? "Limpando…" : "Limpar documentação"}
          </button>
          <button type="button" onClick={sync} disabled={syncing || clearing || !hasOpenApi}
            title={hasOpenApi ? "" : "Configure a URL do OpenAPI acima e salve para sincronizar"}
            className="px-4 py-2 rounded-lg bg-surface-container-high text-on-surface font-bold text-xs hover:bg-surface-container-highest disabled:opacity-50">
            {syncing ? "Sincronizando…" : "Sincronizar do OpenAPI"}
          </button>
        </div>
      </div>

      {confirmClear && (
        <div className="bg-error/10 border border-error/30 rounded-xl px-4 py-3 flex items-center justify-between gap-3 text-sm">
          <span className="text-on-surface">
            Remover as {items.length} operações importadas? A doc personalizada (Markdown) não é afetada.
          </span>
          <div className="flex items-center gap-2 shrink-0">
            <button type="button" onClick={() => setConfirmClear(false)} disabled={clearing}
              className="px-3 py-1.5 rounded-lg text-xs font-bold text-on-surface-variant hover:text-on-surface">
              Cancelar
            </button>
            <button type="button" onClick={clear} disabled={clearing}
              className="px-3 py-1.5 rounded-lg text-xs font-bold bg-error text-white hover:brightness-95 disabled:opacity-50">
              {clearing ? "Limpando…" : "Confirmar"}
            </button>
          </div>
        </div>
      )}
      <p className="text-xs text-on-surface-variant">
        Operações importadas do OpenAPI. Desative as que o cliente não deve ver (endpoints operacionais).
      </p>
      {!hasOpenApi && (
        <p className="text-xs text-on-surface-variant">
          Configure a URL do OpenAPI no campo acima e salve a API para habilitar a sincronização.
        </p>
      )}
      {err && <p className="text-xs text-error">{err}</p>}
      {msg && <p className="text-xs text-emerald-600">{msg}</p>}

      <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 overflow-hidden">
        {loading ? (
          <p className="py-6 text-center text-on-surface-variant text-sm">Carregando…</p>
        ) : items.length === 0 ? (
          <p className="py-6 text-center text-on-surface-variant text-sm">
            Nenhuma operação. Clique em &quot;Sincronizar do OpenAPI&quot;.
          </p>
        ) : (
          <div className="divide-y divide-outline-variant/10">
            {items.map((op) => (
              <div key={op.id} className="grid grid-cols-[70px_1fr_auto] items-center gap-3 px-4 py-2.5 text-sm">
                <span className={`text-center text-[10px] font-black uppercase rounded-md py-1 ${methodPill(op.method)}`}>{op.method}</span>
                <div className="min-w-0">
                  <p className="font-mono text-on-surface truncate">{op.path}</p>
                  {op.summary && <p className="text-xs text-on-surface-variant truncate">{op.summary}</p>}
                </div>
                <label className="flex items-center gap-2 cursor-pointer justify-self-end">
                  <span className="text-xs text-on-surface-variant">{op.visible ? "Visível" : "Oculto"}</span>
                  <input type="checkbox" checked={op.visible} onChange={() => toggle(op)} className="accent-primary w-4 h-4" />
                </label>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
