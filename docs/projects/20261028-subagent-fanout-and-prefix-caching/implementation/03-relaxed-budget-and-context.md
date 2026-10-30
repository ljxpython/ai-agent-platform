# 总用量与上下文占用分离

日期：2026-10-29。用户明确授权放宽100,000总预算，并希望参考dsh的49%上下文占用表现。

## 执行口径

- 取消100,000内完成的限制；仅本隔离栈将Run兜底设为1,000,000，不改产品默认值。预算保护、完整用量与超限记录仍保留。
- 新对照串行与委派各三次、每次新Thread；同模型、提示词、SHA、4096输出上限及上下文配置。旧三次失败保留为历史压力组，不与新额度混算降幅。
- 串行采样期间临时将Pro delegation设为False，终态后再恢复True；模式/角色开启已通过63项组合测试、2项opt-in跳过。
- 公共源文件9份SHA256与旧组一致，新采样前登记于隔离环境`.local-stack/relaxed-v1-manifest.json`；仅模式开关是两组被测差异。

## dsh源码核对

- `packages/client/ui-conversation/src/client/context-occupancy.ts:18-23`：当前投影或最近输入压力/配置窗口，再取整为百分比。
- `packages/llm/token-meter/src/usage-projection.ts:153-175`：投影使用最近供应商输入样本加后续surface变动；分子分母独立更新，不是单次请求的原子观测。
- `packages/llm/token-meter/src/turn-usage.ts`：累计用量汇总整轮所有请求尝试。因此5M累计、97%缓存与49%窗口占用是三个指标。
- `packages/compaction/compaction-basic/src/config.ts:19-23`：默认压力阈值0.8、保留比例0.16；49%不是自动压缩阈值。不能仅凭一次终态截图证明没有压缩或整轮峰值始终49%。

本平台测试直接记录每次模型已报告的input_tokens、峰值/解析窗口及root整理事件。缓存Token仍计入窗口；不承诺同供应商窗口、97%缓存率或5M以下的固定成本。长任务的输出质量与证据优先，实际总用量如实披露。

## 验证证据

等待新两组终态采集和逐项来源核对；不提前记为通过。

## T0.L：放宽预算后暴露的重复错误

v1首轮已知用量500,629仍未交付，repo参数漂移后反复请求；主动取消并保留非finalized原始证据。复用`middlewares/loop_detection.py`检测GitHub无artifact重复错误，`tools/errors.py`添加静态安全定位提示，`tools/github.py`澄清owner/repo含义。同步/异步循环与分页、三类错误隐私提示回归先失败后修复，相关95项通过。隔离环境开启现有循环保护，公共代码变化后改用v2重新采样两组，v1不作成功结果。产品默认开关保持不变，生产需显式启用后再做部署验收。

## 窗口分母核验

2026-10-29正式平台模型目录返回xiaok/deepseek-v4.1-flash配置窗口131,072；转发商`/models`仅给出模型ID，未声明窗口。官方Models & Pricing（`https://api-docs.deepseek.com/quick_start/pricing/`）当前将DeepSeek-V4.1-Flash-1017列为1M上下文；本地dsh `packages/llm/llm-deepseek/src/defaults.ts:6`默认也是1,000,000。不能把官方规格直接套用第三方转发商。当前对照保留配置131,072，以实际分母计算峰值，未提高目录窗口。公开页面副本和脱敏元数据分别保留在隔离`.local-stack/deepseek-official-models.html`、`provider-model-window.json`与`relaxed-model-window.json`。
