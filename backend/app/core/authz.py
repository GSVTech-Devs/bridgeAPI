"""Camada de autorização por feature (RBAC de dashboard).

Distinto das *permissions* do domínio (account → quais APIs externas pode
consumir no proxy). Aqui o conceito é: usuário → quais telas/recursos do
dashboard ele pode acessar.

Hoje as capabilities são derivadas apenas do ``role``. Quando a feature de
membros chegar, ``get_user_capabilities`` passa a mesclar grants por usuário
(ex.: tabela ``user_feature_grants``) sem precisar alterar as rotas — elas já
dependem de ``require_feature`` (ver app.domains.auth.router).
"""

from __future__ import annotations

from enum import Enum

from app.domains.auth.models import UserRole


class Feature(str, Enum):
    API_KEYS = "api_keys"
    CATALOG = "catalog"
    DOCS = "docs"
    LOGS = "logs"
    METRICS = "metrics"
    MEMBERS = "members"  # gestão de usuários da empresa pelo responsável (futuro)


# Conjunto de capabilities padrão por papel.
_ROLE_CAPABILITIES: dict[str, set[Feature]] = {
    UserRole.OWNER.value: {
        Feature.API_KEYS,
        Feature.CATALOG,
        Feature.DOCS,
        Feature.LOGS,
        Feature.METRICS,
        Feature.MEMBERS,
    },
    UserRole.MEMBER.value: {
        Feature.API_KEYS,
        Feature.CATALOG,
        Feature.DOCS,
        Feature.LOGS,
        Feature.METRICS,
    },
}


def get_user_capabilities(role: str) -> set[Feature]:
    """Capabilities de um usuário de account.

    Futuro: receber o usuário e mesclar overrides por membro.
    """
    return set(_ROLE_CAPABILITIES.get(role, set()))
