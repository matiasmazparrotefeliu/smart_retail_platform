"""Tests unitarios del módulo TENANT: gestión de usuarios operativos.

Cubre (lógica pura, sin API HTTP):
- Reglas de roles operativos (analyst/viewer vs tenant_admin).
- Unicidad de email y herencia del client_id del admin.
- Aislamiento por tenant en updates.
- Reset de contraseña con hash verificable.
"""

from datetime import timedelta

import pytest

from src.core.datetime_utils import utc_now
from src.core.exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    ForbiddenActionError,
    InvalidRequestError,
)
from src.core.security import verify_password
from src.modules.auth.schemas import UserRegister
from src.modules.auth.service import AuthService
from src.modules.tenant.schemas import UserCreateTenant, UserResetPassword, UserUpdateTenant
from src.modules.tenant.service import TenantService


# ---------------------------------------------------------------------------
# Reglas de roles operativos
# ---------------------------------------------------------------------------
def test_operational_role_rules(db):
    """Solo analyst/viewer son válidos; tenant_admin está prohibido (403)."""
    service = TenantService(db)

    assert service._get_operational_role("analyst").name == "analyst"
    assert service._get_operational_role("viewer").name == "viewer"

    with pytest.raises(ForbiddenActionError) as admin_exc:
        service._get_operational_role("tenant_admin")
    assert admin_exc.value.status_code == 403

    with pytest.raises(InvalidRequestError) as ghost_exc:
        service._get_operational_role("ghost")
    assert ghost_exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Alta de usuarios operativos
# ---------------------------------------------------------------------------
def test_create_tenant_user_links_admin_client_and_blocks_duplicates(db):
    """El usuario operativo hereda el client_id del admin; email es único (409)."""
    admin = AuthService(db).register_company_and_admin(
        UserRegister(company_name="Corp Dup", email="admin@corp.com", password="Pwd12345!")
    )
    service = TenantService(db)

    created = service.create_tenant_user(
        admin.client_id,
        UserCreateTenant(email="dup@corp.com", password="Pwd12345!", role_name="analyst"),
    )
    assert created.client_id == admin.client_id
    assert created.is_verified is False
    assert created.role.name == "analyst"

    with pytest.raises(EntityAlreadyExistsError) as exc:
        service.create_tenant_user(
            admin.client_id,
            UserCreateTenant(email="dup@corp.com", password="Pwd12345!", role_name="viewer"),
        )
    assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# Aislamiento por tenant
# ---------------------------------------------------------------------------
def test_update_user_is_isolated_by_tenant(db):
    """Un admin no puede tocar usuarios de otra empresa (404)."""
    admin = AuthService(db).register_company_and_admin(
        UserRegister(company_name="Corp Iso", email="iso@corp.com", password="Pwd12345!")
    )
    service = TenantService(db)
    operator = service.create_tenant_user(
        admin.client_id,
        UserCreateTenant(email="isoop@corp.com", password="Pwd12345!", role_name="viewer"),
    )

    outsider = TenantService(db)
    with pytest.raises(EntityNotFoundError) as exc:
        outsider.update_tenant_user(
            admin_client_id=admin.client_id + 999,
            user_id=operator.id,
            data=UserUpdateTenant(is_active=False),
        )
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Reseteo de contraseña
# ---------------------------------------------------------------------------
def test_reset_password_replaces_hash(db):
    """El reset de contraseña actualiza el hash verificable."""
    admin = AuthService(db).register_company_and_admin(
        UserRegister(company_name="Corp Rst", email="rst@corp.com", password="Pwd12345!")
    )
    service = TenantService(db)
    operator = service.create_tenant_user(
        admin.client_id,
        UserCreateTenant(email="rstop@corp.com", password="Pwd12345!", role_name="analyst"),
    )

    service.reset_tenant_user_password(
        admin.client_id,
        operator.id,
        UserResetPassword(new_password="NuevaClave99!"),
    )

    db.refresh(operator)
    assert verify_password("NuevaClave99!", operator.hashed_password) is True
    assert verify_password("Pwd12345!", operator.hashed_password) is False


# ---------------------------------------------------------------------------
# Listado de usuarios del tenant
# ---------------------------------------------------------------------------
def test_list_tenant_users_scoped_to_admin_client(db):
    """El listado solo devuelve usuarios de la empresa del admin."""
    admin = AuthService(db).register_company_and_admin(
        UserRegister(company_name="Corp Lst", email="lst@corp.com", password="Pwd12345!")
    )
    service = TenantService(db)
    service.create_tenant_user(
        admin.client_id,
        UserCreateTenant(email="op1@corp.com", password="Pwd12345!", role_name="analyst"),
    )
    service.create_tenant_user(
        admin.client_id,
        UserCreateTenant(email="op2@corp.com", password="Pwd12345!", role_name="viewer"),
    )

    users = service.list_tenant_users(admin.client_id)
    emails = sorted(u.email for u in users)
    assert emails == ["lst@corp.com", "op1@corp.com", "op2@corp.com"]
