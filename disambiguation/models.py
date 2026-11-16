"""消歧结果数据模型。"""

from dataclasses import dataclass, field


@dataclass
class CandidateEntity:
    """来自 entity_dict 的候选匹配。"""
    dict_id: int
    name: str
    similarity_score: float = 0.0
    match_type: str = ""          # external_id | alias | normalized | rule | vector
    canonical_data: dict = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)
    is_verified: bool | None = None   # 权威状态（entity_dict.is_verified），None=未知


@dataclass
class DisambiguationResult:
    """单个实体的消歧结果。"""
    status: str                   # auto_matched | candidate_matched | new_entity | ambiguous
    dict_id: int | None = None
    confidence: float = 0.0       # 路由用置信度，单一来源 = reranker relevance_score
    llm_confidence: float = 0.0   # Step6 LLM 自我报告分（不进路由信号，仅内部决策/分析）
    matched_name: str = ""
    reason: str = ""
    candidates: list[CandidateEntity] = field(default_factory=list)
    match_step: str = ""          # 哪个阶段产出的结果


STATUS_AUTO_MATCHED = "auto_matched"
STATUS_CANDIDATE_MATCHED = "candidate_matched"
STATUS_NEW_ENTITY = "new_entity"
STATUS_AMBIGUOUS = "ambiguous"
