// Requisitos mínimos de senha, espelhando a validação do backend:
// 8+ caracteres, ao menos uma letra maiúscula, um número e um caractere especial.
export const PASSWORD_REGEX =
  /^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/;

export const PASSWORD_REQUIREMENTS_MESSAGE =
  "A senha deve ter no mínimo 8 caracteres e incluir ao menos uma letra maiúscula, um número e um caractere especial.";

export function isValidPassword(password: string): boolean {
  return PASSWORD_REGEX.test(password);
}
