"""角色權限對照（RBAC）。"""
from enum import Enum

from app.models.user import UserRole


class Perm(str, Enum):
    RECORD_READ = "record:read"
    RECORD_CREATE = "record:create"
    RECORD_IMPORT = "record:import"
    RECORD_UPDATE_OWN = "record:update_own"
    RECORD_UPDATE_ANY = "record:update_any"
    RECORD_DELETE_OWN = "record:delete_own"
    RECORD_DELETE_ANY = "record:delete_any"
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_EXPORT = "analytics:export"
    REALTIME_READ = "realtime:read"
    REALTIME_CONTROL = "realtime:control"
    REALTIME_HISTORY = "realtime:history"
    THRESHOLD_MANAGE = "threshold:manage"
    USER_MANAGE = "user:manage"
    LOG_READ = "log:read"
    SYSTEM_STATUS = "system:status"


_VIEWER = {Perm.RECORD_READ, Perm.ANALYTICS_READ, Perm.ANALYTICS_EXPORT, Perm.REALTIME_READ}
_USER = _VIEWER | {Perm.RECORD_CREATE, Perm.RECORD_IMPORT, Perm.RECORD_UPDATE_OWN, Perm.RECORD_DELETE_OWN}
_ADMIN = set(Perm)

ROLE_PERMISSIONS: dict[UserRole, set[Perm]] = {
    UserRole.VIEWER: _VIEWER,
    UserRole.USER: _USER,
    UserRole.ADMIN: _ADMIN,
}


def has_perm(role: UserRole, perm: Perm) -> bool:
    return perm in ROLE_PERMISSIONS.get(role, set())
