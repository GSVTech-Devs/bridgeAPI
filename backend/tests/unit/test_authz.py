# Testes para a camada de capabilities (RBAC de dashboard) — app/core/authz.py.
from app.core.authz import Feature, get_user_capabilities
from app.domains.auth.models import UserRole


def test_owner_has_all_features() -> None:
    caps = get_user_capabilities(UserRole.OWNER.value)
    assert Feature.API_KEYS in caps
    assert Feature.CATALOG in caps
    assert Feature.LOGS in caps
    assert Feature.METRICS in caps
    assert Feature.MEMBERS in caps


def test_member_lacks_members_feature() -> None:
    caps = get_user_capabilities(UserRole.MEMBER.value)
    # membro vê os recursos operacionais...
    assert Feature.API_KEYS in caps
    assert Feature.LOGS in caps
    # ...mas não gerencia outros usuários
    assert Feature.MEMBERS not in caps


def test_admin_role_has_no_account_capabilities() -> None:
    # admin da plataforma não usa o dashboard de account
    assert get_user_capabilities(UserRole.ADMIN.value) == set()


def test_unknown_role_has_no_capabilities() -> None:
    assert get_user_capabilities("whatever") == set()
