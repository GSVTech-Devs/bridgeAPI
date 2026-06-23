"use client";

import { useEffect } from "react";
import { type BrandTheme, brandThemeCss } from "@/lib/brandColor";

const STYLE_ID = "brand-theme";

/**
 * Aplica o tema de marca da conta em todo o painel, sobrescrevendo as variáveis
 * CSS do tema (globals.css) com um <style> injetado no fim do <head>, separado
 * por modo (`:root` para claro, `html.dark` para escuro). Sem cores definidas,
 * remove o override e o tema volta ao padrão.
 *
 * Não renderiza nada visível; deve ficar dentro do CapabilitiesProvider.
 */
export function BrandThemeStyle({ theme }: { theme: BrandTheme }) {
  const css = brandThemeCss(theme);

  useEffect(() => {
    const existing = document.getElementById(STYLE_ID);

    if (!css) {
      existing?.remove();
      return;
    }

    const el =
      (existing as HTMLStyleElement | null) ?? document.createElement("style");
    el.id = STYLE_ID;
    el.textContent = css;
    if (!existing) document.head.appendChild(el);
  }, [css]);

  return null;
}
