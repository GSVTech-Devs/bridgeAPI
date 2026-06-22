"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { deleteLogo, uploadLogo } from "@/lib/api";
import {
  LOGO_ACCEPT,
  LOGO_REQUIREMENTS_MESSAGE,
  validateLogoFile,
} from "@/lib/branding";
import { useCapabilities } from "@/contexts/CapabilitiesContext";

export default function BrandingPage() {
  const { isOwner, loading: capsLoading, logoDataUri, refresh } =
    useCapabilities();
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Identidade visual é exclusiva do responsável (owner) da conta.
  useEffect(() => {
    if (!capsLoading && !isOwner) {
      router.replace("/dashboard");
    }
  }, [capsLoading, isOwner, router]);

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

  if (capsLoading || !isOwner) {
    return null;
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-10">
        <h2 className="font-headline text-3xl font-extrabold text-on-surface tracking-tight">
          Identidade visual
        </h2>
        <p className="text-on-surface-variant mt-1">
          Personalize a marca exibida no painel da sua conta.
        </p>
      </div>

      <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/15 p-8">
        <h3 className="font-headline font-bold text-on-surface text-lg mb-1">
          Logo
        </h3>
        <p className="text-sm text-on-surface-variant mb-6">
          A logo aparece no topo do painel. Abaixo dela permanece a assinatura
          “BridgeAPI by GSV Tech”.
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
    </div>
  );
}
