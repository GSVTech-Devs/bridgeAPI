// Política de upload da logo — espelha backend/app/domains/branding/service.py.

export const LOGO_ALLOWED_TYPES = [
  "image/png",
  "image/jpeg",
  "image/webp",
] as const;

export const LOGO_ACCEPT = LOGO_ALLOWED_TYPES.join(",");

export const LOGO_MAX_BYTES = 5 * 1024 * 1024; // 5 MB

export const LOGO_REQUIREMENTS_MESSAGE =
  "PNG, JPG ou WEBP · até 5 MB · recomendado ~320×80 px com fundo transparente";

/** Validação client-side; retorna a mensagem de erro ou null se estiver ok. */
export function validateLogoFile(file: File): string | null {
  if (!LOGO_ALLOWED_TYPES.includes(file.type as (typeof LOGO_ALLOWED_TYPES)[number])) {
    return "Formato inválido. Envie PNG, JPG ou WEBP.";
  }
  if (file.size > LOGO_MAX_BYTES) {
    return "Arquivo muito grande. O limite é 5 MB.";
  }
  return null;
}
