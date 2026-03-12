# 自动化测试增量继承方案（按功率逐级筛选）

## 1. 目标与业务规则

针对同一组前置条件（项目名称、频段、频点），实现“功率递进式自动化测试”：

1. 首次测试某功率（例如 10）时，按当前参数空间完整执行。
2. 下一个功率（例如 20）只测试上一个功率中**成功**的参数组合；失败组合不重复。
3. 若再测中间功率（例如 15），同样只继承最近“前序功率”的成功组合。
4. 若后续测试新增了参数范围，导致参数组合多于前序功率，则新增组合必须补测。

> 关键词：继承成功集、失败不重试、新增组合补测。

---

## 2. 核心概念

### 2.1 测试上下文 Key

定义唯一上下文：

- `project_name`
- `band`
- `frequency`

记为 `context_key = (project_name, band, frequency)`。

所有“功率继承关系”都只在同一 `context_key` 内成立，避免串数据。

### 2.2 参数组合签名（Combo Signature）

每一组参数组合生成稳定签名 `combo_id`：

- 将组合按参数名排序后序列化（如 JSON canonical）
- 计算哈希（如 SHA1）或直接使用规范化字符串

示例：

```json
{"cdr delay": 10, "eq offset": -3, "eq sr0": 5}
```

得到 `combo_id=abc123...`。

### 2.3 结果语义

统一结果：

- `PASS`
- `FAIL`
- `SKIP`

继承时只认 `PASS`，`FAIL/SKIP` 不进入后续功率候选。

---

## 3. 数据落库设计（推荐 SQLite）

建议新增三张表：

## 3.1 `test_run`

记录一次任务运行：

- `run_id` (PK)
- `project_name`
- `band`
- `frequency`
- `power`
- `param_schema_hash`（参数空间定义哈希，用于判断组合空间是否变化）
- `started_at`, `finished_at`
- `status`（running/success/partial/failed/stopped）

## 3.2 `combo_catalog`

记录该上下文下出现过的所有组合：

- `context_key` 相关字段
- `combo_id` (PK within context)
- `combo_json`
- `created_in_run_id`

## 3.3 `combo_result`

记录每次运行里组合结果：

- `run_id`
- `combo_id`
- `result`
- `detail`
- `timestamp`

索引建议：

- `(project_name, band, frequency, power)`
- `(context, combo_id)`
- `(run_id, combo_id)`

---

## 4. 计划生成算法（最关键）

输入：

- 当前运行：`context_key + target_power`
- 当前参数空间展开得到 `CurrentSet`

输出：

- 本次待测集合 `PlanSet`

### 4.1 查找“前序功率”

在同 `context_key` 下，取所有 `< target_power` 且状态可用（success/partial）的运行，选择功率最大的一个 `base_power_run`。

- 若不存在前序功率：`PlanSet = CurrentSet`（全量首测）

### 4.2 继承成功集

若存在 `base_power_run`：

- 取其 `PASS` 组合集合：`PassSet(base)`
- 计算本次候选：`InheritedSet = CurrentSet ∩ PassSet(base)`

### 4.3 新增组合补测

为满足“后测参数更多时要补测”，加入：

- `NewSet = CurrentSet - HistoricalKnownSet`
- `HistoricalKnownSet` = 同 `context_key` 下历史所有功率出现过的组合全集

最终：

- `PlanSet = InheritedSet ∪ NewSet`

这样可保证：

- 历史失败组合不会被重复（不在 `PassSet`）
- 新增组合一定被执行（在 `NewSet`）

### 4.4 边界处理

1. `PlanSet` 为空：直接提示“无可执行组合（历史失败或未命中继承条件）”。
2. 基准运行为 `partial`：仅继承其中真实 `PASS` 结果。
3. 同功率重复执行：
   - 默认可全量重跑 `PlanSet`
   - 或提供“仅重试 FAIL”的高级选项（可选）

---

## 5. 你给出的示例如何落地

假设同一 `context_key`：

1. 先测 `power=10`：全量组合 `A~Z`，成功 `{A,B,C,D}`。
2. 再测 `power=20`：
   - 基准为 `10`，继承 `{A,B,C,D}`。
   - 若参数空间未扩展，则只测 `{A,B,C,D}`。
3. 再测 `power=15`：
   - 基准为 `<15` 的最高功率，即 `10`。
   - 只测 `{A,B,C,D}`。
4. 若后续某次（比如 `power=25`）参数扩展出新组合 `{N1,N2}`：
   - `InheritedSet` 来自前序功率成功集
   - `NewSet` 包含 `{N1,N2}`
   - 最终会把新增组合补测进去。

---

## 6. UI/交互建议（PySide6）

在“自动化测试”页增加：

1. **继承策略开关**（默认开启）
   - `按前序功率成功结果继承`
2. **计划预览按钮**
   - 展示：`CurrentSet`、`InheritedSet`、`NewSet`、`PlanSet` 数量
3. **执行前确认弹窗**
   - “本次将执行 X 组；其中继承 Y 组，新增补测 Z 组”
4. **日志增强**
   - 输出基准 run_id、基准功率、命中过滤统计

---

## 7. 与现有执行器的集成建议

可在自动化执行入口前插入“计划编排层”（Planner）：

1. 现有逻辑负责生成全量参数组合。
2. 新增 Planner 根据历史结果过滤为 `PlanSet`。
3. 执行器仅消费 `PlanSet`。
4. 每个组合执行结束后实时写 `combo_result`。

这能将“策略逻辑”和“执行逻辑”解耦，便于后续扩展（如按温度、版本分层继承）。

---

## 8. 伪代码

```python
def build_plan(context_key, target_power, current_set):
    base_run = find_latest_run_with_power_lt(context_key, target_power)

    if base_run is None:
        return current_set

    pass_set = load_pass_set(base_run.run_id)
    inherited = current_set.intersection(pass_set)

    historical_known = load_all_historical_combo_ids(context_key)
    new_set = current_set.difference(historical_known)

    return inherited.union(new_set)
```

---

## 9. 验收标准（建议）

1. 首次功率执行时，计划数 = 当前组合总数。
2. 第二次功率执行时，计划数 = 前序成功组合数（参数空间不变）。
3. 当前组合空间扩展后，计划会包含“新增组合”。
4. 历史失败组合不会被重复加入计划（除非用户主动全量重测）。
5. 日志中可追踪每个组合为何被纳入/排除。

---

## 10. 风险与规避

1. **参数命名变更导致签名不稳定**
   - 规避：组合签名前进行参数名映射和排序规范化。
2. **历史数据污染（不同项目误复用）**
   - 规避：强制使用 `project+band+frequency` 作为上下文分区。
3. **运行中断导致基准数据不完整**
   - 规避：run 状态区分 `partial`，并仅继承已确认 PASS 的组合。

