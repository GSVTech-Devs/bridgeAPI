// Capabilities de dashboard (RBAC do portal). Espelha app/core/authz.py.
// A fonte de verdade do acesso é o backend; estes valores controlam apenas o
// que a UI mostra/esconde.

export const CAP = {
  API_KEYS: "api_keys",
  KEYS_ROTATE: "keys_rotate",
  GLOBAL_KEYS: "global_keys",
  LOGS: "logs",
  METRICS: "metrics",
  CLIENT_USAGE: "client_usage",
  FINANCIAL: "financial",
  PROXIES: "proxies",
  CAPTCHA: "captcha",
  MEMBERS: "members",
} as const;

export type Capability = (typeof CAP)[keyof typeof CAP];

// Capabilities que o owner pode ligar/desligar por role (toggles na UI).
export const ASSIGNABLE_CAPABILITIES: {
  value: Capability;
  label: string;
  description: string;
  icon: string;
}[] = [
  {
    value: CAP.API_KEYS,
    label: "Ver chaves de API",
    description: "Visualizar a lista de chaves de API da conta.",
    icon: "vpn_key",
  },
  {
    value: CAP.KEYS_ROTATE,
    label: "Rotacionar chaves",
    description: "Criar, rotacionar e revogar chaves (não só visualizar).",
    icon: "autorenew",
  },
  {
    value: CAP.GLOBAL_KEYS,
    label: "Chaves globais",
    description: "a chave global possui acesso a todas as APIs habilitadas na conta. O comprometimento dessa credencial afeta todos os serviços simultaneamente. Adote o princípio do menor privilégio utilizando chaves dedicadas por API.",
    icon: "key_vertical",
  },
  {
    value: CAP.LOGS,
    label: "Acessar logs",
    description: "Ver os logs de requisições da conta.",
    icon: "receipt_long",
  },
  {
    value: CAP.METRICS,
    label: "Métricas",
    description: "Ver métricas agregadas (volume, latência, taxa de sucesso).",
    icon: "analytics",
  },
  {
    value: CAP.CLIENT_USAGE,
    label: "Uso por API/chave",
    description: "Ver o detalhamento de consumo por API e por chave.",
    icon: "insights",
  },
  {
    value: CAP.FINANCIAL,
    label: "Dados financeiros",
    description: "Ver custos e valores de faturamento.",
    icon: "account_balance_wallet",
  },
  {
    value: CAP.PROXIES,
    label: "Proxies",
    description: "Gerenciar os próprios proxies por API.",
    icon: "lan",
  },
  {
    value: CAP.CAPTCHA,
    label: "Captcha",
    description: "Gerenciar os próprios provedores de captcha por API.",
    icon: "verified_user",
  },
  {
    value: CAP.MEMBERS,
    label: "Gestão de usuários",
    description: "Criar, editar e excluir usuários e papéis da empresa (gerente de equipe).",
    icon: "group",
  },
];
