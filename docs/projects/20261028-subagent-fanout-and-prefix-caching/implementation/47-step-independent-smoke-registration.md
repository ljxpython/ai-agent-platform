# Step5独立模型兼容性登记

2026-10-29，首次调用前。v37应用无变更，478项扩大回归及源码整合/Runtime重启见45号；Kimi完整交付但原质量4/5的结果保留于46号。不再同配置重复Kimi烟测。

使用当前目录已配置的xiaok `step-5-preview`，model ID `7a1034b5-ac3c-4d12-aa5c-5df5afed7ddf`，配置窗口131072、输出8192。原DSH SHA、原题和五项评分逐字不变，主50/子16/三并发/工具100、费用关闭/Usage开启不变。供应商真实部署窗口/指纹未知；窗口与Kimi256K不同，单独报告绝对用量，不混算降幅。

只执行一次独立正式Web→API→Runtime新Thread完整任务，失败全部保留，不替补、不混入正式组。仅通过后才冻结同模型/窗口/实现的新六次，再nanobot及Final。无提示词、Schema、权限、报告/原文交接或调用额度变更，不发送评分答案。

冻结清单`.local-stack/v38-step-smoke-17-manifest.json`，1131份公共源码及环境/脚本/审计/测试摘要；SHA256 `6fba07eded114969dcf6b0ffa1c1f162851f36a8866ede90d514b53e1355aa6f`，登记`2026-10-29T11:57:16.279946+00:00`。UI预检已确认step-5-preview/xiaok、Pro100步、8192且未发送。存在启动意图时不自动重发。

## 结果：模型请求前配置拒绝

Run `d4edef39-cdfa-45a2-95a9-ef8418e6ae8b`，Thread `b4116a9e-ffd8-4c9a-bffe-fc7058046022`，error。工厂装配 `resolve_tool_output_limit()` 经 `_context_limits()` 返回 `runtime.context.output_budget_exceeded`；该模型在当前受信解析器中属于未知系列，安全输出上限为4096，请求8192超限。已用所属Runtime Python只读调用 `resolve_model_max_output_tokens()` 复核为4096，不修改目录窗口或绕过保护。

调用数0，Usage为not_recorded，未产生可评分报告；上下文、引用、交接与最终流审计均不适用。旧sample审计因空state缺messages失败、context审计因0profile失败的原日志保留，不将它们改成通过。原始`.local-stack/v38-step-smoke-17-terminal.json`，SHA256 `05988e2e8a40d5f2318823412ea2ee96d8b12c51cc47caa11f387c6b1bf62e6f`；复核`.local-stack/v38-step-smoke-17-review.json`。

本次失败保留且不计入模型质量或正式六次。后续以合法4096输出新登记独立配置，原题/评分/应用不变，不替补本记录。
