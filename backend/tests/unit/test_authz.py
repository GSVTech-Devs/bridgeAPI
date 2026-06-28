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


def test_members_is_assignable_but_catalog_is_not() -> None:
    # MEMBERS é atribuível: o owner pode delegar gestão de usuários a uma role.
    assert Feature.MEMBERS in ASSIGNABLE_FEATURES
    # O baseline (CATALOG/DOCS) nunca é toggle de role.
    assert Feature.CATALOG not in ASSIGNABLE_FEATURES
    # E as features operacionais seguem atribuíveis.
    assert Feature.API_KEYS in ASSIGNABLE_FEATURES
    assert Feature.KEYS_ROTATE in ASSIGNABLE_FEATURES
    assert Feature.FINANCIAL in ASSIGNABLE_FEATURES
