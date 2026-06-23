// Tema de marca do portal — espelha backend/app/domains/branding (validação) e
// deriva, no cliente, as variáveis CSS do tema a partir das cores escolhidas
// pelo responsável da conta. Cada modo (claro/escuro) tem 4 cores editáveis:
// primária, secundária, terciária e fundo.

export type BrandSlot = "primary" | "secondary" | "tertiary" | "background";
export type BrandMode = "light" | "dark";

export type ModeColors = {
  primary: string | null;
  secondary: string | null;
  tertiary: string | null;
  background: string | null;
};

export type BrandTheme = { light: ModeColors; dark: ModeColors };

export const EMPTY_MODE_COLORS: ModeColors = {
  primary: null,
  secondary: null,
  tertiary: null,
  background: null,
};

export const EMPTY_BRAND_THEME: BrandTheme = {
  light: { ...EMPTY_MODE_COLORS },
  dark: { ...EMPTY_MODE_COLORS },
};

/** Cores padrão de cada modo (iguais às variáveis em globals.css). */
export const BRAND_DEFAULTS: Record<BrandMode, Record<BrandSlot, string>> = {
  light: {
    primary: "#2b5ab5", // 43 90 181
    secondary: "#005faf", // 0 95 175
    tertiary: "#006493", // 0 100 147
    background: "#f3faff", // 243 250 255
  },
  dark: {
    primary: "#adc6ff", // 173 198 255
    secondary: "#afc7fb", // 175 199 251
    tertiary: "#ffb691", // 255 182 145
    background: "#00161f", // 0 22 31
  },
};

export const BRAND_SLOTS: { slot: BrandSlot; label: string; hint: string }[] = [
  { slot: "primary", label: "Primária", hint: "Botões e destaques" },
  { slot: "secondary", label: "Secundária", hint: "Realces e selos" },
  { slot: "tertiary", label: "Terciária", hint: "Etiquetas e avisos" },
  { slot: "background", label: "Fundo", hint: "Painel e cartões" },
];

/** Atalhos de cores prontas para uma escolha rápida e intuitiva. */
export const BRAND_PRESETS: { name: string; hex: string }[] = [
  { name: "Azul", hex: "#2b5ab5" },
  { name: "Índigo", hex: "#4f46e5" },
  { name: "Violeta", hex: "#7c3aed" },
  { name: "Petróleo", hex: "#0e7490" },
  { name: "Esmeralda", hex: "#059669" },
  { name: "Verde", hex: "#15803d" },
  { name: "Âmbar", hex: "#b45309" },
  { name: "Laranja", hex: "#ea580c" },
  { name: "Vermelho", hex: "#dc2626" },
  { name: "Rosa", hex: "#db2777" },
  { name: "Grafite", hex: "#475569" },
  { name: "Preto", hex: "#1f2937" },
];

/** Tons de fundo claros, úteis como atalho para o slot "Fundo" do modo claro. */
export const SURFACE_PRESETS: { name: string; hex: string }[] = [
  { name: "Branco", hex: "#ffffff" },
  { name: "Névoa azul", hex: "#f3faff" },
  { name: "Areia", hex: "#faf7f0" },
  { name: "Menta", hex: "#f0faf4" },
  { name: "Grafite", hex: "#1a1f2b" },
  { name: "Ardósia", hex: "#0f172a" },
  { name: "Petróleo", hex: "#00161f" },
  { name: "Carvão", hex: "#111111" },
];

const HEX_RE = /^#[0-9a-fA-F]{6}$/;

/** Normaliza para `#rrggbb` minúsculo, ou retorna null se inválido. */
export function normalizeHex(value: string): string | null {
  const v = value.trim().toLowerCase();
  return HEX_RE.test(v) ? v : null;
}

type Rgb = { r: number; g: number; b: number };
type Hsl = { h: number; s: number; l: number };

function hexToRgb(hex: string): Rgb {
  return {
    r: parseInt(hex.slice(1, 3), 16),
    g: parseInt(hex.slice(3, 5), 16),
    b: parseInt(hex.slice(5, 7), 16),
  };
}

function rgbToHsl({ r, g, b }: Rgb): Hsl {
  const rn = r / 255;
  const gn = g / 255;
  const bn = b / 255;
  const max = Math.max(rn, gn, bn);
  const min = Math.min(rn, gn, bn);
  const d = max - min;
  let h = 0;
  if (d !== 0) {
    if (max === rn) h = ((gn - bn) / d) % 6;
    else if (max === gn) h = (bn - rn) / d + 2;
    else h = (rn - gn) / d + 4;
    h *= 60;
    if (h < 0) h += 360;
  }
  const l = (max + min) / 2;
  const s = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1));
  return { h, s: s * 100, l: l * 100 };
}

function hslToRgb({ h, s, l }: Hsl): Rgb {
  const sn = s / 100;
  const ln = l / 100;
  const c = (1 - Math.abs(2 * ln - 1)) * sn;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = ln - c / 2;
  let r = 0;
  let g = 0;
  let b = 0;
  if (h < 60) [r, g, b] = [c, x, 0];
  else if (h < 120) [r, g, b] = [x, c, 0];
  else if (h < 180) [r, g, b] = [0, c, x];
  else if (h < 240) [r, g, b] = [0, x, c];
  else if (h < 300) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];
  return {
    r: Math.round((r + m) * 255),
    g: Math.round((g + m) * 255),
    b: Math.round((b + m) * 255),
  };
}

const triple = ({ r, g, b }: Rgb) => `${r} ${g} ${b}`;

/** Gera um tom: mesma matiz/saturação da base, com a luminosidade dada. */
function tone(base: Hsl, l: number): Rgb {
  return hslToRgb({ h: base.h, s: base.s, l: Math.max(0, Math.min(100, l)) });
}

/** Mistura duas cores no espaço RGB (t=0 → a, t=1 → b). */
function mix(a: Rgb, b: Rgb, t: number): Rgb {
  return {
    r: Math.round(a.r + (b.r - a.r) * t),
    g: Math.round(a.g + (b.g - a.g) * t),
    b: Math.round(a.b + (b.b - a.b) * t),
  };
}

const WHITE: Rgb = { r: 255, g: 255, b: 255 };
const BLACK: Rgb = { r: 0, g: 0, b: 0 };

/** Luminância relativa (WCAG) para escolher texto claro/escuro sobre a cor. */
function luminance({ r, g, b }: Rgb): number {
  const ch = [r, g, b].map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
}

/** Texto legível ("on") sobre um fundo: quase-branco ou quase-preto. */
function onColor(bg: Rgb): Rgb {
  return luminance(bg) > 0.45
    ? { r: 23, g: 30, b: 38 }
    : { r: 255, g: 255, b: 255 };
}

type VarMap = Record<string, string>;
export type ThemeVars = { light: VarMap; dark: VarMap };

/**
 * Variáveis CSS de um slot de cor (primary/secondary/tertiary) para um modo.
 * Em ambos os modos a cor escolhida vira a cor "principal"; o container é um
 * tom mais claro (modo claro) ou mais escuro (modo escuro). `primary` também
 * controla `surface-tint`/`inverse-primary`.
 */
function deriveColorGroup(
  slot: Exclude<BrandSlot, "background">,
  hex: string,
  mode: BrandMode
): VarMap {
  const main = hexToRgb(hex);
  const base = rgbToHsl(main);
  const seed: Hsl = { h: base.h, s: Math.max(base.s, 8), l: base.l };
  const container =
    mode === "light"
      ? tone(seed, Math.min(base.l + 12, 90))
      : tone(seed, Math.max(base.l - 30, 22));

  const out: VarMap = {
    [`--color-${slot}`]: triple(main),
    [`--color-${slot}-container`]: triple(container),
    [`--color-on-${slot}`]: triple(onColor(main)),
    [`--color-on-${slot}-container`]: triple(onColor(container)),
  };
  if (slot === "primary") {
    out["--color-surface-tint"] = triple(main);
    out["--color-inverse-primary"] =
      mode === "light" ? triple(tone(seed, 80)) : triple(tone(seed, 40));
  }
  return out;
}

/**
 * Variáveis CSS das superfícies derivadas de uma cor de fundo, para um modo.
 * Mantém a matiz do fundo e escalona claros/escuros mantendo contraste; o texto
 * (`on-surface`) é sempre o oposto, garantindo legibilidade.
 */
function deriveSurface(hex: string, mode: BrandMode): VarMap {
  const seed = hexToRgb(hex);
  const onSurface =
    mode === "light" ? mix(seed, BLACK, 0.86) : mix(seed, WHITE, 0.86);
  const onVariant =
    mode === "light" ? mix(seed, BLACK, 0.62) : mix(seed, WHITE, 0.62);

  const ladder =
    mode === "light"
      ? {
          lowest: mix(seed, WHITE, 0.75),
          low: mix(seed, WHITE, 0.45),
          base: seed,
          container: mix(seed, BLACK, 0.04),
          high: mix(seed, BLACK, 0.08),
          highest: mix(seed, BLACK, 0.12),
          bright: mix(seed, WHITE, 0.3),
          dim: mix(seed, BLACK, 0.14),
          variant: mix(seed, BLACK, 0.1),
        }
      : {
          lowest: mix(seed, BLACK, 0.4),
          low: mix(seed, WHITE, 0.05),
          base: seed,
          container: mix(seed, WHITE, 0.08),
          high: mix(seed, WHITE, 0.14),
          highest: mix(seed, WHITE, 0.2),
          bright: mix(seed, WHITE, 0.26),
          dim: seed,
          variant: mix(seed, WHITE, 0.12),
        };

  return {
    "--color-background": triple(seed),
    "--color-on-background": triple(onSurface),
    "--color-surface": triple(ladder.base),
    "--color-surface-bright": triple(ladder.bright),
    "--color-surface-dim": triple(ladder.dim),
    "--color-surface-variant": triple(ladder.variant),
    "--color-surface-container": triple(ladder.container),
    "--color-surface-container-low": triple(ladder.low),
    "--color-surface-container-lowest": triple(ladder.lowest),
    "--color-surface-container-high": triple(ladder.high),
    "--color-surface-container-highest": triple(ladder.highest),
    "--color-on-surface": triple(onSurface),
    "--color-on-surface-variant": triple(onVariant),
    "--color-outline": triple(
      mode === "light" ? mix(seed, BLACK, 0.5) : mix(seed, WHITE, 0.45)
    ),
    "--color-outline-variant": triple(
      mode === "light" ? mix(seed, BLACK, 0.22) : mix(seed, WHITE, 0.22)
    ),
  };
}

/** Todas as variáveis de um modo a partir das cores dele. */
function deriveModeVars(
  colors: ModeColors,
  mode: BrandMode,
  { skipDefaults }: { skipDefaults: boolean }
): VarMap {
  const out: VarMap = {};
  for (const slot of ["primary", "secondary", "tertiary"] as const) {
    const hex = normalizeHex(colors[slot] ?? "");
    if (!hex) continue;
    if (skipDefaults && hex === BRAND_DEFAULTS[mode][slot]) continue;
    Object.assign(out, deriveColorGroup(slot, hex, mode));
  }
  const bg = normalizeHex(colors.background ?? "");
  if (bg && !(skipDefaults && bg === BRAND_DEFAULTS[mode].background)) {
    Object.assign(out, deriveSurface(bg, mode));
  }
  return out;
}

/**
 * Variáveis CSS de marca para os dois modos. Um slot só é emitido quando
 * difere do padrão — assim os slots não personalizados preservam o tema
 * afinado à mão de globals.css. Usado pela injeção global do tema.
 */
export function brandThemeVars(theme: BrandTheme): ThemeVars {
  return {
    light: deriveModeVars(theme.light, "light", { skipDefaults: true }),
    dark: deriveModeVars(theme.dark, "dark", { skipDefaults: true }),
  };
}

/** Monta o CSS (`:root` + `html.dark`) que sobrescreve o tema base. */
export function brandThemeCss(theme: BrandTheme): string | null {
  const { light, dark } = brandThemeVars(theme);
  const entries = (vars: VarMap) =>
    Object.entries(vars)
      .map(([k, v]) => `${k}: ${v};`)
      .join(" ");
  const parts: string[] = [];
  if (Object.keys(light).length) parts.push(`:root{${entries(light)}}`);
  if (Object.keys(dark).length) parts.push(`html.dark{${entries(dark)}}`);
  return parts.length ? parts.join(" ") : null;
}

/**
 * Conjunto COMPLETO de variáveis de um modo para a prévia isolada: deriva
 * todos os slots (usando o padrão do modo quando vazios), de forma que a prévia
 * mostre o modo escolhido independentemente do tema atual da página.
 */
export function previewModeVars(colors: ModeColors, mode: BrandMode): VarMap {
  const filled: ModeColors = {
    primary: colors.primary ?? BRAND_DEFAULTS[mode].primary,
    secondary: colors.secondary ?? BRAND_DEFAULTS[mode].secondary,
    tertiary: colors.tertiary ?? BRAND_DEFAULTS[mode].tertiary,
    background: colors.background ?? BRAND_DEFAULTS[mode].background,
  };
  return deriveModeVars(filled, mode, { skipDefaults: false });
}
