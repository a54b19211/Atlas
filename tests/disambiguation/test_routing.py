"""disambiguation.routing（第 6 章分级路由 + 权威门槛）的单元测试。

覆盖 route_decision 判定表 6 类 + 纯函数性（不 mutate 入参）+ 边界。
"""
from disambiguation.models import (
    DisambiguationResult,
    CandidateEntity,
    STATUS_AUTO_MATCHED,
    STATUS_CANDIDATE_MATCHED,
    STATUS_NEW_ENTITY,
    STATUS_AMBIGUOUS,
)
from disambiguation.routing import route_decision


def _cand(dict_id, is_verified):
    return CandidateEntity(dict_id=dict_id, name=f"候选{dict_id}", is_verified=is_verified)


class TestRouteDecision:
    # ① candidate_matched + is_verified=True → auto_matched 落锤
    def test_verified_candidate_matched_auto_linked(self):
        r = DisambiguationResult(
            status=STATUS_CANDIDATE_MATCHED, dict_id=7, confidence=0.9,
            candidates=[_cand(7, True), _cand(8, True)],
        )
        out = route_decision(r)
        assert out.status == STATUS_AUTO_MATCHED
        assert out.dict_id == 7
        assert "cross-validated" in out.reason

    # ② candidate_matched + is_verified=False → ambiguous 待审（不落锤）
    def test_unverified_candidate_matched_downgraded(self):
        r = DisambiguationResult(
            status=STATUS_CANDIDATE_MATCHED, dict_id=7, confidence=0.9,
            candidates=[_cand(7, False)],
        )
        out = route_decision(r)
        assert out.status == STATUS_AMBIGUOUS
        assert out.dict_id is None
        assert "is_verified=False" in out.reason

    # ③ candidate_matched + is_verified=None（缺失）→ 保守 ambiguous 待审
    def test_missing_verified_candidate_matched_downgraded(self):
        r = DisambiguationResult(
            status=STATUS_CANDIDATE_MATCHED, dict_id=7, confidence=0.9,
            candidates=[_cand(7, None)],
        )
        out = route_decision(r)
        assert out.status == STATUS_AMBIGUOUS
        assert out.dict_id is None
        assert "missing" in out.reason

    # ④ ambiguous 原样返回
    def test_ambiguous_unchanged(self):
        r = DisambiguationResult(status=STATUS_AMBIGUOUS, confidence=0.6,
                                 candidates=[_cand(1, True)])
        assert route_decision(r) is r

    # ⑤ new_entity 原样返回
    def test_new_entity_unchanged(self):
        r = DisambiguationResult(status=STATUS_NEW_ENTITY, confidence=0.0)
        assert route_decision(r) is r

    # ⑥ auto_matched（step1/step2 已落锤）原样返回，不得二次处理
    def test_auto_matched_unchanged(self):
        r = DisambiguationResult(status=STATUS_AUTO_MATCHED, dict_id=42, confidence=0.95,
                                 match_step="step2_exact_alias")
        assert route_decision(r) is r

    # candidate_matched 但无候选（异常态）→ 保守降级待审
    def test_candidate_matched_without_candidates(self):
        r = DisambiguationResult(status=STATUS_CANDIDATE_MATCHED, dict_id=7, confidence=0.9)
        out = route_decision(r)
        assert out.status == STATUS_AMBIGUOUS
        assert out.dict_id is None

    # 门槛只看 top1：top1 未验证、top2 已验证 → 仍降级
    def test_only_top1_checked(self):
        r = DisambiguationResult(
            status=STATUS_CANDIDATE_MATCHED, dict_id=7, confidence=0.9,
            candidates=[_cand(7, False), _cand(8, True)],
        )
        out = route_decision(r)
        assert out.status == STATUS_AMBIGUOUS


class TestPureFunction:
    # 纯函数性：调用前后原 result 对象字段不变（不 mutate 入参）
    def test_input_not_mutated(self):
        r = DisambiguationResult(
            status=STATUS_CANDIDATE_MATCHED, dict_id=7, confidence=0.9,
            reason="original", candidates=[_cand(7, True)],
        )
        out = route_decision(r)
        assert out is not r                     # 返回新对象
        assert r.status == STATUS_CANDIDATE_MATCHED  # 原对象不变
        assert r.dict_id == 7
        assert r.reason == "original"
        assert r.candidates[0].is_verified is True
