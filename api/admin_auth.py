"""管理员口令：Authorization: Bearer $ATLAS_ADMIN_TOKEN。没配口令时管理接口一律拒绝。
X-Admin-User 头写操作人（记进 atlas_admin_log），不给就记 admin。"""
import hmac

from fastapi import Header, HTTPException

from config.settings import APP


def require_admin(authorization: str = Header(default=""), x_admin_user: str = Header(default="admin")) -> str:
    token = APP.ATLAS_ADMIN_TOKEN
    if not token:
        raise HTTPException(503, "没有配置 ATLAS_ADMIN_TOKEN，管理接口不可用")
    if not hmac.compare_digest(authorization.encode(), f"Bearer {token}".encode()):
        raise HTTPException(401, "管理员口令不对")
    return (x_admin_user or "admin")[:100]
