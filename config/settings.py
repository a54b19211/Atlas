"""
Atlas 配置 —— 用 pydantic-settings 从 .env 文件 / 环境变量读取（模板见 .env.example）。
其他模块只需 `from config.settings import APP`。这里只列 Atlas 用到的变量。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class _AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",            # 忽略 .env 中多余的变量，不报错
    )

    # ======================== LLM（OpenAI 兼容协议）========================
    LLM_API_KEY: str = ""
    LLM_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    LLM_MODEL_NAME: str = "qwen-plus"

    # 实体抽取专用模型（可选，留空则复用 LLM_*）
    EXTRACTION_LLM_API_KEY: str = ""
    EXTRACTION_LLM_API_BASE: str = ""
    EXTRACTION_LLM_MODEL_NAME: str = ""

    # 消歧精排专用模型（可选，留空则复用 LLM_*）
    RERANK_LLM_API_KEY: str = ""
    RERANK_LLM_API_BASE: str = ""
    RERANK_LLM_MODEL_NAME: str = ""

    # Embedding（消歧向量检索用；维度要和库里 vector 列一致）
    EMBEDDING_API_KEY: str = ""          # 留空则复用 LLM_API_KEY
    EMBEDDING_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_MODEL_NAME: str = "text-embedding-v3"
    EMBEDDING_DIMENSIONS: int = 1024

    @property
    def EMBEDDING_KEY(self) -> str:
        return self.EMBEDDING_API_KEY or self.LLM_API_KEY

    @property
    def RERANK_API_KEY(self) -> str:
        return self.RERANK_LLM_API_KEY or self.LLM_API_KEY

    @property
    def RERANK_API_BASE(self) -> str:
        return self.RERANK_LLM_API_BASE or self.LLM_API_BASE

    @property
    def RERANK_MODEL_NAME(self) -> str:
        return self.RERANK_LLM_MODEL_NAME or self.LLM_MODEL_NAME

    @property
    def EXTRACTION_API_KEY(self) -> str:
        return self.EXTRACTION_LLM_API_KEY or self.LLM_API_KEY

    @property
    def EXTRACTION_API_BASE(self) -> str:
        return self.EXTRACTION_LLM_API_BASE or self.LLM_API_BASE

    @property
    def EXTRACTION_MODEL_NAME(self) -> str:
        return self.EXTRACTION_LLM_MODEL_NAME or self.LLM_MODEL_NAME

    # ======================== 抽取任务队列 ========================
    EXTRACTION_CONCURRENCY: int = 3         # 并行抽取的文档数
    TASK_QUEUE_BACKEND: str = "memory"      # "memory" | "redis"
    REDIS_URL: str = "redis://localhost:6379/0"

    # ======================== Atlas 自己的 PostgreSQL ========================
    DB_HOST: str = ""
    DB_PORT: int = 5432
    DB_NAME: str = ""
    DB_USER: str = ""
    DB_PASSWORD: str = ""
    DB_POOL_SIZE: int = 20

    @property
    def DB_URL(self) -> str:
        """SQLAlchemy 连接串，未配置时返回空字符串。"""
        if not self.DB_HOST or not self.DB_NAME:
            return ""
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # ======================== WeKnora（图谱同步到它的 Neo4j）========================
    WEKNORA_BASE_URL: str = "http://localhost:8080"
    WEKNORA_API_KEY: str = ""
    WEKNORA_KB_ID: str = ""

    # ======================== 资料库 fabric（文档来源，只读）========================
    FABRIC_API_URL: str = "http://127.0.0.1:8000"
    FABRIC_READ_TOKEN: str = ""
    FABRIC_SOURCES: str = ""                # 逗号分隔的来源；留空则拉 /api/fabric/sources 里全部可读来源


# 全局单例——整个项目统一用这个
APP = _AppSettings()
