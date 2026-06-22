# Testes para a camada de capabilities (RBAC de dashboard) — app/core/authz.py.
from app.core.authz import (
    ASSIGNABLE_FEATURES,
    BASELINE_MEMBER_FEATURES,
    Feature,
    get_user_capabilities,
)
from app.domains.auth.models import UserRole


def test_owner_has_all_features() -> None:
    caps = get_user_capabilities(UserRole.OWNER.value)
    assert Feature.API_KEYS in caps
    assert Feature.CATALOG in caps
    assert Feature.LOGS in caps
    assert Feature.METRICS in caps
    assert Feature.MEMBERS in caps
    assert Feature.FINANCIAL in caps


def test_member_role_returns_only_baseline() -> None:
    # As features atribuíveis (api_keys, logs, …) vêm da role do membro e são
    # mescladas em resolve_user_capabilities — não aqui.
    caps = get_user_capabilities(UserRole.MEMBER.value)
    assert caps == set(BASELINE_MEMBER_FEATURES)
    assert Feature.CATALOG in caps
    assert Feature.API_KEYS not in caps
    assert Feature.MEMBERS not in caps


def test_admin_role_has_no_account_capabilities() -> None:
    # admin da plataforma não usa o dashboard de account
    assert get_user_capabilities(UserRole.ADMIN.value) == set()


def test_unknown_role_has_no_capabilities() -> None:
    assert get_user_capabilities("whatever") == set()


def test_members_and_catalog_are_not_assignable() -> None:
    # Toggles de role nunca incluem gestão de usuários nem o baseline.
    assert Feature.MEMBERS not in ASSIGNABLE_FEATURES
    assert Feature.CATALOG not in ASSIGNABLE_FEATURES
    # Mas as features operacionais são atribuíveis.
    assert Feature.API_KEYS in ASSIGNABLE_FEATURES
    assert Feature.KEYS_ROTATE in ASSIGNABLE_FEATURES
    assert Feature.FINANCIAL in ASSIGNABLE_FEATURES
