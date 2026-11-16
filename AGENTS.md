# AGENTS.md — 代码库协作与文件权限契约

> **本文件是本仓库唯一的权威协作契约**，同时供人与 AI 编程助手（Cursor / Claude Code / Codex / GitHub Copilot 等）读取。
>
> **给 AI 助手的强制约束**：改动任何文件前，先在 §2–§4 的权限矩阵中定位该文件归属。
> - 命中「**禁止**」→ 一律不得修改，需向用户说明该文件归对方维护。
> - 命中「**只读**」→ 可 import / 调用，不得修改。
> - 命中「**需告知**」→ 修改前必须先向用户确认，说明影响面。
>
> **状态**：定稿（2026-11-03，经与上游同门逐项确认）
> **本侧仓**：`wtang5407-source/ZKdata-disamb-rev`（Private）｜**上游原仓**：`CPU-ZK-TEAM/ZK_Data-Fabric-test`
> **合并来源**：《项目架构整理方案》《代码库划分方案》《文件权限矩阵》三份草案（已并入本文件）

---

## 0. 双方角色与职责边界

| 角色 | 成员 | 负责范围 |
|---|---|---|
| **上游侧** | 同门（爬虫/清洗） | 爬虫 → 清洗 → 字段映射 → 文档落库 |
| **本侧** | WWTang | LLM 抽取 → 实体消歧 → 审核 → 图同步 → 前端 |
| **共享** | 双方 + 成员2 | DB Schema / 数据访问层 / 工程配置 / 审核 API / 前端 |

**切割线**：定在「**文档落库**」与「**LLM 抽取**」之间——两侧代码重叠最少、职责最清晰。

```
上游：爬虫 → 清洗/字段映射 → 写 collected_document（文档表）
  ─────────── 交接契约：共享同一 Postgres + 同一份 Schema ───────────
本侧：读文档 → LLM 抽取 → 实体消歧 → 写 extracted_entities / entity_dict
```

- 上游交付物 =「清洗后的文档」（`collected_document`）
- 本侧交付物 =「消歧后的实体」（`entity_dict`）
- 表结构统一定义在 `db/schema.sql` + `migration/`

---

## 1. 权限级别与变更规则定义

### 1.1 权限级别（谁对文件能做什么）

| 级别 | 含义 |
|---|---|
| **读写** | 可改、可调用，全权负责 |
| **只读** | 可 import / 调用，但不能改 |
| **禁止** | 不碰、不改、不依赖 |

### 1.2 变更规则（改动时的约束）

| 规则 | 含义 |
|---|---|
| **全权改** | 自己的活文件，改完无需通知 |
| **需告知** | 共享文件，改前 / 改后通知对方（**改前征得同意、无异议再合**） |
| **坚决不能改** | 对方的文件，改了就是漂移 / 冲突 |

### 1.3 核心映射（三条规则覆盖全部文件）

| 归属块 | 上游侧 | 本侧 | 改动规则 |
|---|---|---|---|
| 上游文件 | 读写 | 禁止 | 上游全权改，本侧坚决不能改 |
| 下游文件 | 禁止 | 读写 | 本侧全权改，上游坚决不能改 |
| 共享文件 | 读写 | 读写 | 双方可改，改前需告知 |

> 矩阵以「读写 / 禁止」两态为主。**「只读」级别的实际用例 = `biz_rules/schemas.py`**（上游维护·读写全权，下游 import 读取·只读勿改）——凡是「一方维护、另一方 import 但不改」的跨边界文件都用「只读」。

---

## 2. 上游文件（上游侧读写·全权 / 本侧禁止）

| 文件 / 模块 | 上游侧 | 本侧 | 改动规则 |
|---|---|---|---|
| `config/crawler_settings.py` + `config/sites/*`（24 个站点配置） | 读写 | 禁止 | 上游全权 |
| `core_engine/scrapling_client.py` | 读写 | 禁止 | 上游全权 |
| `core_engine/pagination_driver.py` | 读写 | 禁止 | 上游全权 |
| `core_engine/router.py` | 读写 | 禁止 | 上游全权 |
| `core_engine/api_router.py` | 读写 | 禁止 | 上游全权 |
| `core_engine/api_client.py` | 读写 | 禁止 | 上游全权 |
| `core_engine/content_cleaner.py` | 读写 | 禁止 | 上游全权 |
| `core_engine/docx_parser.py` | 读写 | 禁止 | 上游全权 |
| `core_engine/excel_parser.py` | 读写 | 禁止 | 上游全权 |
| `core_engine/pdf_meta_sniffer.py` | 读写 | 禁止 | 上游全权 |
| `core_engine/storage_writer.py` | 读写 | 禁止 | 上游全权 |
| `core_engine/transform_pipeline.py` | 读写 | 禁止 | 上游全权 |
| `core_engine/authority_client.py` | 读写 | 禁止 | 上游全权 |
| `core_engine/authority_resolver.py` | 读写 | 禁止 | 上游全权 |
| `core_engine/authority_store.py` | 读写 | 禁止 | 上游全权 |
| `core_engine/lineage_store.py` | 读写 | 禁止 | 上游全权 |
| `core_engine/lineage_tracer.py` | 读写 | 禁止 | 上游全权 |
| `core_engine/quality_checker.py` ★ | 读写 | 禁止 | 上游全权 |
| `core_engine/review_exporter.py` | 读写 | 禁止 | 上游全权 |
| `flows/crawl_flow.py` | 读写 | 禁止 | 上游全权 |
| `biz_rules/cleaners/*`（6） | 读写 | 禁止 | 上游全权 |
| `biz_rules/extractors/*`（来源解析器 25 个） | 读写 | 禁止 | 上游全权 |
| `biz_rules/source_mapper.py` | 读写 | 禁止 | 上游全权 |
| `biz_rules/document_validator.py` | 读写 | 禁止 | 上游全权 |
| `biz_rules/collected_document.py` | 读写 | 禁止 | 上游全权 |
| `biz_rules/css_extractors.py` | 读写 | 禁止 | 上游全权 |
| `biz_rules/clinical_research.py` | 读写 | 禁止 | 上游全权 |
| `biz_rules/who_don.py` | 读写 | 禁止 | 上游全权 |
| `biz_rules/drug_name_normalizer.py` | 读写 | 禁止 | 上游全权 |
| `biz_rules/schemas.py` ★ | 读写 | **只读** | 上游全权（下游只读勿改） |
| `biz_rules/observations.py` | 读写 | 禁止 | 上游全权 |
| `db/sites/*`（chictr / hkex / pubmed / clinicaltrials） | 读写 | 禁止 | 上游全权 |
| `db/source_refresh.py` | 读写 | 禁止 | 上游全权 |
| `main_etl.py` | 读写 | 禁止 | 上游全权 |
| `feedback_ingest.py` | 读写 | 禁止 | 上游全权 |
| `可以提前把这个喂给ai.md` | 读写 | 禁止 | 上游全权 |
| `docker-compose.authority.yml` | 读写 | 禁止 | 上游全权（暂缓启用） |
| `tests/` 上游组（20 个，跟随被测上游代码，明细见 §7） | 读写 | 禁止 | 上游全权 |

---

## 3. 下游文件（本侧读写·全权 / 上游禁止）

| 文件 / 模块 | 上游侧 | 本侧 | 改动规则 |
|---|---|---|---|
| `disambiguation/*`（全部 7 个） | 禁止 | 读写 | 本侧全权 |
| `flows/extraction_flow.py` | 禁止 | 读写 | 本侧全权 |
| `flows/extraction_worker.py` | 禁止 | 读写 | 本侧全权 |
| `flows/extraction_rq_job.py` | 禁止 | 读写 | 本侧全权 |
| `flows/chunking.py` | 禁止 | 读写 | 本侧全权 |
| `flows/graph_publish.py` | 禁止 | 读写 | 本侧全权 |
| `flows/history_fetch.py` | 禁止 | 读写 | 本侧全权 |
| `flows/history_publish.py` | 禁止 | 读写 | 本侧全权 |
| `biz_rules/extraction_prompts.py` | 禁止 | 读写 | 本侧全权 |
| `biz_rules/prompts.py` | 禁止 | 读写 | 本侧全权 |
| `biz_rules/reviewed_graph.py` | 禁止 | 读写 | 本侧全权 |
| `biz_rules/history_models.py` | 禁止 | 读写 | 本侧全权 |
| `biz_rules/history_sources.py` | 禁止 | 读写 | 本侧全权 |
| `biz_rules/entity_schemas.py` | 禁止 | 读写 | 本侧全权 |
| `core_engine/agent_config.py` | 禁止 | 读写 | 本侧全权 |
| `core_engine/agent_runner.py` | 禁止 | 读写 | 本侧全权 |
| `core_engine/agent_tools/*`（5） | 禁止 | 读写 | 本侧全权 |
| `core_engine/agents/*`（7） | 禁止 | 读写 | 本侧全权 |
| `core_engine/merge_queue.py` | 禁止 | 读写 | 本侧全权 |
| `core_engine/weknora_graph_client.py` | 禁止 | 读写 | 本侧全权 |
| `db/agent_run_repo.py` | 禁止 | 读写 | 本侧全权 |
| `db/history.py` | 禁止 | 读写 | 本侧全权 |
| `db/review_lifecycle.py` | 禁止 | 读写 | 本侧全权 |
| `db/review_listeners.py` | 禁止 | 读写 | 本侧全权 |
| `db/publication.py` | 禁止 | 读写 | 本侧全权 |
| `sync_to_weknora.py` | 禁止 | 读写 | 本侧全权 |
| `reparse_weknora.py` | 禁止 | 读写 | 本侧全权 |
| `GRAPH_SYNC_DESIGN.md`、`图谱Schema-实体类型定义.md` | 禁止 | 读写 | 本侧全权 |
| `ops/systemd/*`（3 个 service） | 禁止 | 读写 | 本侧全权 |
| `WeKnora-main/*`（5 个 `__init__.py`） | 禁止 | 读写 | 本侧全权 |
| `data/quality_annotations/README.md` | 禁止 | 读写 | 本侧全权 |
| `tests/` 下游组（14 个，跟随被测下游代码，明细见 §7） | 禁止 | 读写 | 本侧全权 |

---

## 4. 共享文件（双方读写·改前需告知）

> ⚠️ **当前处于阶段2 试运行期，本节全部文件冻结**：双方均不改动。确需改动时先说明内容与原因、双方确认后当日同步，详见 §8.3「共享层冻结」。

| 文件 / 模块 | 上游侧 | 本侧 | 改动规则 |
|---|---|---|---|
| `db/session.py` | 读写 | 读写 | 双方改前告知 |
| `db/models.py` | 读写 | 读写 | 双方改前告知 |
| `db/schema.sql` | 读写 | 读写 | 双方改前告知 |
| `db/repository.py` ★ | 读写 | 读写 | 双方改前告知 |
| `migration/*` | 读写 | 读写 | 双方改前告知 |
| `config/settings.py` | 读写 | 读写 | 双方改前告知 |
| `core_engine/cloud_api_client.py` ★ | 读写 | 读写 | 双方改前告知 |
| `core_engine/task_queue.py` | 读写 | 读写 | 双方改前告知 |
| `core_engine/exception_logger.py` | 读写 | 读写 | 双方改前告知 |
| `requirements.txt` | 读写 | 读写 | 双方改前告知 |
| `.env.example` | 读写 | 读写 | 双方改前告知 |
| `.gitignore` | 读写 | 读写 | 双方改前告知 |
| `pytest.ini` | 读写 | 读写 | 双方改前告知 |
| `frontend/*`（全部 33 个） | 读写 | 读写 | **分区治理**：上游区（清洗质量审核页）/ 本侧区（实体审核页）各自全权，共享基建（路由表 / 布局 / 鉴权 / 公共组件）改前告知 |
| `api/*`（全部 15 个） | 读写 | 读写 | 双方改前告知 |
| `README.md`、`ARCHITECTURE.md`、`ARCHITECTURE_ISSUES.md`、`dev_plan.md` | 读写 | 读写 | 双方改前告知 |
| `task_doc/*`（24 个任务/分工文档） | 读写 | 读写 | 双方改前告知 |
| 各目录 `__init__.py`（跟随父目录归属；顶层混合目录的归共享） | 读写 | 读写 | 双方改前告知 |
| `tests/` 共享组（6 个：conftest / station_profiles / fixtures / repository） | 读写 | 读写 | 双方改前告知 |
| `index.html`（根目录独立静态页） | 读写 | 读写 | 双方改前告知 |
| `AGENTS.md`（本文件） | 读写 | 读写 | 双方改前告知 |

---

## 5. 特殊文件单独说明（★）

| 文件 | 为什么特殊 | 处置 |
|---|---|---|
| `db/repository.py` | **函数级混合**：同一文件既有上游 `upsert_document`，又有下游 `update_extraction_status` / 生成 embedding / 实体入库 | 暂**不拆**，双方读写·改前告知；后续「服务分割」时再拆成 upstream / downstream 两份 |
| `core_engine/cloud_api_client.py` | **一文件两用**：上游 mineru PDF 解析 + 下游 qwen 抽取 / embedding | 暂**不拆**，双方读写·改前告知 |
| `core_engine/quality_checker.py` | 注释自称核心模块，物理挂在爬虫清洗链路 | 已定归**上游**，本侧禁止改（引用其逻辑不等于拥有代码改动权） |
| `biz_rules/schemas.py` | 上游维护的数据契约（上游读写全权），但被下游 `extraction_flow` / `extraction_prompts` import 读取 | 上游**读写全权**、下游**只读勿改**（本矩阵唯一的「只读」用例） |
| `frontend/*` | 单一 Vue3 前端，承载上游「清洗质量审核」+ 本侧「实体审核」两类页面 | **共享·分区治理**：上游区（清洗质量审核）由上游全权、本侧区（实体审核/消歧/图同步）由本侧全权；路由表 / 布局 / 鉴权等共享基建改前告知 |

---

## 6. 共享层边界（架构依据）

### 6.1 现状诊断

- git tracked 文件 **310 个**
- 三个「混合目录」：`core_engine/`(38)、`flows/`(9)、`biz_rules/`(47)，上游与本侧 `.py` 交错堆放
- **真正的耦合不在「目录混放」，而在「共享层依赖网」**：`db/`、`cloud_api_client`、`schemas`、`settings` 被上下游同时 import

### 6.2 共享层六大类（基于 import 事实）

| 共享模块 | 被谁 import | 判定 |
|---|---|---|
| `db/session.py` / `db/models.py` / `db/schema.sql` | 上下游几乎所有模块 | 共享层 |
| `db/repository.py` | 上游 `main_etl`/`crawl_flow`/`config/sites/*`；下游 `extraction_flow`/`disambiguation/*`/`api/*` | 共享层，⚠️ 函数级混合（见 §5） |
| `migration/` | 部署/迁移 | 共享层 |
| `config/settings.py` | 全仓 | 共享层 |
| `core_engine/cloud_api_client.py` | 上游 `router`/`docx_parser`（mineru PDF）；下游 `extraction_flow`/`disambiguation`/`agent_tools`（qwen 抽取 + embedding） | 共享层（一文件两用途） |
| `requirements.txt` / `.env.example` / `.gitignore` / `pytest.ini` | 全仓 | 共享工程配置 |
| `frontend/`（Vue3 单前端，33 文件） | 通过 `api/` 调用上下游后端 | 共享层（**分区治理**） |
| `api/`（全部 15 个） | FastAPI 审核后台，承载上游「清洗质量审核」+ 本侧「实体审核」接口 | 共享层（双方读写·改前告知） |

> **结论**：真正的「契约层」就这几类，范围清晰。分仓/拆服务时，这一层要么复制两边、要么抽独立包，不能归任何一方独有。

### 6.3 目标目录结构（若最终物理切分）

```
upstream/    ← §2 全部
downstream/  ← §3 全部
shared/      ← §4 全部
```

三者关系：`upstream/` 与 `downstream/` 都 `import shared/`，彼此**互不 import**（这是切分成功的验收标准）。

---

## 7. 测试文件归属（A 方案：跟随被测代码）

> 判定依据：测试跟随其**被测代码**的归属——上游代码的测试归上游、下游代码的测试归下游、跨层/共享基建的测试归共享。共 40 个。

| 归属 | 测试文件 | 数量 |
|---|---|---|
| **上游** | `test_authority_client`、`test_authority_resolution_table`、`test_authority_resolver`、`test_authority_store`、`test_chembl_authority`、`test_identifier_alignment`、`test_identifier_formats`、`test_identifier_pipeline`、`test_drug_name_normalizer`、`test_drug_name_pipeline`、`test_source_mapper`、`test_source_refresh`、`integration_source_refresh`、`test_content_cleaner`、`test_quality_checker`、`test_transform_pipeline`、`test_clinical_research`、`test_station_fixtures`、`test_api_field_mapping`、`biz_rules/test_document_validator` | 20 |
| **下游** | `disambiguation/test_engine`、`disambiguation/test_llm_ranker`、`disambiguation/test_normalization_rules`、`disambiguation/test_normalizer`、`disambiguation/test_rules`、`biz_rules/test_entity_schemas`、`biz_rules/test_normalizer_l3`、`flows/test_chunking`、`test_extraction_runtime_safety`、`test_reviewed_graph`、`test_history`、`integration_history`、`test_publication`、`integration_publication` | 14 |
| **共享** | `conftest.py`、`station_profiles.py`、`fixtures/collected_nmpa_frontmatter.json`、`db/test_repository_stale`、`test_repository_storage`、`integration_research_read` | 6 |

> **协作约定**：上游代码的测试当前由成员2 代写，上游同门负责 review / 验收；改上游代码时应连带改对应测试。

---

## 8. 仓库治理与分仓进展

### 8.1 为什么要分

全链路（爬虫 → 清洗 → 抽取 → 消歧 → 审核 → 图同步 → 前端）原先集中在同一个仓库 `CPU-ZK-TEAM/ZK_Data-Fabric-test`：

- 双方改动在同一批 `db/`、`migration/`、`biz_rules/` 文件里交织，合并冲突与分支混乱持续累积（远端近 50 个分支）
- 上游改爬虫/清洗、本侧改消歧/抽取，互相被迫等待对方的分支与迁移
- 代码层面共用一个工作区，课题推进互相阻塞

**目标**：① 边界清晰（每个目录只有一个明确维护者）；② 互不干扰（独立建分支、独立提交、独立发布）；③ 交接稳定（数据交接契约固化，改动走评审而非靠默契）。

### 8.2 方案选型（三选一，已定 A 的变体）

| 方案 | 做法 | 结论 |
|---|---|---|
| A. 双仓分治 + 契约包 | 本侧代码迁到个人仓，契约层抽成独立包 | **采纳其「双仓分治」思路** |
| B. 组织内双仓 | 组织下新建「上游仓」「课题仓」 | 需组织 admin 建仓授权，本侧无此权限 |
| C. 单仓 monorepo 治理 | 顶层重组 + CODEOWNERS | 改动最小，但不是「分仓」 |

**最终落地 = 「完整镜像 + 文件级权限矩阵」**，而非 `git filter-repo` 抽子目录：

理由：`core_engine/`、`flows/`、`biz_rules/` 三个目录**文件级交织严重**，硬切会导致两侧都跑不起来。改为**两边完整复制**同一份代码，用本文件的权限矩阵做**软隔离**——各自只改自己那一块，共享层走「改前告知」。

### 8.3 分阶段流程与当前进展

| 阶段 | 动作 | 状态 |
|---|---|---|
| **阶段0** | 治理规则定稿（本文件） | ✅ 完成（2026-11-03） |
| **阶段1** | 复制仓库：完整镜像到本侧个人仓（三分支 + 完整历史） | ✅ 完成（2026-11-03） |
| **阶段1'** | 上游侧同样复制个人仓（镜像 + tree hash 验证） | 待执行 |
| **阶段2** | 试运营（约 1–2 天，**自 2026-11-03 起**）：两侧独立开发，按本矩阵软隔离；**共享层冻结**（见下） | 🔄 试运营中 |
| **阶段3** | 原组织仓废弃 / 归档（前置条件见下） | 待执行 |
| **阶段4** | 组织接收两个平行仓，长期运营 | 待执行 |
| **阶段5** | 运行时拆服务（拆独立部署单元 + 接口调用），并锁行防并发写冲突 | 待定（可选，不阻塞交接） |

**终态形态（已定，2026-11-03）：A —— 组织下两个平行仓各自独立**

- 上游仓 = 爬虫 / 清洗 / 采集链路
- 下游仓 = 抽取 / 消歧 / 审核 / 图同步 / 前端
- 两仓**各自完整镜像**同一份代码基线，用本文件的权限矩阵做软隔离
- 因此**不做目录分层**（不建 `upstream/` `downstream/` `shared/`），§6.3 仅为「若将来改走形态 B/C」的备选参考

**阶段2 试运行策略：共享层冻结（替代同步机制）**

试运行仅 1–2 天，无需引入 pip 包 / submodule / 定期比对等机制。改为**冻结策略**，把风险归零：

- 试运行期内，§4 列出的共享文件（`db/` 四件、`migration/`、`settings`、`cloud_api_client`、`task_queue` / `exception_logger`、工程配置、`frontend/`、`api/`）**双方均不改动**
- 若确实必须改：先在群里说明改动内容与原因，双方确认无冲突后再动，改完当日同步给对方
- 冻结的目的是让 1–2 天的试运行只验证「两仓能否独立跑通」，不叠加协作变量

**阶段3 废弃 / 归档前置条件（三项缺一不可）**

1. 上游侧完成镜像并**通过 tree hash 逐分支比对**（不能只比文件数）
2. 确认无第三方仍依赖原仓（成员2 等；其 31 个测试提交需确认归属去向）
3. 打 tag 或 archive 存档，废弃不等于删除，历史需可回溯

**阶段4 组织接收：权限前置**

将两个个人仓 transfer / 移入组织需要**组织 owner** 操作。本侧为 Contributor（无 admin），须提前确认 owner 身份与流程，不可等到试运行结束再发起。

**⚠️ 形态 A 的固有代价（须知情）**

两仓各自完整镜像 ⇒ 同一个共享层文件在两个仓各有一份，**没有单一真相源**。长期必然漂移。缓解约定：共享层以「谁在维护」判定优先方（如 `db/repository.py` 以成员2 侧为准），另一方只跟随同步、不主导变更。此约定在阶段4 后可重新评估。

### 8.4 阶段1 执行记录

- 本侧仓：`wtang5407-source/ZKdata-disamb-rev`（Private）
- 推送范围：`main` / `dev` / `tww-GP` 三个主分支 + 完整提交历史（不带 40+ 废弃分支）
- 镜像验证：三分支 commit 一致、**tree hash 逐分支比对全等**、提交历史 109 = 109
- 分库验证：clone 个人仓到项目外干净目录，四层递进（结构 / 隔离 / 依赖 / 测试）+ **与原项目基线做用例级 diff**
  - 结构：默认分支 `tww-GP`、tracked 文件两仓相等、`AGENTS.md` 就位
  - 隔离：`.env` / `data/` / `scripts/` / `.workbuddy/` / `node_modules` 均未入库
  - 依赖：`disambiguation.{normalizer,rules,engine}`、`biz_rules.{entity_schemas,schemas}` 全部可导入
  - 测试：clone 独有失败 5 个，全为 `test_station_fixtures` 的 `[nmpa]` 参数；补入 `data/json_envelopes/nmpa` 后重跑，失败数与本地基线**完全一致**
  - **结论：代码层面零差异，所有差异可归因于本地私有资产（数据文件 + `.env`），分库成功**

### 8.5 权限现状（本侧）

- 本侧对 `CPU-ZK-TEAM/ZK_Data-Fabric-test` 为**外部协作者（Contributor）**，拥有 **Write** 权限，**非 admin**
- 因此：本侧**可**推送代码、迁移自己的模块；本侧**不可**在组织内新建仓库、不可 archive / 重命名 / 转移组织仓
- 组织内的收尾动作（建仓、清理、transfer）需**组织 owner / admin** 配合；同门 **lazazyfolivora** 可协助 transfer（待其确认权限）

### 8.6 本地私有资产（不入库，新环境必须单独准备）

| 资产 | 状态 | 缺失后果 |
|---|---|---|
| `.env` | 不入库（本机私有配置） | `db.session` / `db.repository` **import 不报错**，静默走 `localhost:5432` 默认值，连库时才失败。新环境必须先配 `.env` |
| `data/` | 整目录忽略（仅 `quality_annotations/README.md` 入库） | `test_station_fixtures` 等 fixture 测试全红（依赖 `data/json_envelopes`、`data/lineage` 的真实采集数据，需单独同步） |
| `scripts/` | 整目录忽略 | 本地临时脚本，不影响运行 |
| `.workbuddy/` | 忽略 | 本地工作记忆与会话记录 |

### 8.7 本地工作区与 remote 约定（2026-11-03 定）

本地工作目录**未搬迁**，仍复用原组织仓的 clone 目录；仓库归属通过 remote 命名区分：

> 命名提示：本节 `upstream` 指 **git remote 名**（组织仓）；§6.3 目标目录结构里的 `upstream/` 指**代码目录**（上游侧模块），两者同名但含义无关，勿混淆。

| remote 名 | 指向 | 用途 |
|---|---|---|
| `origin` | 个人仓 `wtang5407-source/ZKdata-disamb-rev` | **默认推拉目标**（`git push` / `git pull` 不带参数即打此处） |
| `upstream` | 组织仓 `CPU-ZK-TEAM/ZK_Data-Fabric-test` | 仅用 `git fetch upstream` 查看同门进展，**不自动合入** |

分支跟踪关系：

- `tww-GP` / `main` / `dev` → 跟踪 `origin/<同名分支>`（个人仓）
- 其余 9 个历史分支（`UI-graph` / `feat/nextjs-frontend` / `frontend-with-structure` / `humorous-beech` / `test-suite` / `thesis-disambiguation` / `ui-design` / `ui-redesign` / `update-opening-report`）→ **已于 2026-11-03 删除**（其中 5 个含本地独有提交，SHA 留痕于本地 `data/_deleted_branches_backup.txt`；如需找回可查 reflog）
- 同时清理：`git fetch upstream --prune` 清理失效远程引用（50 → 6），移除 `.kilo/worktrees/` 下两个 Kilo Code 历史工作树

> 当前本地仅保留 `tww-GP`（主工作分支）、`main`、`dev` 三个分支，操作面已收敛。

⚠️ **历史坑（已修正）**：2026-11-03 之前 `tww-GP` 的 upstream 是 `origin/dev`（即**组织仓的 dev 分支**），一次不带参数的 `git push` 就会直接推到组织仓。改名后该风险已消除。若在旧环境或他人机器上继续工作，须先核对 `git for-each-ref --format='%(refname:short)|%(upstream:short)' refs/heads/`。

常用操作：

- 同步个人仓：`git pull`（= `git pull origin <当前分支>`）
- 查看组织仓同门进展：`git fetch upstream` 后 `git log upstream/dev --oneline -10`
- 需要往组织仓交付共享层改动时：显式 `git push upstream <分支>`，走「改前告知」流程

---

## 9. 决策留痕

### 9.1 文件归属确认（8 项，全部 ✅）

| # | 事项 | 结论 |
|---|---|---|
| 1 | 角色两方（上游侧 / 本侧），成员2 的 `repository.py` 并入共享层 | ✅ 认可 |
| 2 | 「只读」用例 `schemas.py`（上游读写全权、下游只读勿改） | ✅ 认可 |
| 3 | `repository.py` / `cloud_api_client.py` 暂不拆、双方读写需告知 | ✅ 认可 |
| 4 | 改前告知 = 更强（改前征得同意、无异议再合） | ✅ 采纳 |
| 5 | 全量扫描漏文件 | ✅ 已补齐（5 类遗漏 + 4 处数字偏差） |
| 6 | `index.html` 归属 | ✅ 共享 |
| 7 | `scripts/` 3 个误 track 文件 | ✅ `check_hkex_data.py` 删除；`quality_gate_eval.py` / `test_nccn.py` `git rm --cached` 移出跟踪；恢复「`scripts/` 不入库」约定（2026-11-03 已执行） |
| 8 | 测试 A 方案协作约定（上游代码测试由成员2 代写、上游同门 review，改上游代码连带改测试） | ✅ 认可 |

### 9.2 混合目录与契约层处置

| # | 事项 | 结论 |
|---|---|---|
| 1 | `core_engine/quality_checker.py` 归属 | ✅ 归上游 |
| 2 | `core_engine/transform_pipeline.py` 归属 | ✅ 归上游 |
| 3 | `core_engine/task_queue.py` / `exception_logger.py` | ✅ 归共享 |
| 4 | `core_engine/authority_*` 三件 + `api_router.py` + `api_client.py` | ✅ 归上游（authority 链整条） |
| 5 | `biz_rules/drug_name_normalizer.py` | ✅ 归上游 |
| 6 | 共享 infra（前端 / 审核 API / Agent / 图同步） | ✅ 由本侧负责 |
| 7 | 前端治理方式 | ✅ 共享·分区治理（上游「清洗质量审核」页 / 本侧「实体审核」页各区全权） |

---

## 10. 验收清单（阶段2 起持续校验）

- [ ] 改动文件前已按 §2–§4 核对归属，未越界修改对方文件
- [ ] 共享文件改动已走「改前告知」，双方无异议后合入
- [ ] 两侧各自 `pytest` **无回归**（基线 130 个失败为仓库既有技术债，非分库引入；判定标准是失败集合不新增，而非失败数为 0）
- [ ] 上游能独立跑「爬虫 → 清洗 → 落库」
- [ ] 本侧能独立跑「抽取 → 消歧 → 审核」
- [ ] `upstream/` 与 `downstream/` 互不 import（物理切分时校验）

---

> **维护约定**：本文件为双方共享，任何修改需「改前告知」对方。文件归属发生变更时，同步更新 §2–§4 对应行并在 §9 追加决策记录。
