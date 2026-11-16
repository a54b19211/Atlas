# 共享层改动说明：search_similar_entities 新增返回字段 is_verified

日期：2026-11-03
改动文件：`db/repository.py`（仅 `search_similar_entities` 一个函数）
改动人：tww（消歧链路）

---

## 一、一句话结论

我在 `search_similar_entities` 的返回结果里，给每个候选**多带了一个字段 `is_verified`**，其余一律没动。属于纯增量、向后兼容，**不需要你们做任何操作**，仅请知悉。

---

## 二、改了什么（3 处，全是「加」，没有「改」也没有「删」）

| 位置 | 改动 | 性质 |
|---|---|---|
| 函数说明（docstring） | 返回字段清单里补了一行 `is_verified` | 文档同步 |
| SQL 查询 | `SELECT` 多取一列 `EntityDict.is_verified` | 追加一列 |
| 返回 dict | 每个候选多一个 key `"is_verified"` | 追加一个字段 |

具体 diff 就三处，其中真正有代码效果的是下面一行（其余两处是注释和返回拼装）：

```python
# SELECT 里追加（原来是 canonical_data 后就结束了）
EntityDict.is_verified,

# 返回结果里追加
"is_verified": r.is_verified,
```

---

## 三、为什么要加这个字段

消歧链路在「决定要不要把一条抽取出来的实体，链接到知识库里某个实体」时，
新增了一道**权威门槛**：只有目标是**已人工审核过的权威本体**（`is_verified=True`）才敢链接；
目标是**未审核的占位实体**（`is_verified=False`）时，不链接、转人工待审。

`is_verified` 是 `entity_dict` 表里**本来就存在**的一列（布尔值，表示该实体是否经过审核）。
之前 `search_similar_entities` 召回候选时没把它带出来，消歧链路要用它还得对每个候选单独再查一次库。

这次让它**在召回时顺手带出**，省掉二次查询，性能上只会更快、不会更慢。

---

## 四、对你们有没有影响：没有

请放心，这次改动不改变这个函数的任何既有行为：

| 维度 | 情况 |
|---|---|
| 函数签名（入参） | 完全不变 |
| 返回值类型 | 不变（仍是候选列表） |
| 原有 5 个字段 | `dict_id` / `name` / `similarity_score` / `canonical_data` / `aliases` 照旧返回，值不变 |
| 新增内容 | 每个候选 dict 仅**多一个 key** `is_verified` |
| 调用方 | 该函数目前**只有消歧链路调用**（`disambiguation/engine.py` 和消歧评估脚本），仓库里没有其他成员调用它 |

> 结论：如果你们的代码里没有直接调用 `search_similar_entities`，这次改动对你们**零影响**。

---

## 五、新字段 `is_verified` 的取值含义

| 取值 | 含义 |
|---|---|
| `True` | 该实体是已审核的权威本体 |
| `False` | 该实体是未审核的占位实体 |
| `None` | 该列为空（历史数据可能如此），视为「未知」 |

三个值都是直接透传数据库原值，没有做任何加工。若你们以后也要用这个字段，按上表理解即可。

---

## 六、需要你们做的

**无。** 仅请知悉。

如果你们也在用 `search_similar_entities`、或对这个字段的改动有任何异议，请随时找我，我可以调整或撤回。
