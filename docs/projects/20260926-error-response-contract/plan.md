# 错误响应统一 - 实施方案

> 版本：2026-09-26执行细则。用户已同意方案；本轮仅完成文档。本专项只改platform-api/platform-web，Runtime/GraphHarbor完全不变。

## 1. 范围与责任

平台公开HTTP失败使用统一Envelope；平台adapter负责解释不同上游格式，前端负责读取和展示。
覆盖普通JSON、上传、下载、SSE建立前4xx/5xx。成功响应和已开启SSE不改。
浏览器离线、用户取消、反向代理HTML错误只能客户端兜底，不能假装存在服务端code。
不改JWT、权限裁决、ID生成算法、数据库、SDK版本/补丁或Runtime/GraphHarbor任一文件/配置。

## 2. 现有代码与已确认缺口

| 位置 | 事实和工作 |
|---|---|
| platform-api core/schemas.py、core/errors/{base,payload,handlers}.py | 已有公共结构/handler，直接扩展；不新建错误框架 |
| adapters/langgraph/sdk_client.py | create_runtime_upstream_error当前返回PlatformApiError并附原始upstream_detail；改为来源明确的UpstreamServiceError和安全字段 |
| adapters/langgraph/runtime_client.py | JSON/文件/流握手经过_raise_for_status；SDK线程/运行适配器经过raise_runtime_upstream_error |
| modules/runtime_gateway/application/service.py | create_thread/reconcile_pending_thread捕获UpstreamServiceError；必须保留对账及原始上游4xx/5xx分类 |
| adapters/langgraph/runtime_gateway_upstream.py | dear_memory再次限制错误；必须保留memory机器码、已清洗details和恢复诊断，不能重新抹掉 |
| platform-web services/langgraph/client.ts | normalizeProtocolErrorResponse覆盖error对象，导致extra丢失 |
| services/threads/session.service.ts | create读取error.extra.thread_id，read自行拼错误字符串，需共用解析器 |
| utils/http-error.ts、services/runtime-gateway/workspace.service.ts | 两套字段解析需收敛；已有状态/中文提示映射保留 |
| services/langgraph/client.ts → createLanggraphClient | 当前未显式禁用SDK重试；通用写调用有重放风险，固定maxRetries:0，与Session现状一致 |

代码路径上表省略的后端前缀为 `apps/platform-api/src/platform_api/`，前端为 `apps/platform-web/src/`；任务文档列完整落点。
SDK 1.10.2 的HTTPError保存status/text；Protocol HTTP transport优先读顶层message。纯内存SDK探针已验证保留error对象可通过HTTPError正文传递，不需要升级SDK。
源码读取位置：安装包 `dist/utils/async_caller.js`、`dist/client/stream/transport/http.js`；实施测试使用现有公开Client，不改node_modules。

## 3. 公开结构

```json
{
  "error": {
    "code": "workspace_directory_changed",
    "message": "Directory changed",
    "details": []
  },
  "request_id": "req-example"
}
```

- error.code/message必填非空字符串；details必填数组；extra有内容才返回。
- request_id始终根级且与x-request-id头一致；不增加meta，不截取ID。
- 平台已有业务code保持原名，包括invalid_token/invalid_api_key等401码，不统一改成not_authenticated。
- 422详情为loc数组、type字符串、message字符串；禁止input、ctx和原始输入。
- 业务判断只依据HTTP status/code，不依据message；新平台码snake_case，既有点分码不改。
- 不收窄ErrorBody.details现有Pydantic类型以免破坏内部调用；安全标准化在handler/上游转换处完成。

## 4. 确定性的上游转换

### 4.1 解析输入

仅从以下四个候选中取第一个含“已登记非空code”或“非空message”的对象：error对象、detail对象、顶层对象；最后处理字符串detail。
对象必须是Mapping且不能是数组。已选对象中的code/message/details不能与其他层交叉拼凑。
字符串只有与error-catalog登记码完全相等时才作为code；其他字符串/HTML/异常str不公开。
未知对象、未知码、字段类型错误按状态走fallback。不得用前缀匹配允许任意code。
422原生detail数组作为校验详情单独识别。cursor recovery按清单固定位置提取。

### 4.2 来源状态和公开状态分离

扩展已有UpstreamServiceError，不新建并行基类：
- 保留upstream/code/status_code参数；增加可选details/extra/headers和upstream_status_code。
- status_code用于对外HTTP；upstream_status_code记录真实收到的HTTP状态，无响应为None。
- extra由平台生成，合并安全清单，来源upstream固定langgraph；有来源状态才输出upstream_status_code。
- create_runtime_upstream_error统一返回UpstreamServiceError（仍是PlatformApiError子类）。
- 已经是PlatformApiError的异常继续原样抛出，不重复转换。
- 超时：504/langgraph_upstream_timeout；其他HTTP传输失败：502/langgraph_upstream_unavailable。
- 现有从异常字符串ValueError推断400的支路改为固定fallback文案，不公开异常原文；没有可信HTTP状态时按502处理。

| 原因 | 公开HTTP | code/message |
|---|---|---|
| 上游401 | 502 | runtime_delegation_rejected / Runtime authentication failed |
| 上游403 | 403 | 清单码或forbidden / Permission denied |
| 上游422且无登记业务码 | 422 | validation_failed / Validation failed |
| 上游429且无登记业务码 | 429 | langgraph_upstream_rate_limited / Runtime request rate limited |
| 上游500—599 | 502 | 默认langgraph_upstream_request_failed / Runtime request failed |
| 上游已登记4xx | 来源HTTP不变 | 清单精确码、安全固定文案 |
| 其他上游4xx | 来源HTTP不变 | 调用者现有fallback_code / Runtime request failed |
| 平台自身PlatformApiError | 原status/code | 保留平台生成的业务含义及登记字段 |
| 平台未捕获异常 | 500 | internal_server_error / Internal server error |

唯一现役5xx业务码保留例外：`memory_storage_unavailable`来源503仍输出该code与固定Memory storage unavailable，公开HTTP为502，保证现有页面按code识别；不得扩大为任意上游5xx code透传。
所有来源HTTP都记录为upstream_status_code；客户端显示公开status，不把原始状态当登录状态。

### 4.3 extra白名单

精确规则见[error-catalog.md](error-catalog.md)。默认不输出上游extra、upstream_path或原始upstream_detail。
保留平台生成pending thread_id/reconcile_path，以及cursor_expired的upstream_detail.recovery=thread_snapshot。
对上游未知字段直接丢弃，不拷贝后再依赖敏感词过滤。
全局redact_runtime_private_fields仍服务成功JSON和SSE，不修改为错误专用allowlist。
dear_memory wrapper保留现有memory业务allowlist及固定Memory request failed文案；允许新增runtime_delegation_rejected和通用上游失败码，传递已清洗details，不恢复原正文。

### 4.4 校验信息与响应头

- details最多20项；loc最多16段，每段只接受非bool整数或字符串（最大128字符），非法项丢弃。
- type只接受ASCII字母/数字/下划线，最长64；否则validation_error。
- message固定：missing→Field required；extra_forbidden→Extra field not permitted；其他→Invalid value。
- 上游登记的非422错误details=[]；不回显任意message或原输入。
- PlatformApiError自有details保留现有loc/type/message结构；当前业务生产者只有memory验证，使用相同安全规范。
- Retry-After只在429/503保留：非负十进制整数或标准库可解析HTTP日期，最大128字符，拒绝CR/LF；不自动重试。
- Allow只在405保留，按标准HTTP方法token拆分过滤；WWW-Authenticate只保留平台自身401产生的值，拒绝CR/LF，最长512字符。
- 任何来源Set-Cookie/Authorization/Cookie/上游CORS头均不透传。
- 在现有payload builder/异常handler设置x-request-id，避免意外异常绕过response middleware时丢头；异常日志只用安全code、请求ID、异常类型与栈位置，不打印异常正文/locals。
- request_context middleware用try/finally覆盖整个call_next，保证异常路径reset；request.state保留原ID供外层500 handler读取。
- 正常来源Origin的4xx/500必须有正确CORS访问头；在main.create_app集成验证。固定在request_context现有中间件内捕获普通Exception（不捕获取消/BaseException），委托统一500响应构造函数；这样错误响应经过现有CORS层，create_app仍返回FastAPI。保留最外层handler作为兜底并共用构造逻辑，不新增中间件框架。不得以关闭CORS检查掩盖500。
- 对外请求ID展示只接受1—128字符ASCII字母/数字/点/下划线/连字符，其余不展示；本期不改变后端既有ID生成/接收算法。

## 5. 会话创建与对账的确定行为

当前create_thread捕获UpstreamServiceError但公共转换返回父类，这是必须补的组合缺口。

1. 已收到上游4xx（包括最终公开变成502的内部401）：按upstream_status_code判断确定拒绝，清理pending；清理失败走原503 thread_provisioning_unconfirmed。
2. 未收到响应或收到5xx：保留pending，附平台生成thread_id/reconcile_path；沿用现有主动探测。
3. 主动探测返回同ID且权限/归属正确：标ready并返回成功；标ready失败返回503待对账。
4. 探测404、超时、签发失败：保留原可对账异常及ID；不得造新Thread重试。
5. reconcile对上游404仍返回pending；其他拒绝不泄漏他人数据。
6. status映射之后禁止再仅用exc.status_code<500判断是否安全清理；必须用来源状态。
7. 图片/文件Content-Type不支持时，删除动态回显的content_type，保留已有runtime_invalid_*_response code与固定安全message。

## 6. 前端实施规则

### 6.1 单一字段解析

扩展utils/http-error.ts现有函数，不另建service：
- 同步extractPlatformHttpError输入优先级：Axios response.data对象 → SDK.text JSON对象 → 已规范化Error自有字段 → 直接Envelope。
- SDK.text最大64KiB，超过或非法JSON使用fallback；error对象优先于旧顶层code/message；兼容根级request_id及已有meta.request_id读取。
- 返回status:number|null、code?、message、requestId?、details?、extra?、cancelled:boolean。
- status依次取response.status、status、statusCode，须为100—599整数；Protocol错误只有文本时保留原严格状态提取正则作为兜底，不解析机器码。
- Axios ERR_CANCELED/DOM AbortError标cancelled=true；不新增toast。
- 网络错误固定“网络连接失败，请检查网络后重试”；非JSON HTTP固定“请求失败（HTTP N）”；不能显示HTML、HTTPError拼出的原JSON或堆栈。
- unwrapPlatformHttpError只在Blob.size≤64KiB时读取文本，然后调用相同解析；返回Error保留机器字段，取消保持取消语义。
- 上游error.code与Axios自身code分开；有HTTP响应时不得把ERR_BAD_RESPONSE冒充业务码。
- resolvePlatformHttpErrorMessage与normalizeRuntimeGatewayError复用解析；保留原业务中文规则，404只有route_not_found提示接口缺失，其他404提示资源不存在/不可访问。
- 新增同文件formatPlatformHttpErrorMessage：非取消且有合法requestId时在既有可见错误文案末尾加“（请求编号：ID）”，避免重复追加；纯extract不修改message。
- workspace服务、Session失败提示复用此格式化；不做全站组件改造/全站i18n，已有memory页面按code显示专用提示保持原状。

### 6.2 SDK无损适配

normalizeProtocolErrorResponse保留原error对象，追加顶层message/code；顶层message是安全文案加合法请求编号（供Protocol文本错误显示），nested error.message保持纯安全文案。
仍删除content-length/content-encoding/transfer-encoding。response.ok不克隆读取，成功下载和流不缓存。
createLanggraphClient设置callerOptions.maxRetries=0；Session已有0保持。401授权刷新最多一次且幂等键不变，不引入写请求网络重试。

SDK Protocol流握手路径会抛普通Error并丢结构字段；本期保证安全文案和状态兜底，不承诺该SDK分支拥有details/extra。410恢复需要结构信息的问题明确交接SSE专项，禁止改SDK/Runtime来暗中扩范围。

### 6.3 消费者改动

- session.service.create共用解析器读取extra.thread_id，校验标准UUID格式，再保存用户+项目隔离pending ID。原错误保留status/code/requestId/extra。
- session.service.read把失败Response转成规范Error；不再自己只看顶层detail。
- runtime-gateway/workspace.service.ts删除重复字段解析，保留现有kind/中文业务决策。
- threads/workspace.service.ts沿用unwrap；useArtifacts的workspace_directory_changed只重读首页一次，不能变成写重试。
- skills页面与terminal消费者保留现有码；详见清单，不顺带重构页面。

## 7. 发布与兼容

实施顺序：前端无损解析及禁止隐式重试 → API转换/对账/headers → 组合和HTTP验收。
不升级SDK、Runtime或GraphHarbor，不改数据库。本期交付代码和隔离验证；生产部署排期/外部客户迁移不在本专项授权内，不阻塞开发。

验证组合固定为：实现前API+新Web；新API+新Web。旧Web+新API必须作为风险检查，旧Web已有字段丢失问题，不允许该组合成为正式上线顺序。
若旧缓存Web仍在使用，API切换前要求刷新/重载新版Web；静态资产版本和已打开会话按现有发布机制处理，不建新的热更新服务。
实现者在verification记录实施前后git revision、脏工作区diff标识、SDK锁定版本、测试环境URL；这是证据填值而非新增设计决策。
回退API到实施前版本时保留新Web无损解析，重测pending/401/409/Blob；该回退会恢复旧安全输出缺口，只能隔离测试或维护止流环境演练，不能默认为生产恢复服务方案。安全问题上线后优先前滚。
不运行git commit/push，不修改Runtime配置来适配测试；需要Runtime服务端修复时记录为本专项外依赖。

## 8. 已确认决策

| 编号 | 决策 |
|---|---|
| E01 | 只统一平台公开出口；Runtime/GraphHarbor完全不改 |
| E02 | 保留根级request_id与响应头 |
| E03 | 精确登记code及extra，未知正文不公开；按来源处理，不全局删平台业务extra |
| E04 | 内部401→502；403保留；上游5xx→502；超时504；平台pending503保留；内部来源状态独立 |
| E05 | SDK保留error对象，补顶层message/code；普通HTTP组合已做有限探针，正式测试随实施 |
| E06 | 本期只管HTTP及流建立前错误；流内和410自动恢复归SSE |
| E07 | 在现有公共错误提示附请求编号；保留业务中文提示，无全站翻译/组件改造 |
| E08 | Web先API后，Runtime/DB/SDK不变；本期代码交付和隔离验证，生产发布另行授权 |

已批准方向下的实现细则不需要重复讨论；实现中若发现必须突破Runtime硬边界或公开契约范围，再单独提出范围变更。
