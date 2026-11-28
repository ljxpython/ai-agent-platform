# 专题 08：指定用例勾选打擂与局部回归方案（Case-Level Selective Evaluation）

> 所属项目：[独立评测中台迁移与平台原生化改造方案](README.md)｜状态：**已完成（done）**

---

## 1. 业务背景与用户痛点

在当前的独立评测工坊与白盒诊断平台中，评测集（Suite）发布冻结后，用户点击「发起评测打擂」默认必须针对该版本下的**全量用例**进行执行。在日常工程实践中，研发与业务人员面临以下高频摩擦：

1. **调试单题/偶发 Badcase 成本极高**：当题库规模扩大（如数十至数百题），开发者往往只是修改了某一个 Prompt 节点或某个工具逻辑，希望针对特定的 1~2 道失败用例（如特定报错题 `COP-PITFALL-01`）进行快速验证。强制全量开考导致耗时过长，且大量浪费推理模型与裁判模型的 Token 及预算配额。
2. **能力分级与分批验证受阻**：某些复杂用例（如多轮博弈 `simulation`、工作区文件操作）可能仅适配特定高阶 Agent（如 `dearflow_agent`），而简单问答用例适用于轻量模型。全量开考容易因个别用例能力不匹配而阻碍整体打擂。
3. **缺乏直观的用例挑选交互**：用例表格首列仅为静态数字序号（`# 1, 2, 3`），无法直接进行复选操作，无法让用户在总览考题时随心组合“重点回归子集”。

**核心目标：**
在保持现有评测版本快照（`evaluation-target/v1`）完整性与证据不可篡改的前提下，在考题列表表格实现直观的 Checkbox 多选机制，支持将选定的若干用例（`case_keys`）透传至单配置基准开考及多模型矩阵打擂，实现**秒级触发、成本可控、精准回归**的局部打擂能力。

---

## 2. 方案与技术设计

### 2.1 整体架构与数据流

```mermaid
flowchart TD
    subgraph UI ["platform-web 前端"]
        A["CaseEditorPanel<br/>(考题表格 # 列)"] -->|勾选单项 / 全选 / 反选| B["selectedCaseKeys 响应式状态"]
        B --> C["EvaluationStudioPage<br/>按钮文案动态联动"]
        B --> D["LaunchRunModal<br/>开考范围提示与确认"]
    end

    subgraph API ["platform-api 控制面"]
        D -->|POST /studio/runs (case_keys)| E["studio_router: create_run"]
        D -->|POST /studio/runs/matrix (case_keys)| F["studio_router: create_matrix_runs"]
        E --> G["targets: check_readiness<br/>(仅预检所选用例)"]
        F --> G
        G --> H["studio_service: create_run_record<br/>(用例子集过滤)"]
    end

    subgraph Runner ["eval-runner 评测执行端"]
        H -->|EvalRun (仅含选定用例)| I["并发任务调度池"]
        I --> J["MLflow Trace & 裁判打分"]
    end
```

### 2.2 详细设计规格

#### 1. 前端用例列表表格（`CaseEditorPanel.vue`）
* **表头 Checkbox**：
  * 表头第 1 列 `#` 增加全选复选框。
  * 状态联动：全选（checked）、无选中（unchecked）、部分选中（`indeterminate` 半选态）。
  * 搜索联动：当用户在搜索框输入关键词过滤时，全选操作仅作用于当前 `filteredRows` 匹配的可见考题，避免误勾选隐藏用例。
* **数据行 Checkbox**：
  * 每行最左侧序号列改造为：`[Checkbox] {{ idx + 1 }}`，紧凑排布。
  * 勾选状态双向绑定，提供 `selectedCaseKeys` 状态导出。
* **状态清除与提示栏**：
  * 当 `selectedCount > 0` 时，表格工具栏上方显式提示：“已勾选 $N$ 道考题用于局部评测打擂”，并提供一键【清空选择】与【反选】按钮。

#### 2. 开考弹窗与主页按钮联动（`LaunchRunModal.vue` & `EvaluationStudioPage.vue`）
* **按钮状态感知**：
  * 无勾选时：主页开考按钮显示「发起评测打擂 →」。
  * 勾选 $N$ 题时：按钮高亮显示「发起评测打擂 ($N$ 题) →」。
* **弹窗范围提示**：
  * 弹窗接收 `selectedCaseKeys: string[]`。
  * 弹窗顶部模式选择下方展示当前开考范围提示条：
    * 若勾选了题目：展示 `已选局部打擂用例：(用例列表 tags) 仅运行勾选题目`。
    * 若未勾选：不展示局部芯片，默认全量开考。
* **Readiness 校验针对性优化**：
  * 弹窗向 `/api/evaluation/studio/readiness` 发起预检时，若存在 `selectedCaseKeys`，仅将选中的用例清单传入预检，**未选中的用例即使能力不兼容也不会阻碍当前开考**。

#### 3. 后端协议与打擂透传（`apps/platform-api`）
* **单配置开考（`POST /api/evaluation/studio/runs`）**：
  * `RunCreate` 模式已声明 `case_keys: list[str] | None = Field(default=None, max_length=500)`。
  * `studio_service.create_run_record` 已包含过滤逻辑：
    ```python
    selected_keys = set(body.case_keys) if getattr(body, "case_keys", None) else None
    cases = [
        c for c in version.frozen_cases_json
        if selected_keys is None or c["case_key"] in selected_keys
    ]
    ```
* **多模型矩阵打擂（`POST /api/evaluation/studio/runs/matrix`）**：
  * `MatrixCreate` 补充字段：
    ```python
    case_keys: list[str] | None = Field(default=None, max_length=500)
    ```
  * `studio_router.create_matrix_runs` 将 `body.case_keys` 显式透传给每个变体的 `RunCreate`。
* **Readiness 预检精准化**：
  * `POST /api/evaluation/studio/readiness` 接收可选的 `case_keys`，预检时仅针对目标用例集合推导 `incompatible_cases`。

---

## 3. 核心边界与防护设计

1. **版本漂移防护**：
   用户在页面勾选的是工作区考题（可能包含草稿或新增考题），若在弹窗中选择了一个较旧的题库冻结版本（旧版本中不存在该 `case_key`）：
   后端按 `c["case_key"] in selected_keys` 自动求交集；若交集为空，抛出 400 `eval_cases_empty: "没有可执行的测试用例。"`，防止生成空运行。
2. **无缝回退（Zero Breaking Change）**：
   当用户未做任何勾选直接点击开考，前端传递 `case_keys: undefined`，后端维持原逻辑对冻结版本的全量用例进行开考，保证老用户操作习惯不受任何影响。
3. **并发与 Pass^k 聚合准确性**：
   单题重复 $k$ 次时，`summary_metrics_json["total_cases"]` 精准设置为 `len(cases) * body.repeat_k`，打擂大厅的进度百分比基于实际选定用例数动态计算，不与全量版本题数混淆。

---

## 4. 本专题规划任务（实施与验证清单）

### Task 8.1：后端矩阵打擂 Schema 扩展与 Readiness 选定用例预检
用户需要不仅在单配置开考时指定题目，在多模型矩阵打擂时也能针对选定用例发起横向 PK，同时预检时不能被未选中的无关用例阻碍。

**状态：** 已完成（done）。
**完成标准：** `MatrixCreate` 与 `ReadinessRequest` 支持 `case_keys`，`create_matrix_runs` 正确透传；`check_readiness` 仅针对指定用例检查兼容性；Pytest 测试 100% 通过。
**涉及位置：**
* `apps/platform-api/src/platform_api/modules/evaluation/studio_schemas.py`
* `apps/platform-api/src/platform_api/modules/evaluation/studio_router.py`
* `apps/platform-api/tests/test_evaluation_studio.py`

- [x] 在 `MatrixCreate` 与 `ReadinessRequest` 增加 `case_keys: list[str] | None` 字段。
- [x] 在 `create_matrix_runs` 中向各变体子任务 `RunCreate` 透传 `case_keys`。
- [x] 在 `readiness_check` / `create_run` 支持可选的 `case_keys` 预检与过滤。
- [x] 编写单测验证：指定用例单开考、指定用例矩阵开考、指定用例排除不兼容干扰。

**开发与验证证据：**
* 运行 `uv run --directory apps/platform-api pytest tests/test_evaluation_studio.py` 验证通过（1 passed in 1.39s）。验证了 readiness 仅校验过滤后的用例、单配置开考过滤用例以及矩阵打擂透传过滤用例（`total_cases == 1`）。

---

### Task 8.2：前端 API Client 契约升级与开考弹窗范围提示
前端开考弹窗需要让用户清楚感知当前评测是“全量”还是“已选 X 题”，并在发起时将用例列表准确送达后端。

**状态：** 已完成（done）。
**完成标准：** `services/evaluation/studio.ts` 契约补充 `case_keys`；`LaunchRunModal.vue` 接收 `selectedCaseKeys`，直观呈现评测范围芯片，开考与打擂事件完整透传。
**涉及位置：**
* `apps/platform-web/src/services/evaluation/studio.ts`
* `apps/platform-web/src/modules/evaluation/components/LaunchRunModal.vue`
* `apps/platform-web/src/modules/evaluation/components/SelectiveEvaluation.spec.ts`

- [x] 扩展 `createRun`、`checkReadiness` 与 `createMatrixRuns` 的 payload 类型定义，允许传入 `case_keys?: string[]`。
- [x] 改造 `LaunchRunModal.vue`，增加 `selectedCaseKeys` prop，添加开考用例范围提示栏。
- [x] 在 `triggerReadiness` 与 `submitLaunch` 时根据是否有勾选，将 `case_keys` 组装进 `emit("launch")` 与 `emit("launchMatrix")`。
- [x] 单元测试验证：弹窗在有勾选与无勾选下的文字渲染及发射 payload 的正确性。

**开发与验证证据：**
* 运行 `cd apps/platform-web && pnpm typecheck`（`vue-tsc --noEmit`）通过（TypeScript: No errors found）。
* 单元测试通过 `SelectiveEvaluation.spec.ts` 验证 `LaunchRunModal` 提示文本及 `checkReadiness`/`launch` 透传 `case_keys`。

---

### Task 8.3：考题表格复选框交互与主页按钮联动重构
用户需要直接在考题列表最左侧第一列进行快速勾选、全选、反选，并且主页面的操作按钮需要随之动态响应。

**状态：** 已完成（done）。
**完成标准：** `CaseEditorPanel.vue` 表头支持全选/半选，数据行支持每题勾选；`EvaluationStudioPage.vue` 按钮文案联动，选定题目顺畅带入开考弹窗；`vue-tsc` 与 Vitest 100% 通过。
**涉及位置：**
* `apps/platform-web/src/modules/evaluation/components/CaseEditorPanel.vue`
* `apps/platform-web/src/modules/evaluation/EvaluationStudioPage.vue`
* `apps/platform-web/src/modules/evaluation/components/SelectiveEvaluation.spec.ts`

- [x] 改造 `CaseEditorPanel.vue` 第 1 列为复选框列，支持表头全选、半选（`indeterminate`）与单行选中。
- [x] 添加已选考题状态提示卡片（已选 $N$ 题、一键清空选择、反选）。
- [x] 在 `EvaluationStudioPage.vue` 维护 `selectedCaseKeys` 状态，联动右上角「发起评测打擂」按钮文案。
- [x] 切换当前题库（Suite）或版本时，自动重置已选用例集合，防止跨题库脏数据。
- [x] 跑通 `vue-tsc --noEmit` 与 Vitest 单元测试。

**开发与验证证据：**
* 在 `SelectiveEvaluation.spec.ts` 中完成行点击、全选、反选、清空以及主按钮动态文案 `发起评测打擂 (1 题) →` 的断言测试，测试 100% PASS。
* `pnpm test:run src/modules/evaluation/` 23 项测试全量通过。

---

### Task 8.4：端到端全链路验证与回归测试
在前后端联调环境下，确保勾选 1~2 道用例后发起评测，评测大厅仅调度执行这几道题，并在打擂完成后的详情与对比 PK 中正常呈现。

**状态：** 已完成（done）。
**完成标准：** 前后端类型安全、接口契约一致、单测覆盖完整，文档无任何硬编码绝对路径。
**涉及位置：**
* `apps/platform-api/`
* `apps/platform-web/`
* 全局文档规范校验

- [x] 验证后端 `create_run_record` 与 `create_matrix_runs` 在携带 `case_keys` 时的真实入库与用例过滤能力。
- [x] 验证前端单配置与多模型矩阵打擂下的 `case_keys` 透传完整性。
- [x] 执行全套自动化代码质量检查（`check_docs.py`、`vue-tsc`、前端 Vitest、后端 Pytest）。

**开发与验证证据：**
* 前端类型检查：`cd apps/platform-web && pnpm typecheck` -> `TypeScript: No errors found`。
* 前端评测工坊单测：`cd apps/platform-web && pnpm test:run src/modules/evaluation/` -> 6 passed (6), 23 passed (23)。
* 后端评测工坊单测：`uv run --directory apps/platform-api pytest tests/test_evaluation_studio.py` -> 1 passed in 1.39s。
* 文档规范检查：`python3 scripts/check_docs.py` -> `Documentation checks passed.`。
