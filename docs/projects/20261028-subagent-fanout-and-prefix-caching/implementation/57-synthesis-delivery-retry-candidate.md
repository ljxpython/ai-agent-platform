# 主级交付重试：离线复现与候选

2026-10-29，T5.3/T5.7。当前只有私有离线候选，应用源码保持56号冻结；不是正式质量通过或Final。

## 事实与最小修复范围

56号首轮的三个子报告成功；主级反复返回普通正文，`ResearchSynthesisMiddleware._retry()`将它们隐藏并追加同一SystemMessage。21份重复反馈留在持久状态，后续请求仍带41个Schema；主峰虽仅30,094，累计输入明显增长，最终没有合法交付。当前已证实的是交付协议重试不收敛；不能据此断言模型供应商或所有可用工具就是唯一原因。

核对官方[工具强制选择](https://docs.langchain.com/oss/python/langchain/models#forcing-tool-calls)、[结构化输出](https://docs.langchain.com/oss/python/langchain/structured-output)及`ModelRequest`参考，并只读检查当前安装的LangChain factory：ToolStrategy绑定`tool_choice="any"`，会附加报告Schema，但仍保留执行工具；仅改request.tool_choice不能覆盖该SDK分支。

候选沿用已批准的最终组合契约和既有`disable_tool_calls()`：模型一旦尝试交付而进入格式/字段纠错，后续只保留ResearchSynthesis Schema；同一Run的最新校验反馈使用固定消息ID覆盖，避免逐轮追加。若模型在交付阶段仍返回执行工具，整批拒绝并纠正，不能因为工具节点已注册就执行。发现引用、原句验证、报告上限和调用预算都保留；不把普通正文直接解析为成功报告，不新增模型层或额度。

应用目标位置：`apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/synthesis.py`。这属于既有交付路径的收敛修复，未新增公共Schema/权限或来源范围；按已有开发授权推进，待本组固定采样结束后才接入。

## 私有离线样例

文件在所属Worktree的`.local-stack/`：`v46-candidate-synthesis.py`、`test_v46_candidate.py`、`run-v46-candidate-tests.py`。独立Python进程仅在进程内装载候选模块，服务继续加载未修改的正式源码；没有真实模型请求。

- 原实现：2 failed / 5 warnings，20.51秒，`v46-candidate-red.log`。分别复现交付后仍暴露执行工具，以及重复正文造成三份反馈累积。
- 候选：2 passed / 2 warnings，0.95秒，`v46-candidate-green.log`。验证只剩报告Schema、违背Schema返回的读取工具不执行、最终报告合法，以及三次正文纠错只留一份当前Run反馈。

仅证明候选在两个有界图样例成立。尚未证明完整装配、跨Run/取消/预算/私有流回归或供应商实际兼容性，更不证明原五项与六次稳定门槛通过。正式组结束后将必要回归放入原测试文件、执行关联集和一次正式独立任务，再按原门槛验证；本组及历史失败全部保留。
