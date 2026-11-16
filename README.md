# Atlas —— 医药知识图谱

Atlas 把资料库（fabric）里洗好的文档变成一张审核过的知识图谱：
用大模型从文档里抽实体和关系，和已有实体对上号（消歧），人和 Agent 审核，审核通过的再同步到 WeKnora 的 Neo4j。

Atlas 只**读** fabric，不往 fabric 写任何东西。采集、清洗、存档都是 fabric 的事。
底子是唐的图谱代码（含分级置信度路由 `disambiguation/routing.py`），从旧的大一统仓库里拆出来。

## 几个部分

| 目录 / 文件 | 做什么 |
|---|---|
| `pull/` | 常驻服务：从 fabric 拉文档到 `documents` 表（本地缓存），过白名单和质量门槛；管理接口 `api/routers/pull.py` |
| `ops/` | 部署样例（systemd 单元 `atlas-pull.service`） |
| `flows/` | 抽取：分块 `chunking.py`、提示词 `extraction_prompts.py`、实体类型 `entity_schemas.py`、流程 `extraction_flow.py`、任务队列 `extraction_worker.py` / `extraction_rq_job.py` |
| `disambiguation/` | 消歧：强 ID → 别名 → 类型规则 → 向量召回 → Reranker 精排 → 分级路由 |
| `db/` | 表结构 `models.py`、所有读写 `repository.py`、Agent 运行记录 `agent_run_repo.py`、审核计数监听 `review_listeners.py` |
| `core_engine/` | 大模型和 Embedding 调用 `cloud_api_client.py`、Agent `agents/` + `agent_runner.py`、WeKnora 图同步 `weknora_graph_client.py`、抽取队列 `task_queue.py` |
| `api/` | 后端接口（FastAPI）：文档、抽取、审核、Agent、WeKnora |
| `frontend/` | 审核页面（Vue 3 + Element Plus） |
| `migration/` | 建表迁移 `python -m migration.migrate` |
| `docs/` | 代码地图、实体类型定义 |

## 一条文档怎么走

```
fabric /api/fabric/changes + /clean-text
  → pull/ 过两道关（来源/类型白名单、质量门槛）后写 documents（extraction_status=pending）
  → 触发抽取（页面或 POST /api/extraction/trigger/pending）
  → 分块 → 大模型抽实体/关系 → 校验 → 消歧 → 写 extracted_entities / entity_relations
  → 人工或 Agent 审核（通过的进实体字典 entity_dict，字段冲突进 entity_merge_queue）
  → 同步到 WeKnora 的 Neo4j（页面“Neo4j”或 /api/weknora/graph/sync-all）
```

消歧的几步（`disambiguation/engine.py`）：强 ID（股票代码、CAS、试验号等）和别名精确匹配直接链接；
类型规则、向量召回 + Reranker 只给候选；最后 `routing.py` 按置信度和“已核实”标记分流：高的自动链接，中间的给人看，低的当新实体。

## 怎么装

要 Python 3.12、Node 18+、PostgreSQL（带 pgvector 扩展）；用 Redis 队列时还要 Redis。

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env            # 填库、fabric、大模型、WeKnora 的地址和密钥
.venv/bin/python -m migration.migrate      # 建表（--list 看状态）
cd frontend && npm install
```

## 怎么跑

```bash
.venv/bin/python -m pull.service               # 拉取常驻服务（--once 只跑一轮；部署用 ops/atlas-pull.service）
.venv/bin/uvicorn api.main:app --port 8100      # 后端
cd frontend && npm run dev                      # 页面 http://localhost:5174（代理到 8100）
```

抽取队列默认 `TASK_QUEUE_BACKEND=memory`（在后端进程里跑，重启丢任务）。
改成 `redis` 后要另起 worker：`rq worker extraction --url $REDIS_URL`。
后端重启不会清队列、不会重置在途任务；暂停/恢复抽取看 `/api/extraction/pause`、`/resume`。

跑测试：`.venv/bin/python -m pytest`（全是假库假模型，不连任何服务）。

## 从 fabric 读什么

只用 fabric 的公开读接口，凭据放 `Authorization: Bearer $FABRIC_READ_TOKEN`：

- `GET /api/fabric/changes?source_id=&is_demo=false&after=<序号>&limit=100`：某来源在序号之后新存的版本，按序号翻页。
- `GET /api/fabric/clean-text?source_id=&is_demo=false&mode=current&cutoff=<时间>&quality=true&version_ids=...`：清洗正文、画像和质量分。
- `GET /api/fabric/versions/{version_id}`：按需请求时取单个版本。

写进 `documents` 的字段：

| documents | 来自 fabric |
|---|---|
| `uuid` | 由 `来源 + 记录号` 算出的固定 uuid（同一条记录的新版本覆盖旧的） |
| `fabric_version_id` | 版本号 `version_id` |
| `raw_content` | 清洗正文 `clean.text`；还没洗好就用版本自带的 `clean_text` |
| `title` / `source_url` | 同名字段 |
| `source_site` | `source_id` |
| `publish_date` | `source_published_at.value`，没有就 `event_time.value` |
| `doc_type` / `category` | 画像的 `doc_type` / `doc_category`；没画像时 `doc_type` 用 `record_kind` |
| `language` | `clean.language` |
| `crawl_timestamp` | `first_seen_at` |

白名单在 `atlas_pull_whitelist`，质量门槛、间隔、暂停在 `atlas_settings`，都用 `/api/pull/*` 管理接口改（`Authorization: Bearer $ATLAS_ADMIN_TOKEN`，改动记进 `atlas_admin_log`）；
`POST /api/pull/request` 按版本号拉进来（绕过白名单），给雷达和人工用。
拉到哪个序号记在 `fabric_pull_state` 表，一页文档和序号在同一个事务里写，中途断了下次接着拉。
正文变了的文档会把 `extraction_status` 改回 `pending` 等重新抽取（旧的抽取结果保留，和“重新抽取”按钮一样）。

## 注意

- 来源权威度和合并优先级（`core_engine/agent_config.py`、`db/repository.py` 的 `_SOURCE_PRIORITY`）是按旧站点名写的，
  fabric 的 `source_id` 和旧名不一样的地方要对一下。
- `.env` 有密钥，不要提交。
