"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getCatalog,
  getClientApiCaptchas, createClientApiCaptcha, updateClientApiCaptcha, deleteClientApiCaptcha,
  type Captcha, type CaptchaInput,
} from "@/lib/api";
import { useCapabilities } from "@/contexts/CapabilitiesContext";
import { CAP } from "@/lib/capabilities";

type Api = { id: string; name: string; uses_captcha?: boolean };

function statusPill(s: string): string {
  switch (s) {
    case "active": return "bg-green-600 text-white";
    case "failing": return "bg-error text-on-error";
    default: return "bg-surface-container-high text-on-surface-variant";
  }
}

const EMPTY: CaptchaInput = {
  name: "", provider: "", api_key: "", balance_usd: null, priority: 100,
};

export default function ClientCaptchaPage() {
  const { can, loading: capsLoading } = useCapabilities();
  const allowed = can(CAP.CAPTCHA);

  const [apis, setApis] = useState<Api[]>([]);
  const [apiId, setApiId] = useState<string>("");
  const [items, setItems] = useState<Captcha[]>([]);
  const [notEnabled, setNotEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<CaptchaInput>(EMPTY);
  const [saving, setSaving] = useState(false);

  const loadApis = useCallback(async () => {
    const c = await getCatalog();
    const usable = c.items.filter((a) => a.uses_captcha);
    setApis(usable);
    if (!apiId && usable.length) setApiId(usable[0].id);
  }, [apiId]);

  const loadItems = useCallback(async (id: string) => {
    if (!id) { setItems([]); return; }
    setNotEnabled(false);
    try {
      const c = await getClientApiCaptchas(id);
      setItems(c.items);
    } catch {
      setItems([]);
      setNotEnabled(true);
    }
  }, []);

  useEffect(() => {
    if (!allowed) { setLoading(false); return; }
    loadApis().catch((e) => setErr(String(e))).finally(() => setLoading(false));
  }, [loadApis, allowed]);

  useEffect(() => {
    if (apiId && allowed) loadItems(apiId).catch((e) => setErr(String(e)));
  }, [apiId, allowed, loadItems]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErr(null);
    try {
      await createClientApiCaptcha(apiId, {
        ...form,
        provider: form.provider || null,
        api_key: form.api_key || null,
        balance_usd: form.balance_usd ?? null,
      });
      setShowForm(false);
      setForm(EMPTY);
      await loadItems(apiId);
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Falha ao criar provedor");
    } finally {
      setSaving(false);
    }
  }

  async function toggle(c: Captcha) {
    await updateClientApiCaptcha(apiId, c.id, { status: c.status === "active" ? "inactive" : "active" });
    await loadItems(apiId);
  }

  async function remove(id: string) {
    if (!confirm("Remover este provedor?")) return;
    await deleteClientApiCaptcha(apiId, id);
    await loadItems(apiId);
  }

  const field = (k: keyof CaptchaInput, v: string | number | null) =>
    setForm((f) => ({ ...f, [k]: v }));

  if (!capsLoading && !allowed) {
    return (
      <div className="max-w-3xl mx-auto py-20 text-center">
        <span className="material-symbols-outlined text-5xl text-on-surface-variant">lock</span>
        <p className="mt-4 text-on-surface-variant">
          Você não tem acesso à gestão de captcha. Fale com o responsável da conta.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-10">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-4xl font-extrabold tracking-tight text-on-surface font-headline mb-2">
            Meus captchas
          </h2>
          <p className="text-on-surface-variant font-medium">
            Configure seus próprios provedores de captcha por API — quando o provedor da Bridge habilita isso.
          </p>
        </div>
        {apiId && !notEnabled && (
          <button
            onClick={() => { setForm(EMPTY); setShowForm(true); }}
            className="px-5 py-2.5 rounded-xl bg-primary text-white font-bold text-sm hover:opacity-90"
          >
            + Novo provedor
          </button>
        )}
      </div>

      {err && <div className="bg-error-container/30 text-error rounded-lg px-4 py-3 text-sm">{err}</div>}

      <section className="space-y-3">
        <div className="flex items-center gap-3">
          <label className="text-sm font-bold text-on-surface-variant">API:</label>
          <select
            value={apiId}
            onChange={(e) => setApiId(e.target.value)}
            className="px-3 py-2 rounded-lg bg-surface-container border border-outline-variant/20 text-sm text-on-surface"
          >
            {apis.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </div>

        {notEnabled ? (
          <p className="py-12 text-center text-on-surface-variant text-sm bg-surface-container-lowest rounded-xl border border-outline-variant/10">
            O provedor não habilitou a configuração do seu captcha nesta API.
          </p>
        ) : (
          <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 overflow-hidden">
            {loading ? (
              <p className="py-12 text-center text-on-surface-variant text-sm">Carregando…</p>
            ) : apis.length === 0 ? (
              <p className="py-12 text-center text-on-surface-variant text-sm">Nenhuma API com captcha disponível.</p>
            ) : items.length === 0 ? (
              <p className="py-12 text-center text-on-surface-variant text-sm">Nenhum provedor seu nesta API ainda.</p>
            ) : (
              <div className="divide-y divide-outline-variant/10">
                {items.map((c) => (
                  <div key={c.id} className="grid grid-cols-[90px_1fr_130px_90px_120px] items-center gap-3 px-5 py-3.5 text-sm">
                    <span className={`text-center text-[10px] font-black uppercase rounded-md py-1 ${statusPill(c.status)}`}>
                      {c.status}
                    </span>
                    <div className="min-w-0">
                      <p className="font-bold text-on-surface truncate">{c.name}</p>
                      <p className="text-xs text-on-surface-variant truncate">
                        {c.provider ?? "—"} · {c.has_api_key ? "chave ✓" : "sem chave"}
                      </p>
                      {c.last_error && <p className="text-xs text-error truncate">⚠ {c.last_error}</p>}
                    </div>
                    <span className="text-xs text-on-surface-variant">
                      {c.balance_usd != null ? `US$ ${c.balance_usd.toFixed(2)}` : "saldo —"} · prio {c.priority}
                    </span>
                    <button onClick={() => toggle(c)} className="text-xs font-bold text-primary hover:underline justify-self-start">
                      {c.status === "active" ? "Desativar" : "Ativar"}
                    </button>
                    <button onClick={() => remove(c.id)} className="text-on-surface-variant hover:text-error justify-self-end">
                      <span className="material-symbols-outlined text-[20px]">delete</span>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setShowForm(false)}>
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={submit}
            className="bg-surface-container-lowest rounded-2xl p-6 w-full max-w-md space-y-4"
          >
            <h3 className="text-xl font-bold text-on-surface">Novo provedor de captcha</h3>
            <div className="grid grid-cols-2 gap-3">
              <Input label="Nome" value={form.name} onChange={(v) => field("name", v)} required />
              <Input label="Provedor" value={form.provider ?? ""} onChange={(v) => field("provider", v)} />
              <Input label="API key" value={form.api_key ?? ""} onChange={(v) => field("api_key", v)} />
              <Input label="Saldo (US$)" type="number" value={form.balance_usd != null ? String(form.balance_usd) : ""} onChange={(v) => field("balance_usd", v === "" ? null : Number(v))} />
              <Input label="Prioridade" type="number" value={String(form.priority)} onChange={(v) => field("priority", Number(v))} />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 rounded-lg text-on-surface-variant font-bold text-sm hover:bg-surface-container">
                Cancelar
              </button>
              <button type="submit" disabled={saving} className="px-5 py-2 rounded-lg bg-primary text-white font-bold text-sm hover:opacity-90 disabled:opacity-50">
                {saving ? "Salvando…" : "Criar"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

function Input({ label, value, onChange, type = "text", required = false }: {
  label: string; value: string; onChange: (v: string) => void; type?: string; required?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-bold text-on-surface-variant">{label}</label>
      <input
        type={type} value={value} required={required}
        onChange={(e) => onChange(e.target.value)}
        className="px-3 py-2 rounded-lg bg-surface-container border border-outline-variant/20 text-sm text-on-surface focus:outline-none focus:border-primary"
      />
    </div>
  );
}
