"use client";

import { useEffect, useState } from "react";
import { changePassword, getMe } from "@/lib/api";
import { isValidPassword, PASSWORD_REQUIREMENTS_MESSAGE } from "@/lib/password";

const inputClass =
  "w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg px-4 py-2.5 text-sm text-on-surface focus:border-primary focus:ring-0 outline-none transition-all";

export default function SettingsPage() {
  const [email, setEmail] = useState<string>("");
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    getMe()
      .then((me) => setEmail(me.email))
      .catch(() => {});
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (next !== confirm) {
      setError("A confirmação não corresponde à nova senha.");
      return;
    }
    if (!isValidPassword(next)) {
      setError(PASSWORD_REQUIREMENTS_MESSAGE);
      return;
    }

    setLoading(true);
    try {
      await changePassword({ current_password: current, new_password: next });
      setCurrent("");
      setNext("");
      setConfirm("");
      setSuccess("Senha alterada com sucesso.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao alterar a senha");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-10">
        <h2 className="font-headline text-3xl font-extrabold text-on-surface tracking-tight">
          Configurações
        </h2>
        <p className="text-on-surface-variant mt-1">
          Gerencie as credenciais de acesso da sua conta.
        </p>
      </div>

      <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/15 p-8">
        <h3 className="font-headline font-bold text-on-surface text-lg mb-1">
          Segurança
        </h3>
        <p className="text-sm text-on-surface-variant mb-6">
          Altere a senha de acesso ao portal.
        </p>

        {error && (
          <div role="alert" className="mb-4 p-3 bg-error-container rounded-lg text-on-error-container text-sm">
            {error}
          </div>
        )}
        {success && (
          <div role="status" className="mb-4 p-3 bg-tertiary-container rounded-lg text-on-tertiary-container text-sm">
            {success}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-outline uppercase tracking-widest mb-1.5">
              Senha atual
            </label>
            <input
              aria-label="Senha atual"
              type="password"
              className={inputClass}
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-outline uppercase tracking-widest mb-1.5">
              Nova senha
            </label>
            <input
              aria-label="Nova senha"
              type="password"
              className={inputClass}
              value={next}
              onChange={(e) => setNext(e.target.value)}
              minLength={8}
              required
            />
            <p className="text-xs text-on-surface-variant mt-1.5">
              {PASSWORD_REQUIREMENTS_MESSAGE}
            </p>
          </div>

          <div>
            <label className="block text-xs font-bold text-outline uppercase tracking-widest mb-1.5">
              Confirmar nova senha
            </label>
            <input
              aria-label="Confirmar nova senha"
              type="password"
              className={inputClass}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              minLength={8}
              required
            />
          </div>

          <div className="pt-2">
            <button
              type="submit"
              disabled={loading}
              className="px-6 py-2.5 rounded-lg bg-gradient-to-br from-primary to-primary-container text-white font-bold text-sm hover:scale-[1.02] transition-all disabled:opacity-60"
            >
              {loading ? "Salvando…" : "Alterar senha"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
