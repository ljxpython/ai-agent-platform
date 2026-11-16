# 平台内置助手前端开发交接

## 1. 先理解交付目标与当前可用程度

用户在任意平台页面打开助手，可以咨询用法、聊天和查资料，也可以从错误弹窗把诊断信息交给助手。助手读取用户有权查看的数据后返回判断、证据和建议。用户可重开历史继续聊；如果助手提出有副作用的业务动作，必须由用户选择“执行/不执行”。读操作不弹确认。

**本次开发者负责后端、Agent和本交接文档；前端同事负责前端代码、组件选型与浏览器验证。** 本文不给前端规定组件拆分，只规定必须一致的接口和行为。已有聊天组件可供参考，如何复用由前端同事决定。

**当前为交接初稿，不是后端已就绪通知。** 现有平台的Thread、运行、历史、审批协议已做源码核对；新platform_assistant图、数据工具和写工具强制审批尚未实现/验证。前端可据此了解流程和既有协议，但正式联调前本次开发者必须补齐第9节交付项。不能把示例中的业务工具名当成已发布工具。

进度唯一来源为[tasks.md](tasks.md)的T07；整体方案见[plan.md](plan.md)，测试要求见[verification.md](verification.md)。

## 2. 用户流程与页面上下文

| 场景 | 前端行为 | 后端/Agent行为 |
|---|---|---|
| 打开全局助手 | 显示当前用户/项目的助手会话，可新建或继续；未选择项目时提示选择 | 通过既有授权链绑定会话，不借管理员身份替用户查询 |
| 从错误现场打开 | 展示即将发送的诊断摘要，用户发送后开始调查；仍支持粘贴诊断包 | 校验诊断目标，读取获准运行/日志/数据库 |
| 普通聊天/使用咨询 | 正常输入与流式展示，不增加模式选择负担 | 按需查询文档/资料，普通聊天不强制用工具 |
| 查询来源 | 展示可理解的来源与版本/时间，无权限或过期时解释 | 复核来源访问权，不能仅凭URL/证据ID开放原始内容 |
| 待执行动作 | 显示具体动作、对象、参数、影响及执行/不执行 | 原生interrupt持久等待；批准前不调用写工具 |
| 重开历史 | 读取已有会话和消息，继续沿原Thread | 使用持久checkpoint恢复会话；新Thread不自动继承长期记忆 |

助手Thread与被诊断Thread分开；原失败Run不可由打开助手自动重跑。助手会话按用户、项目和Agent绑定，切换账号/项目不能复用之前的消息、待审动作或来源缓存。全局入口不代表全局数据权限。

诊断上下文至少应说明：当前页面、错误发生时间、已有错误摘要，以及可获得的project/thread/run/request/trace标识。缺少字段允许发送；平台Trace和模型Trace分别保留类型。第一版可复用现有诊断Markdown作为消息正文，不要求前端推断根因，也不发送Cookie、令牌、完整环境配置或数据库凭据。若后端新增结构化字段，必须在最终交接补准确schema及兼容方式，不能在configurable中自行注入内部身份字段。

## 3. 已有平台接口与接线入口

以下路径来自现有API源码，前缀统一为 /api/langgraph。实际origin取平台配置，不能硬编码开发端口。平台请求使用现有授权fetch和x-project-id；新助手沿相同链路运行。

| 行为 | 已有接口/入口 | 注意 |
|---|---|---|
| 创建助手会话 | POST /threads；session.service.ts的create | 使用真实平台Agent ID和执行graph_id；新图拟名platform_assistant，尚未注册 |
| 列出历史会话 | SDK threads.search/count；session.service.ts的list/count | metadata筛选仅是筛选条件，权限仍由后端执行 |
| 读取会话/状态 | GET /threads/{thread_id}、GET /threads/{thread_id}/state | 当前状态包含恢复/待审所需事实；先读再决定动作 |
| 历史checkpoint | POST /threads/{thread_id}/history | 按需读取，不让历史快照覆盖当前实时状态 |
| 持久消息 | GET /threads/{thread_id}/messages | 分页、排序与消息投影沿现有消息服务 |
| 发送/恢复 | POST /threads/{thread_id}/commands，或标准runs/stream路径 | 选既有客户端支持的路径；不额外写第二套运行协议 |
| 事件订阅 | POST /threads/{thread_id}/stream/events及既有SDK控制器 | 流状态与业务动作分开，断流不等于运行失败 |
| 查询Run | GET /threads/{thread_id}/runs/{run_id} | 受理回执不等于已执行成功 |
| 停止 | POST /threads/{thread_id}/cancel及stop-requests查询 | 沿现有停止回执，不把取消请求成功等同执行已终止 |
| 运行诊断 | GET /threads/{thread_id}/runs/{run_id}/diagnostics | 这里传目标Thread/Run，不能误用助手运行ID |
| 删除历史 | DELETE /threads/{thread_id} | 沿既有ACL/生命周期；前端不能只删本地消息 |
| 审批恢复 | commands的input.respond或runs的command.resume | 使用真实interrupt ID，不能覆盖运行配置 |

可直接阅读的源码（相对仓库根）：
- apps/platform-web/src/services/langgraph/client.ts：授权、API base、命令幂等键。
- apps/platform-web/src/services/threads/session.service.ts：创建、历史、列表、恢复和删除。
- apps/platform-web/src/modules/chat/run-actions.ts：SDK命令转换与动作状态。
- apps/platform-web/src/modules/chat/approvals.ts：action_requests/review_configs解析及决策构造。
- apps/platform-web/src/modules/chat/composables/useChatSession.ts：现有会话控制器接线示例。
- apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py：注册路径。
- apps/platform-api/docs/standards/runtime-gateway-interface-standard.md：既有平台契约。

这些是协议参考，不要求前端照抄整个ChatSession或采用某个抽屉。

## 4. 写操作：执行/不执行

写工具即使已经授权也必须暂停；正常只读SQL、日志和文档读取不触发审批。前端不允许“自动执行全部”或把full_access解释为本助手的写审批豁免。

以下为**沿现有batched审批协议构造的示意报文**，不是本项目真实运行结果。example_update_setting仅用于说明写工具交互，不是已发布业务动作。真实工具名称、参数schema和影响摘要由后端交付。

待审对象示意：

```json
{
  "id": "interrupt-from-current-state",
  "value": {
    "action_requests": [
      {
        "name": "example_update_setting",
        "args": {"resource_id": "example-resource", "enabled": true},
        "description": "将指定对象的开关改为启用；等待用户决定"
      }
    ],
    "review_configs": [
      {
        "action_name": "example_update_setting",
        "allowed_decisions": ["approve", "reject"]
      }
    ]
  }
}
```

用户选择“执行”后，标准恢复正文示意：

```json
{
  "assistant_id": "platform_assistant",
  "command": {
    "resume": {
      "interrupt-from-current-state": {
        "decisions": [{"type": "approve"}]
      }
    }
  }
}
```

用户选择“不执行”时，同一位置改为：

```json
{
  "decisions": [
    {"type": "reject", "message": "用户选择不执行"}
  ]
}
```

若使用commands入口，遵循现有转换后的协议：

```json
{
  "id": 1,
  "method": "input.respond",
  "params": {
    "resume": {
      "interrupt-from-current-state": {
        "decisions": [{"type": "approve"}]
      }
    }
  }
}
```

接入要求：
- interrupt ID必须来自当前服务端state/事件。多个interrupt按ID映射，每组decisions按该组action_requests顺序逐项对应，不能漏项或一键默认批准。
- 只提供执行/不执行；本期不提供edit参数审批。要改变参数应重新生成动作并再次确认。
- 不执行可使用固定拒绝文案，不强迫用户写理由；现有helper要求非空message时用上面的固定值。
- 新决策产生新的Idempotency-Key；同一决策结果未知后的重试保留原key和原正文。协议整数id不是HTTP幂等键。
- 等待用户选择期间不显示“执行完成”；关页面、断网、超时和重启不会批准。
- 恢复前重新鉴权由后端完成；前端不能将approve权限按钮当后端授权。恢复可能产生新Run ID，应沿SDK刷新实际运行。
- 恢复不得附带新的input/config/context覆盖原任务。重复/过期/异项目审批显示明确失败，并重读状态。
- 点击执行返回受理后，继续观察工具/运行结果；结果未知时先查询，不能用新动作再次写入。
- 用户拒绝后显示“未执行”，助手可以解释或提供替代建议，不能偷偷换工具完成同一动作。
- pending卡片显示的参数和目标必须对应当前interrupt；禁止显示旧动作却批准新动作。

若本期尚无实际业务写工具，正式用户不会看到该示例操作；前端可使用后端提供的隔离测试夹具验收协议，测试工具不得发布到正式Agent目录。

## 5. 历史、记忆与状态

历史列表及重开是产品能力；同Thread多轮上下文是Agent记忆；两者都需要持久化。新会话默认不自动召回旧会话，没有新的长期个人画像入口。

前端关闭面板不等于停止任务。页面刷新后先获取会话state和Run状态，再恢复流/待审展示；不重复发送最后一条用户消息。历史待审只展示当前仍有效的interrupt，不把已批准/拒绝的旧记录重新变成按钮。

| 状态 | 交互行为 |
|---|---|
| 空会话 | 可输入，无需加载其他项目历史 |
| 运行中/取证中 | 显示进展，可按现有协议停止 |
| 等待用户决定 | 展示动作及执行/不执行，不能自动resume |
| 提交结果未知 | 保留原动作标识，回查状态，不新建重复动作 |
| 已完成 | 展示答复与证据；下一轮沿同Thread |
| 拒绝动作 | 明确本动作未执行；后续解释不是已执行 |
| 失败/取消 | 保留已产生内容，说明未完成和可用操作 |
| 权限被撤销 | 停止新的取数/来源访问，清理对应作用域可操作状态 |
| 瞬态网络故障 | 不误判为永久撤权，不清掉其他项目会话 |

不能只用isLoading一个布尔值表达所有状态。现有会话SDK/控制器可作为行为来源，具体UI由前端决定。

## 6. 证据、数据查询与权限展示

前端不直接连接数据库、Loki或源码宿主机。Agent读取schema、自行生成SQL并执行是后端工具循环；前端只展示允许公开的步骤和结果。是否展示完整SQL需按权限/脱敏决定，不能在普通用户界面泄露隐藏字段或字面值。

答案应能区分判断、证据、处理建议和未知项。第一版可使用消息Markdown引用；后端若增加结构化证据，最终交接必须列出准确字段、可用性和来源解析方式，不能让前端猜source_ref是可直接打开的URL。

来源缺失、过期、权限不足与服务暂不可用分别展示。引用链接也需权限，展示过的来源不能作为今后读取授权。普通用户默认没有源码读取入口；组件隐藏不是后端安全措施。

## 7. 错误与降级

统一使用平台错误Envelope及现有http-error解析。现有认证/权限/资源/冲突错误按其业务码处理，不将所有403导致全站登出，不把404统一解释成权限不足。新增助手错误码必须在最终交接逐项列明。

模型、Runtime或日志后端不可用时仍保留原诊断复制入口。前端不自动再启动另一个助手排查本助手。读取工具空结果或partial应显示缺口，不能把HTTP200解释为根因查明。

## 8. 前端验收要求（由前端同事执行）

1. 全局与错误入口可用；发送前上下文可见，粘贴路径可用，目标与助手会话分开。
2. 正常数据库/日志/文档读取不弹审批；显式写工具必须出现执行/不执行。
3. 批准前、拒绝后、关闭页面及断网时没有写副作用；批准后展示真实结果。
4. 历史重开/刷新/切页不重发消息，不复活过期审批；新Thread不串旧上下文。
5. 账号、项目和权限变化不混消息、来源或审批；拒绝和瞬态故障区分。
6. 正常流式、停止、结果未知、错误降级、移动视口和键盘操作可用。
7. 联合API/Runtime证据验证用户操作，不仅验证按钮点击和前端mock。

## 9. 交接完成条件

本次后端开发者必须在交付时补全以下内容；未具备时T07-A不能标完成：
- 实际部署/隔离环境地址的获取方法、Graph与平台Agent启用方式、测试角色/资料准备命令；不填写真实密码或密钥。
- 已实现接口列表、准确请求/响应/事件/错误/能力schema，清楚区分既有与新增。
- 新建→发送→取证→答复→历史续聊，以及写工具批准/拒绝的实际报文与运行证据。
- 服务重启恢复、撤权、结果未知、取消和故障降级的可复现步骤。
- 新增接口契约测试、API客户端示例、已知限制、数据/模型版本及后端验收结果。
- 若旧日志入口改变，对应前端调用者迁移方式和兼容情况。
- 前端只需依照文档即可开发；不能要求同事翻聊天猜字段或拿未实现接口联调。

后端交付验收与全栈联合验收分别记录。本交接初稿没有执行浏览器验收，不表示新助手已经可用。
