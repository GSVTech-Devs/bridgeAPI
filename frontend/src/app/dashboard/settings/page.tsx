"use client";

import { useEffect, useRef, useState } from "react";
import { changePassword, deleteLogo, getMe, uploadLogo } from "@/lib/api";
import { isValidPassword, PASSWORD_REQUIREMENTS_MESSAGE } from "@/lib/password";
import {
  LOGO_ACCEPT,
  LOGO_REQUIREMENTS_MESSAGE,
  validateLogoFile,
} from "@/lib/branding";
import { useCapabilities } from "@/contexts/CapabilitiesContext";

const inputClass =
  "w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg px-4 py-2.5 text-sm text-on-surface focus:border-primary focus:ring-0 outline-none transition-all";

function BrandingCard() {
  const { logoDataUri, refresh } = useCapabilities();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    setError(null);
    setSuccess(null);
    const file = e.target.files?.[0];
    e.target.value = ""; // permite reenviar o mesmo arquivo
    if (!file) return;

    const validationError = validateLogoFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    try {
      await uploadLogo(file);
      await refresh();
      setSuccess("Logo atualizada com sucesso.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao enviar a logo");
    } finally {
      setLoading(false);
    }
  }

  async function handleRemove() {
    setError(null);
    setSuccess(null);
    setLoading(true);
    try {
      await deleteLogo();
      await refresh();
      setSuccess("Logo removida. Voltamos à marca padrão.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao remover a logo");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/15 p-8 mb-8">
      <h3 className="font-headline font-bold text-on-surface text-lg mb-1">
        Identidade visual
      </h3>
      <p className="text-sm text-on-surface-variant mb-6">
        Personalize a logo exibida no topo do painel. Abaixo dela permanece a
        assinatura “BridgeAPI by GSV Tech”.
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

      <div className="flex items-center gap-6">
        <div className="h-20 w-40 rounded-lg border border-dashed border-outline-variant/40 bg-surface-container-low flex items-center justify-center overflow-hidden shrink-0">
          {logoDataUri ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={logoDataUri}
              alt="Logo atual"
              className="max-h-16 max-w-full object-contain"
            />
          ) : (
            <span className="text-xs text-on-surface-variant text-center px-2">
              Sem logo
            </span>
          )}
        </div>

        <div className="flex-1">
          <div className="flex flex-wrap gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept={LOGO_ACCEPT}
              onChange={handleFileChange}
              className="hidden"
              aria-label="Selecionar logo"
            />
            <button
              type="button"
              disabled={loading}
              onClick={() => fileInputRef.current?.click()}
              className="px-5 py-2.5 rounded-lg bg-gradient-to-br from-primary to-primary-container text-white font-bold text-sm hover:scale-[1.02] transition-all disabled:opacity-60"
            >
              {loading ? "Enviando…" : logoDataUri ? "Trocar logo" : "Enviar logo"}
            </button>
            {logoDataUri && (
              <button
                type="button"
                disabled={loading}
                onClick={handleRemove}
                className="px-5 py-2.5 rounded-lg border border-outline-variant/40 text-on-surface font-bold text-sm hover:bg-surface transition-all disabled:opacity-60"
              >
                Remover
              </button>
            )}
          </div>
          <p className="text-xs text-on-surface-variant mt-3">
            {LOGO_REQUIREMENTS_MESSAGE}
          </p>
        </div>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const [email, setEmail] = useState<string>("");
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const { isOwner } = useCapabilities();

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

      {isOwner && <BrandingCard />}

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
