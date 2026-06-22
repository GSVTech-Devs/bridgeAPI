"""Camada de autorização por feature (RBAC de dashboard).

Distinto das *permissions* do domínio (account → quais APIs externas pode
consumir no proxy). Aqui o conceito é: usuário → quais telas/recursos do
dashboard ele pode acessar.

A resolução das capabilities de um usuário acontece em
``app.domains.members.service.resolve_user_capabilities`` (precisa do banco para
ler a role do membro). Este módulo é puro: define o enum de features e os
conjuntos de referência (owner = tudo, baseline do membro, atribuíveis a roles).
"""

from __future__ import annotations

from enum import Enum

from app.domains.auth.models import UserRole


class Feature(str, Enum):
    API_KEYS = "api_keys"  # ver chaves de API
    KEYS_ROTATE = "keys_rotate"  # criar/rotacionar/revogar chaves
    CATALOG = "catalog"
    DOCS = "docs"
    LOGS = "logs"
    METRICS = "metrics"  # dashboard de métricas agregadas
    CLIENT_USAGE = "client_usage"  # detalhamento por API/chave da conta
    FINANCIAL = "financial"  # dados de custo/financeiros
    MEMBERS = "members"  # gestão de usuários da empresa pelo responsável


# Todas as features de dashboard — o responsável (owner) tem acesso total.
OWNER_FEATURES: set[Feature] = set(Feature)

# Features que o owner pode ligar/desligar por role de membro (toggles).
# ``MEMBERS`` (gestão de usuários) e ``CATALOG``/``DOCS`` (baseline) ficam de fora.
ASSIGNABLE_FEATURES: set[Feature] = {
    Feature.API_KEYS,
    Feature.KEYS_ROTATE,
    Feature.LOGS,
    Feature.METRICS,
    Feature.CLIENT_USAGE,
    Feature.FINANCIAL,
}

# Features que todo membro de account tem por padrão, independente da role.
BASELINE_MEMBER_FEATURES: set[Feature] = {Feature.CATALOG, Feature.DOCS}


def get_user_capabilities(role: str) -> set[Feature]:
    """Capabilities derivadas apenas do papel (sem ler a role do membro).

    - ``owner`` → todas as features.
    - ``member`` → apenas o baseline (as features atribuíveis vêm da role,
      mescladas em ``resolve_user_capabilities``).
    - demais → nenhuma.
    """
    if role == UserRole.OWNER.value:
        return set(OWNER_FEATURES)
    if role == UserRole.MEMBER.value:
        return set(BASELINE_MEMBER_FEATURES)
    return set()
