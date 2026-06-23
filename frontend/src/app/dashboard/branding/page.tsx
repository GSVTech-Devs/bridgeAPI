"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  deleteBrandTheme,
  deleteLogo,
  updateBrandTheme,
  uploadLogo,
} from "@/lib/api";
import {
  LOGO_ACCEPT,
  LOGO_REQUIREMENTS_MESSAGE,
  validateLogoFile,
} from "@/lib/branding";
import {
  BRAND_DEFAULTS,
  BRAND_PRESETS,
  BRAND_SLOTS,
  type BrandMode,
  type BrandSlot,
  type BrandTheme,
  type ModeColors,
  normalizeHex,
  previewModeVars,
  SURFACE_PRESETS,
} from "@/lib/brandColor";
import { useCapabilities } from "@/contexts/CapabilitiesContext";

type Draft = Record<BrandMode, Record<BrandSlot, string>>;

const MODE_LABELS: { mode: BrandMode; label: string; icon: string }[] = [
  { mode: "light", label: "Tema claro", icon: "light_mode" },
  { mode: "dark", label: "Tema escuro", icon: "dark_mode" },
];

export default function BrandingPage() {
  const {
    isOwner,
    loading: capsLoading,
    logoDataUri,
    brandTheme,
    refresh,
  } = useCapabilities();
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

      <ColorSection brandTheme={brandTheme} logoDataUri={logoDataUri} refresh={refresh} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cores da marca: tema completo (claro/escuro × 4 cores) + prévia da página
// ---------------------------------------------------------------------------
function buildDraft(theme: BrandTheme): Draft {
  const fromMode = (mode: BrandMode): Record<BrandSlot, string> => ({
    primary: theme[mode].primary ?? BRAND_DEFAULTS[mode].primary,
    secondary: theme[mode].secondary ?? BRAND_DEFAULTS[mode].secondary,
    tertiary: theme[mode].tertiary ?? BRAND_DEFAULTS[mode].tertiary,
    background: theme[mode].background ?? BRAND_DEFAULTS[mode].background,
  });
  return { light: fromMode("light"), dark: fromMode("dark") };
}

function ColorSection({
  brandTheme,
  logoDataUri,
  refresh,
}: {
  brandTheme: BrandTheme;
  logoDataUri: string | null;
  refresh: () => Promise<void>;
}) {
  const [draft, setDraft] = useState<Draft>(() => buildDraft(brandTheme));
  const [mode, setMode] = useState<BrandMode>("light");
  const [active, setActive] = useState<BrandSlot>("primary");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Ressincroniza com o salvo quando muda (ex.: após salvar/restaurar).
  const themeKey = JSON.stringify(brandTheme);
  useEffect(() => {
    setDraft(buildDraft(brandTheme));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [themeKey]);

  const modeColors = draft[mode];
  const activeValue = modeColors[active];
  const activeNorm = normalizeHex(activeValue);
  const presets = active === "background" ? SURFACE_PRESETS : BRAND_PRESETS;

  const allValid = (["light", "dark"] as BrandMode[]).every((m) =>
    BRAND_SLOTS.every(({ slot }) => normalizeHex(draft[m][slot]))
  );
  const isCustomized = (["light", "dark"] as BrandMode[]).some((m) =>
    BRAND_SLOTS.some(({ slot }) => brandTheme[m][slot])
  );
  const dirty = (["light", "dark"] as BrandMode[]).some((m) =>
    BRAND_SLOTS.some(({ slot }) => {
      const saved = brandTheme[m][slot] ?? BRAND_DEFAULTS[m][slot];
      return (normalizeHex(draft[m][slot]) ?? "") !== saved;
    })
  );

  function setActiveColor(value: string) {
    setDraft((prev) => ({
      ...prev,
      [mode]: { ...prev[mode], [active]: value },
    }));
  }

  // Converte o rascunho no payload, enviando null para cores iguais ao padrão.
  function toPayload(m: BrandMode): Partial<ModeColors> {
    const out: Partial<ModeColors> = {};
    for (const { slot } of BRAND_SLOTS) {
      const norm = normalizeHex(draft[m][slot]);
      out[slot] = norm && norm !== BRAND_DEFAULTS[m][slot] ? norm : null;
    }
    return out;
  }

  async function handleSave() {
    if (!allValid) {
      setError("Há uma cor inválida. Use hexadecimais no formato #RRGGBB.");
      return;
    }
    setError(null);
    setSuccess(null);
    setSaving(true);
    try {
      await updateBrandTheme({ light: toPayload("light"), dark: toPayload("dark") });
      await refresh();
      setSuccess("Tema atualizado com sucesso.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao salvar o tema");
    } finally {
      setSaving(false);
    }
  }

  async function handleReset() {
    setError(null);
    setSuccess(null);
    setSaving(true);
    try {
      await deleteBrandTheme();
      await refresh();
      setSuccess("Tema restaurado para o padrão.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao restaurar o tema");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/15 p-8 mt-6">
      <h3 className="font-headline font-bold text-on-surface text-lg mb-1">
        Cores da marca
      </h3>
      <p className="text-sm text-on-surface-variant mb-6">
        Personalize completamente o painel: as quatro cores — incluindo o fundo —
        para o tema claro e o escuro, de forma independente. Acompanhe o
        resultado na prévia ao lado.
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

      {/* Alternância de modo (qual tema estou editando) */}
      <div className="inline-flex rounded-full bg-surface-container-low p-1 mb-5">
        {MODE_LABELS.map((m) => {
          const isSel = mode === m.mode;
          return (
            <button
              key={m.mode}
              type="button"
              onClick={() => setMode(m.mode)}
              className={`flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-bold transition-all ${
                isSel
                  ? "bg-primary text-on-primary"
                  : "text-on-surface-variant hover:text-on-surface"
              }`}
            >
              <span className="material-symbols-outlined text-[16px]">{m.icon}</span>
              {m.label}
            </button>
          );
        })}
      </div>

      {/* Seleção do slot a editar (no modo atual) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        {BRAND_SLOTS.map(({ slot, label, hint }) => {
          const isActive = active === slot;
          const norm = normalizeHex(modeColors[slot]) ?? BRAND_DEFAULTS[mode][slot];
          return (
            <button
              key={slot}
              type="button"
              onClick={() => setActive(slot)}
              className={`text-left rounded-xl border p-3 transition-all ${
                isActive
                  ? "border-primary ring-1 ring-primary bg-surface-container-low"
                  : "border-outline-variant/30 hover:bg-surface-container-low"
              }`}
            >
              <span
                className="block h-8 w-full rounded-lg border border-black/10 mb-2"
                style={{ backgroundColor: norm }}
              />
              <span className="block text-sm font-bold text-on-surface">{label}</span>
              <span className="block text-[11px] text-on-surface-variant leading-tight mt-0.5">
                {hint}
              </span>
            </button>
          );
        })}
      </div>

      {/* Editor da cor ativa */}
      <div className="rounded-xl border border-outline-variant/20 bg-surface-container-low p-4 mb-6">
        <div className="flex flex-wrap gap-2 mb-4">
          {presets.map((preset) => {
            const isSel = activeNorm === normalizeHex(preset.hex);
            return (
              <button
                key={preset.hex}
                type="button"
                title={preset.name}
                aria-label={preset.name}
                aria-pressed={isSel}
                onClick={() => setActiveColor(preset.hex)}
                className={`h-8 w-8 rounded-full border border-black/10 transition-all ${
                  isSel
                    ? "ring-2 ring-offset-2 ring-offset-surface-container-low ring-on-surface scale-110"
                    : "hover:scale-110"
                }`}
                style={{ backgroundColor: preset.hex }}
              />
            );
          })}
        </div>
        <div className="flex items-center gap-2">
          <input
            type="color"
            aria-label="Escolher cor personalizada"
            value={activeNorm ?? BRAND_DEFAULTS[mode][active]}
            onChange={(e) => setActiveColor(e.target.value)}
            className="h-10 w-12 rounded-lg border border-outline-variant/40 bg-transparent cursor-pointer p-1"
          />
          <input
            type="text"
            aria-label="Código hexadecimal da cor"
            value={activeValue}
            onChange={(e) => setActiveColor(e.target.value)}
            placeholder="#2b5ab5"
            spellCheck={false}
            className={`w-32 px-3 py-2 rounded-lg bg-surface-container-lowest text-on-surface text-sm font-mono outline-none border transition-all focus:ring-1 focus:ring-primary focus:border-primary ${
              activeNorm ? "border-outline-variant/40" : "border-error"
            }`}
          />
        </div>
      </div>

      {/* Prévia da página principal (reflete o modo em edição) */}
      <p className="text-xs font-bold text-on-surface-variant mb-2">
        Prévia da página · {mode === "light" ? "tema claro" : "tema escuro"}
      </p>
      <PagePreview colors={modeColors} mode={mode} logoDataUri={logoDataUri} />

      <div className="flex flex-wrap gap-3 mt-7">
        <button
          type="button"
          disabled={saving || !dirty || !allValid}
          onClick={handleSave}
          className="px-5 py-2.5 rounded-lg bg-gradient-to-br from-primary to-primary-container text-white font-bold text-sm hover:scale-[1.02] transition-all disabled:opacity-60 disabled:hover:scale-100"
        >
          {saving ? "Salvando…" : "Salvar tema"}
        </button>
        {isCustomized && (
          <button
            type="button"
            disabled={saving}
            onClick={handleReset}
            className="px-5 py-2.5 rounded-lg border border-outline-variant/40 text-on-surface font-bold text-sm hover:bg-surface transition-all disabled:opacity-60"
          >
            Restaurar padrão
          </button>
        )}
      </div>
    </div>
  );
}

// Mini-réplica do painel que reflete as cores/modo escolhidos ao vivo. Aplica o
// conjunto COMPLETO de variáveis derivadas (inclusive fundo) num contêiner
// isolado, então mostra o modo escolhido independentemente do tema da página.
function PagePreview({
  colors,
  mode,
  logoDataUri,
}: {
  colors: ModeColors;
  mode: BrandMode;
  logoDataUri: string | null;
}) {
  const style = previewModeVars(colors, mode) as React.CSSProperties;

  const navItems = [
    { icon: "dashboard", label: "Dashboard", active: true },
    { icon: "api", label: "Catalog", active: false },
    { icon: "vpn_key", label: "My Keys", active: false },
    { icon: "analytics", label: "Métricas", active: false },
  ];

  return (
    <div
      style={style}
      className="rounded-xl border border-outline-variant/20 overflow-hidden bg-background flex h-64 text-[9px] select-none"
    >
      {/* Sidebar */}
      <div className="w-1/4 bg-surface-container-low flex flex-col p-2.5 gap-2">
        <div className="h-6 flex items-center mb-1">
          {logoDataUri ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={logoDataUri} alt="" className="max-h-5 max-w-full object-contain" />
          ) : (
            <span className="font-black text-on-surface text-[11px]">Bridge API</span>
          )}
        </div>
        {navItems.map((item) => (
          <div
            key={item.label}
            className={
              item.active
                ? "flex items-center gap-1.5 px-2 py-1.5 rounded-full bg-surface-container-lowest text-primary font-bold border-r-2 border-primary"
                : "flex items-center gap-1.5 px-2 py-1.5 rounded-full text-on-surface-variant"
            }
          >
            <span
              className="material-symbols-outlined text-[12px]"
              style={item.active ? { fontVariationSettings: "'FILL' 1" } : undefined}
            >
              {item.icon}
            </span>
            <span>{item.label}</span>
          </div>
        ))}
      </div>

      {/* Área principal */}
      <div className="flex-1 flex flex-col bg-surface">
        {/* Header */}
        <div className="h-8 flex items-center justify-between px-3 border-b border-outline-variant/15">
          <div className="flex items-center gap-1 bg-surface-container-low rounded-full px-2 py-1 w-24 border border-outline-variant/15">
            <span className="material-symbols-outlined text-on-surface-variant text-[11px]">
              search
            </span>
            <span className="text-on-surface-variant">Buscar…</span>
          </div>
          <div className="h-5 w-5 rounded-full bg-primary text-on-primary flex items-center justify-center font-bold">
            B
          </div>
        </div>

        {/* Conteúdo */}
        <div className="flex-1 p-3 space-y-2.5 overflow-hidden">
          {/* Hero gradiente (primária) */}
          <div className="primary-gradient rounded-lg p-2.5">
            <div className="h-1.5 w-20 rounded-full bg-white/70 mb-1.5" />
            <div className="h-1.5 w-14 rounded-full bg-white/40" />
          </div>

          {/* Cards de estatística — um por cor */}
          <div className="grid grid-cols-3 gap-2">
            {[
              { chip: "bg-primary-container text-on-primary-container", icon: "trending_up" },
              { chip: "bg-secondary-container text-on-secondary-container", icon: "bolt" },
              { chip: "bg-tertiary-container text-on-tertiary-container", icon: "check_circle" },
            ].map((card, i) => (
              <div
                key={i}
                className="rounded-lg bg-surface-container-lowest border border-outline-variant/15 p-2"
              >
                <span
                  className={`material-symbols-outlined text-[12px] rounded-md px-1 py-0.5 ${card.chip}`}
                >
                  {card.icon}
                </span>
                <div className="h-1.5 w-8 rounded-full bg-on-surface/70 mt-1.5" />
                <div className="h-1 w-10 rounded-full bg-on-surface-variant/40 mt-1" />
              </div>
            ))}
          </div>

          {/* Selos usando as três cores de marca */}
          <div className="flex items-center gap-1.5">
            <span className="px-2 py-0.5 rounded-full bg-primary text-on-primary font-bold">
              Primária
            </span>
            <span className="px-2 py-0.5 rounded-full bg-secondary text-on-secondary font-bold">
              Secundária
            </span>
            <span className="px-2 py-0.5 rounded-full bg-tertiary-container text-on-tertiary-container font-bold">
              Terciária
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
