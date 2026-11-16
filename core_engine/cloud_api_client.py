"""
API 客户端 —— 封装 LLM（结构化抽取、对话）和 Embedding 的请求逻辑。
"""

import json
import tempfile

from openai import OpenAI
from loguru import logger


def _format_json_error(raw: str, exc: json.JSONDecodeError) -> str:
    """生成 JSON 解析错误的详细诊断信息，定位到出错位置附近。"""
    pos = exc.pos
    start = max(0, pos - 200)
    end = min(len(raw), pos + 200)
    snippet = raw[start:end]
    pointer = " " * (pos - start) + "^-- HERE"

    # 计算出错位置的行号（基于原字符串）
    before = raw[:pos]
    line_num = before.count("\n") + 1
    last_nl = before.rfind("\n")
    col_num = pos - (last_nl + 1) if last_nl >= 0 else pos

    lines = [
        f"JSON 解析失败: {exc.msg}",
        f"位置: 第 {line_num} 行, 第 {col_num} 列 (char {pos})",
        f"上下文:",
        f"```json",
        f"{snippet}",
        f"{pointer}",
        f"```",
    ]
    return "\n".join(lines)


def _strip_json_fence(raw: str) -> str:
    """剥离 LLM 输出中可能包裹的 ```json ... ``` 围栏。"""
    s = raw.strip()
    if s.startswith("```json"):
        s = s[7:]
    elif s.startswith("```"):
        s = s[3:]
    if s.endswith("```"):
        s = s[:-3]
    return s.strip()

from config.settings import APP


# ===================================================================
#  Qwen 大模型 API —— Markdown → 结构化 JSON
# ===================================================================

def _build_qwen_client() -> OpenAI:
    """构建兼容 OpenAI 协议的 LLM 客户端（爬虫阶段元数据提取用）。"""
    return OpenAI(
        api_key=APP.LLM_API_KEY,
        base_url=APP.LLM_API_BASE,
    )


def _build_extraction_client() -> OpenAI:
    """构建实体抽取专用 LLM 客户端（可配置独立模型）。"""
    return OpenAI(
        api_key=APP.EXTRACTION_API_KEY,
        base_url=APP.EXTRACTION_API_BASE,
    )


def qwen_extract_structured(
    prompt: str,
    system_prompt: str = "",
    use_extraction_model: bool = False,
    stream: bool = False,
) -> dict:
    """
    调用 LLM 进行结构化信息提取（OpenAI 兼容协议）。

    参数:
        prompt:               完整 user prompt
        system_prompt:        自定义 system prompt，为空时使用默认值
        use_extraction_model: True 时使用 EXTRACTION_* 配置的模型
        stream:               True 时开启流式输出，token 实时打印到终端

    返回:
        dict: 解析后的 JSON，失败时返回空 dict
    """
    api_key = APP.EXTRACTION_API_KEY if use_extraction_model else APP.LLM_API_KEY
    model_name = APP.EXTRACTION_MODEL_NAME if use_extraction_model else APP.LLM_MODEL_NAME

    if not api_key:
        logger.error("LLM API Key 未配置（LLM_API_KEY），跳过结构化提取")
        return {}

    default_system = "你是专业的医药文档信息提取助手。直接输出纯 JSON 文本（以 { 开头），禁止用 ```json 代码块包裹，禁止添加任何解释或额外文字。"
    messages = [
        {"role": "system", "content": system_prompt or default_system},
        {"role": "user", "content": prompt},
    ]

    try:
        client = _build_extraction_client() if use_extraction_model else _build_qwen_client()

        if stream:
            return _stream_extract(client, model_name, messages)
        else:
            return _batch_extract(client, model_name, messages)

    except Exception as e:
        logger.error(f"LLM API 调用异常: {e}")
        return {}


def _batch_extract(client: OpenAI, model_name: str, messages: list) -> dict:
    """非流式调用，等待完整响应后返回。"""
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        raw_content = _strip_json_fence(response.choices[0].message.content)
        result = json.loads(raw_content)
        logger.info(f"LLM 提取成功，模型={model_name}，字段数={len(result)}")
        return result
    except json.JSONDecodeError as e:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        tmp.write(raw_content)
        tmp.close()
        logger.error(f"LLM 返回内容非合法 JSON\n{_format_json_error(raw_content, e)}\n完整内容(原始): {tmp.name}")
        return {}


def _stream_extract(client: OpenAI, model_name: str, messages: list) -> dict:
    """
    流式调用，token 实时打印到终端，完成后解析完整 JSON 返回。
    适合命令行调试时观察 LLM 实时输出。
    """
    import sys
    print(f"\n[LLM 流式输出] 模型={model_name}", flush=True)
    print("-" * 60, flush=True)

    full_content = ""
    try:
        stream = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.1,
            stream=True,
            # 注意：部分模型流式模式不支持 response_format，去掉该参数
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            token = getattr(delta, "content", "") or ""
            if token:
                print(token, end="", flush=True)
                full_content += token

        print("\n" + "-" * 60, flush=True)
        logger.info(f"[LLM] 流式输出完成，总长度={len(full_content)}")

        # 解析完整 JSON（先剥离可能的围栏）
        clean_content = _strip_json_fence(full_content)
        result = json.loads(clean_content)
        logger.info(f"LLM 提取成功，模型={model_name}，字段数={len(result)}")
        return result

    except json.JSONDecodeError as e:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        tmp.write(full_content)
        tmp.close()
        logger.error(f"LLM 流式输出非合法 JSON\n{_format_json_error(clean_content, e)}\n完整内容(原始): {tmp.name}")
        return {}
    except Exception as e:
        logger.error(f"LLM 流式调用异常: {e}")
        return {}


# ===================================================================
#  Embedding API —— 文本 → 向量（消歧向量检索用）
# ===================================================================

def generate_embedding(text: str) -> list[float] | None:
    """
    调用 DashScope text-embedding-v3 API（OpenAI 兼容 /embeddings 端点）。
    返回维度 = APP.EMBEDDING_DIMENSIONS 的 float 列表，失败返回 None。
    """
    api_key = APP.EMBEDDING_KEY
    if not api_key:
        logger.error("Embedding API Key 未配置，跳过 embedding 生成")
        return None

    try:
        client = OpenAI(api_key=api_key, base_url=APP.EMBEDDING_API_BASE)
        response = client.embeddings.create(
            model=APP.EMBEDDING_MODEL_NAME,
            input=text,
            dimensions=APP.EMBEDDING_DIMENSIONS,
        )
        embedding = response.data[0].embedding
        logger.debug(f"[Embedding] 生成成功, dims={len(embedding)}")
        return embedding
    except Exception as e:
        logger.error(f"[Embedding] 生成失败: {e}")
        return None


def qwen_chat(
    system_prompt: str = "",
    user_message: str = "",
    temperature: float = 0.0,
    max_tokens: int = 500,
) -> str:
    """
    轻量 LLM 对话，用于消歧 LLM 兜底等非结构化场景。
    返回 LLM 文本回复，失败返回空字符串。
    """
    if not APP.LLM_API_KEY:
        logger.error("LLM API Key 未配置")
        return ""
    try:
        client = OpenAI(api_key=APP.LLM_API_KEY, base_url=APP.LLM_API_BASE)
        response = client.chat.completions.create(
            model=APP.LLM_MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt or ""},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"qwen_chat 调用失败: {e}")
        return ""


def build_embedding_text(
    entity_name: str,
    entity_type: str,
    entity_data: dict | None = None,
) -> str:
    """
    构造用于 embedding 的文本，组合实体类型、名称、别名和关键 ID 字段。
    不只用名称，避免 PD-1 和 PD-L1 向量相近但非同实体的误判。
    """
    parts = [f"实体类型: {entity_type}", f"名称: {entity_name}"]

    if entity_data:
        name_en = entity_data.get("name_en") or entity_data.get("name")
        if name_en and name_en != entity_name:
            parts.append(f"英文名: {name_en}")

        aliases = entity_data.get("aliases") or []
        if aliases:
            parts.append(f"别名: {', '.join(str(a) for a in aliases[:5])}")

        key_fields_map = {
            "Company":       ["stock_code"],
            "Drug":          ["cas_number"],
            "Target":        ["gene_symbol"],
            "ClinicalTrial": ["trial_id"],
            "Compound":      ["cas_number"],
            "Policy":        ["doc_number"],
            "Pathway":       [],
        }
        for f in key_fields_map.get(entity_type, []):
            val = entity_data.get(f)
            if val:
                parts.append(f"{f}={val}")

    return "\n".join(parts)
