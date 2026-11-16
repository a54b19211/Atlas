"""拉取的管理接口（全部要管理员口令，见 api/admin_auth.py）：白名单、质量门槛、拉取状态和开关、按需请求。"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from api.admin_auth import require_admin
from pull import fabric, service, store

router = APIRouter(prefix="/api/pull", tags=["pull"])


class WhitelistIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(min_length=1, max_length=100)
    doc_type: str = Field(default="", max_length=100)  # 空 = 这个来源的所有类型
    enabled: bool = True
    note: str = Field(default="", max_length=500)


class WhitelistPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doc_type: str | None = Field(default=None, max_length=100)
    enabled: bool | None = None
    note: str | None = Field(default=None, max_length=500)


class QualityIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min_level: Literal["", "低", "中", "高"] | None = None
    skip_quarantine: bool | None = None
    allow_unscored: bool | None = None


class ScheduleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interval_seconds: int = Field(ge=10, le=7 * 86400)


class PullRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(min_length=1, max_length=100)
    version_ids: list[str] = Field(min_length=1, max_length=100)
    force: bool = False  # true：连质量门槛也绕过


# ── 白名单 ────────────────────────────────────────────────────────────
@router.get("/whitelist")
def list_whitelist(_: str = Depends(require_admin)):
    return {"items": store.list_whitelist()}


@router.post("/whitelist")
def add_whitelist(body: WhitelistIn, actor: str = Depends(require_admin)):
    return store.add_whitelist(body.model_dump(), actor)


@router.patch("/whitelist/{row_id}")
def update_whitelist(row_id: int, body: WhitelistPatch, actor: str = Depends(require_admin)):
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(422, "没有要改的字段")
    row = store.update_whitelist(row_id, changes, actor)
    if row is None:
        raise HTTPException(404, "没有这条规则")
    return row


@router.delete("/whitelist/{row_id}")
def delete_whitelist(row_id: int, actor: str = Depends(require_admin)):
    if not store.delete_whitelist(row_id, actor):
        raise HTTPException(404, "没有这条规则")
    return {"deleted": row_id}


# ── 质量门槛 ──────────────────────────────────────────────────────────
@router.get("/quality-gate")
def get_quality_gate(_: str = Depends(require_admin)):
    return store.quality_gate()


@router.put("/quality-gate")
def set_quality_gate(body: QualityIn, actor: str = Depends(require_admin)):
    changes = {f"quality.{k}": v for k, v in body.model_dump(exclude_none=True).items()}
    if changes:
        store.set_settings(changes, actor)
    return store.quality_gate()


# ── 拉取状态和开关 ─────────────────────────────────────────────────────
@router.get("/status")
def status(_: str = Depends(require_admin)):
    """每来源：拉到的序号、fabric 最新序号（上一页看到的）、积压、跳过数、上轮起止、上次错误；以及服务开关。"""
    s = store.get_settings("pull.")
    return {"paused": s["pull.paused"], "run_now": s["pull.run_now"], "interval_seconds": s["pull.interval_seconds"],
            "sources": store.list_state()}


@router.post("/pause")
def pause(actor: str = Depends(require_admin)):
    store.set_settings({"pull.paused": True}, actor)
    return {"paused": True}


@router.post("/resume")
def resume(actor: str = Depends(require_admin)):
    store.set_settings({"pull.paused": False}, actor)
    return {"paused": False}


@router.post("/run-now")
def run_now(actor: str = Depends(require_admin)):
    """服务下一次醒来（几秒内）就跑一轮，暂停中也跑这一轮。"""
    store.set_settings({"pull.run_now": True}, actor)
    return {"run_now": True}


@router.put("/schedule")
def set_schedule(body: ScheduleIn, actor: str = Depends(require_admin)):
    store.set_settings({"pull.interval_seconds": body.interval_seconds}, actor)
    return {"interval_seconds": body.interval_seconds}


# ── 按需请求 ──────────────────────────────────────────────────────────
@router.post("/request")
def request_versions(body: PullRequestIn, actor: str = Depends(require_admin)):
    """按 fabric 版本号拉进来并标成待抽取：绕过白名单，仍过质量门槛（force=true 绕过）。给雷达和人工用。"""
    gate = store.quality_gate()
    with service.fabric_client() as client:
        rows, skipped, missing = fabric.request_versions(client, body.source_id, body.version_ids, gate, body.force)
    store.save_page(body.source_id, rows, None, skipped, None)
    store.mark_pending([r["uuid"] for r in rows])
    with store._session() as s:
        store.log_change(s, actor, "pull.request", {"source_id": body.source_id, "count": len(body.version_ids),
                                                     "accepted": len(rows), "force": body.force})
    return {"accepted": [{"version_id": r["fabric_version_id"], "document_uuid": r["uuid"]} for r in rows],
            "skipped_quality": skipped["quality"], "missing": missing}
