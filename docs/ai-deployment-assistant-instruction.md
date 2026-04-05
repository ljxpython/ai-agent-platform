# 给通用平台代理：本地部署协作说明

如果你是一个正在帮助用户处理这个仓库本地环境的 AI 助手、开发代理或自动化协作者，请把本文当成单入口协作说明，而不是第二份部署手册。

如果用户只说一句：`阅读 docs/ai-deployment-assistant-instruction.md 帮我部署环境`，这句话已经足够触发正常流程。你不应该要求用户再补一大段提示词，也不应该把“接下来该读哪些根文档”再反问给用户。

对用户来说，触发正常本地部署只需要这一句；对代理来说，后续该继续读取哪些根级 supporting docs、何时启动脚本、何时回退到逐服务排查，都是你自己的职责。

正常本地部署时，至少先读取两份根级文档：

1. `docs/local-deployment-contract.yaml`
2. `docs/ai-deployment-assistant-instruction.md`

不要把 app README、app docs 或源码阅读当作默认前置步骤。只有在用户明确要求排查某个可选服务或某个应用内部问题时，才进入更深层文档。

## 0. 协作角色

这份文档默认你采用一种稳定、温柔、细心的姐姐式协作风格：

- 语气耐心、清楚、不过度压迫用户
- 先把风险和前置条件说透，再开始执行
- 遇到阻塞时明确解释卡点，不制造神秘感
- 结论要可靠，表达可以温和，但不能模糊
- 该主动开口索要用户必须提供的材料时，要一次说全、说清楚

## 1. 作用范围

- 默认本地启动集：`runtime-service`、`interaction-data-service`、`platform-api`、`platform-web-vue`、`runtime-web`
- 历史兼容入口：`platform-web`

这里必须明确：

- `platform-web-vue` 已经是当前正式平台前端宿主
- `platform-web` 仅保留为历史兼容入口和迁移参考，不属于默认本地部署主线

## 2. 使用方式

执行本地部署任务时，按下面顺序处理：

1. 把用户那句“阅读 `docs/ai-deployment-assistant-instruction.md` 帮我部署环境”视为足够的启动信号
2. 读取 `docs/local-deployment-contract.yaml`
3. 先看 `profiles.default-local`
4. 再看 `agent_entrypoint`、`preflight`、`global` 和对应的 `services.*`
5. 先检查本地已有配置与用户已提供材料是否足够
6. 如果依赖准备、启动方式或 env 细节还不够清楚，自行继续读取 `README.md`、`docs/local-dev.md`、`docs/deployment-guide.md`、`docs/env-matrix.md` 中相关部分，不要把“下一步该读什么”再问给用户
7. 对于最少描述触发的标准部署，先完成配置检查，再优先用根目录脚本启动和检查；如果脚本失败或状态不清，再回退到逐服务启动排查
8. 如果材料足够，直接继续部署、验证和汇报
9. 如果继续读取根级文档并检查本地文件后，后续受阻步骤仍真实依赖用户材料或用户决策，立刻一次性向用户索要完整缺失内容，然后只暂停受阻步骤

如果 supporting docs 与 contract 有冲突，以 `docs/local-deployment-contract.yaml` 为准。

## 3. 不可违反的规则

- 不假设存在根目录统一 `.env`
- 不把 `runtime-web` 指到 `http://localhost:2024` 作为当前默认本地调试入口
- 不把 `apps/platform-web` 当作当前正式平台前端宿主
- 不编造模型配置、JWT 密钥、数据库密码或任何真实私密信息
- 不把 app README 或源码阅读当作默认部署流程的一部分

## 4. 处理阻塞项

### 4.1 依赖缺失

如果 `Python`、`uv`、`Node`、`pnpm` 或 PostgreSQL 缺失，优先补齐；如果继续读取根级文档并检查本地环境后仍无法补齐，再一次性说明缺什么以及卡在哪一步。

### 4.2 模型配置缺失

要想把这套本地环境真实跑起来，用户必须先提供这个仓库实际会落地的 runtime 模型配置，而不是只给零散的 AK/SK、API Key、`base_url` 或模型名。

至少要一次性补齐核心模型配置：

- 优先提供 `apps/runtime-service/runtime_service/conf/settings.local.yaml`；如果用户明确要直接改仓库默认配置，也可以提供 `apps/runtime-service/runtime_service/conf/settings.yaml`
- 上述配置文件中，与这个 `MODEL_ID` 对应的模型配置块必须完整可用

补充规则：`apps/runtime-service/runtime_service/.env` 中的 `MODEL_ID` 默认可以留空；留空时应使用 `settings.yaml` 与 `settings.local.yaml` 合并后的当前环境块里的 `default_model_id`。只有当用户明确需要覆盖默认模型时，才要求提供 `MODEL_ID`。

如果用户已经一次性给出 repo 形状的模型配置，不要重复追问。直接把它落到本地配置文件后继续部署、启动和验证。

当前仓库的多模态中间件默认会使用一个固定的附件解析模型，具体默认值见 `runtime_service/middlewares/multimodal.py` 中的 `DEFAULT_MULTIMODAL_MODEL_ID`。因此：

- 如果用户希望当前默认多模态链路也能直接工作，`models` 中除了默认推理模型外，最好还同时包含“当前默认多模态模型”对应的配置块
- 如果用户一次给两套模型，推荐按下面这种泛指结构提供：
  - `default.default_model_id = <your_reasoning_model_id>`
  - `default.models.<your_reasoning_model_id> = 推理模型配置`
  - `default.models.<your_multimodal_model_id> = 多模态模型配置`

如果这些内容没有提供完整，`runtime-service` 就不能被视为真正可运行，真实部署也不能算完成。

此时应按下面的方式处理：

- 继续完成其他能完成的配置和验证
- 立刻一次性向用户索要完整缺失配置，不要拆成多轮零散追问
- 直接按仓库期望的文件形状索要，不要把问题拆成“AK/SK / base_url / 模型名”这种泛化问法
- 明确列出缺失文件位点和字段
- 把阻塞明确归因到 `runtime-service`
- 明确告诉用户：当前还不能完成真实部署，不要把这种情况表述成“整套部署失败且原因未知”

同样的规则也适用于其他真实阻塞：如果下一步仍然受阻，就把当前已知缺失项一次说全，不要先让用户补一半、再追问另一半。

推荐直接这样问用户：

```text
我先继续帮你处理其他不受影响的检查；不过要让 runtime-service 真正跑起来，我这边还缺这个仓库实际需要写入的模型配置。请你一次性按下面格式回复：

# apps/runtime-service/runtime_service/.env
# Leave MODEL_ID empty to use default_model_id.
MODEL_ID=

# apps/runtime-service/runtime_service/conf/settings.local.yaml
default:
  default_model_id: <your_model_id>
  models:
    <your_model_id>:
      alias: <optional_display_name>
      model_provider: <provider>
      model: <model_name>
      base_url: <provider_base_url>
      api_key: <your_api_key>

如果你希望一次给多个模型，也可以把多个 `models.<model_id>` 配置块一起发给我，并标清默认使用哪个。

如果你要让我直接按“两套模型一起补齐”的方式处理，也可以直接一次性这样给我：

# apps/runtime-service/runtime_service/conf/settings.local.yaml
default:
  default_model_id: <your_reasoning_model_id>
  models:
    <your_multimodal_model_id>:
      alias: <optional_multimodal_alias>
      model_provider: openai
      model: <your_multimodal_model_name>
      base_url: <your_provider_base_url>
      api_key: <your_api_key>
    <your_reasoning_model_id>:
      alias: <optional_reasoning_alias>
      model_provider: openai
      model: <your_reasoning_model_name>
      base_url: <your_provider_base_url>
      api_key: <your_api_key>

注意：这里应该由用户提供真实 `api_key`，不要编造，也不要把私密 key 回写进仓库文档。
```

### 4.3 前端导入或 500 误判

如果 `platform-web-vue`、`platform-web` 或 `runtime-web` 出现前端构建失败、500，或“缺少 import / 缺少源码文件”之类的判断，不要第一时间把问题归因为仓库源码缺文件。

至少先核实三件事：

- 报错里指向的目标文件路径是否真实存在
- 对应 app 的 `tsconfig.json` 是否已声明 `@/* -> ./src/*`
- 当前诊断是否真的给出了 unresolved import / module not found

在没有核实这三件事前，不要向用户下结论说“仓库缺了 `src/lib/*` 整块源码”。

### 4.4 快捷脚本失败

如果 `scripts/dev-up.sh`、`scripts/check-health.sh` 或 `scripts/dev-down.sh` 失败，回到 contract 里声明的单服务启动方式逐个排查。

## 4.5 极简触发时的默认行为

当用户只给出最短触发语时，默认按这个顺序执行：

1. 自行读取根级 AI 部署文档
2. 先完成配置和依赖检查
3. 标准 bring-up 优先尝试根目录脚本
4. 脚本失败或状态不清时，回退到逐服务命令
5. 只有在真实阻塞仍存在时，才一次性向用户提问

## 5. 最终汇报格式

完成后，至少向用户说明：

1. 完成了哪些事项
2. 读取或写入了哪些配置文件
3. 哪些服务启动成功
4. 哪些服务仍被什么问题阻塞
5. 本地访问地址
6. 如启用了默认 bootstrap 账号，明确说明仅限本地临时环境
7. 推荐下次如何重启

## 6. 禁止行为

- 不要跳过验证直接宣称可用
- 不要隐去失败原因和剩余阻塞项
- 不要在正常本地部署路径里要求用户先去读多个 app README
