"""第 6 章核心方法：分级置信度路由 + 权威门槛（交叉验证）。

纯函数：不访问 DB / session；is_verified 由 search_similar_entities 前置进候选，
此处只读内存对象。不 mutate 入参，用 dataclasses.replace 返回新对象。
注意：DisambiguationResult 是 @dataclass（models.py），无 _replace 方法。
"""
from dataclasses import replace

from disambiguation.models import (
    DisambiguationResult,
    STATUS_AUTO_MATCHED,
    STATUS_CANDIDATE_MATCHED,
    STATUS_AMBIGUOUS,
)


def route_decision(result: DisambiguationResult) -> DisambiguationResult:
    """分级置信度路由 + 权威门槛（第 6 章核心方法）。

    判定表（全场景覆盖）：
      ① candidate_matched + top1 is_verified=True  → auto_matched（落锤）
      ② candidate_matched + top1 is_verified=False → ambiguous（占位待审）
      ③ candidate_matched + top1 is_verified=None  → ambiguous（保守待审）
      ④ ambiguous                                   → 原样返回
      ⑤ new_entity                                  → 原样返回
      ⑥ auto_matched（step1/step2 已落锤）          → 原样返回（不得二次处理）

    交叉验证语义：candidate_matched 已含 reranker≥τ_u(0.7)∧gap≥0.15（信号1），
    叠加 is_verified=True（信号2）= 双信号佐证才提交；信号2 缺失 → 降级 ambiguous 待审。
    """
    # ④⑤⑥：非 candidate_matched 一律原样返回（不二次处理）
    if result.status != STATUS_CANDIDATE_MATCHED:
        return result

    top1 = result.candidates[0] if result.candidates else None
    if top1 is None:
        # candidate_matched 但无候选是异常态，保守降级待审（宁可不判，不误判）
        return replace(
            result, dict_id=None, status=STATUS_AMBIGUOUS,
            reason="routing: candidate_matched without candidates → 待审",
        )

    # ① 双信号佐证：reranker≥τ_u 已隐含于 candidate_matched + is_verified=True
    if top1.is_verified is True:
        return replace(
            result,
            status=STATUS_AUTO_MATCHED,
            dict_id=result.dict_id,
            reason="routing: reranker≥τ_u(0.7)+is_verified (cross-validated)",
        )
    # ② is_verified=False（占位）→ 权威门槛拦截，降级待审
    if top1.is_verified is False:
        return replace(
            result, dict_id=None, status=STATUS_AMBIGUOUS,
            reason="authority gate: top1 is_verified=False → 待审",
        )
    # ③ is_verified 缺失（None）→ 保守同②，降级待审
    return replace(
        result, dict_id=None, status=STATUS_AMBIGUOUS,
        reason="authority gate: top1 is_verified missing → 待审",
    )
