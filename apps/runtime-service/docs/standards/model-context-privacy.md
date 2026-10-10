# 模型上下文隐私保护

F05 只保护正式四图及其声明式子图、摘要、标题、推荐问题、自动记忆和视觉分析问题的模型外发文本。用户输入、工具执行参数、授权后的消息/文件/checkpoint 保留业务原文。设计、源码对照和验收见 [专项](../../../../docs/projects/20261009-agent-pii-redaction/README.md)。

## 部署配置

| 变量 | 默认 | 约束 |
|---|---|---|
| `RUNTIME_PII_REDACTION_ENABLED` | `false` | `true/false/1/0/yes/no/on/off`；非法值拒绝 |
| `RUNTIME_PII_TOKEN_SECRET` | 空 | 启用时必填、至少 16 字符；使用专用高熵随机密钥，建议至少 32 随机字节的安全编码，不复用 JWT/Provider/Langfuse 凭据 |
| `RUNTIME_PII_DETECTORS` | `email,api_key,national_id,credit_card,phone` | 可取非空子集；空/未知/重复拒绝，顺序由实现固定 |

在 Runtime API 与所有 Worker 的受控进程环境配置；platform-api 不持有这个密钥。浏览器不得传入政策。启动 lifespan 和正式构图均检查配置；Worker 构图取得已验证 Delegation 与执行 Thread，再绑定策略。仅导入/读取 schema 不发送模型请求。

`runtime/pii.py` 是唯一算法入口；`PiiRedactionMiddleware` 是最终模型请求副本保护，放在动态 system/Skills/Memory/Queue/工具装配后、容量校验前。新增独立模型入口必须接入同一函数并提供受信 scope，不能靠主图 wrapper 保护旁路。

五类是规则集合，不是完整 DLP。邮箱使用 ASCII 邮箱规则及中文边界；凭据是已知前缀/Authorization/结构化敏感标签；身份证为中国 18 位 mod-11/日期；卡号为 13–19 位 Luhn；电话为国内手机号及所支持的国际格式。未知/编码/混淆凭据、姓名/地址和其他证件未覆盖。

## 消息与失败

HMAC 输入包含算法版本、tenant/project/thread、category、完整原值，固定 27 位 base26 token；同 Thread 同原值稳定，跨 Thread 不关联；不存映射、不还原、不归一化不同格式。

连续普通文本块一起扫描，图片/data/base64/文件引用保留。远程媒体 URL 命中规则、未知发送块、加密 reasoning 或无法安全改写的签名内容会阻断。工具名/参数名/schema 枚举和常量不能改写成占位符；这些结构约束含敏感值时阻断，工具实际执行仍遵守原契约。

摘要继续复用官方 cutoff/state/history 机制；只在摘要输入副本保护。命中 PII 的待裁剪参数保持完整，最终请求再投影。官方 ContextOverflow 恢复会截断大型工具尾部，因此超过 4000 字且命中 PII 的连续工具尾部阻断恢复，避免部分标识符漏检；归档和工作区保留原文，不写入脱敏替代事实。

失败为 `RuntimePrivacyError` / `runtime.privacy.redaction_failed`，不计 Provider 故障、不切备用模型绕过。平台固定说明“隐私保护处理失败，本次模型请求未发送。”只指失败的本次调用；之前模型调用、已执行工具和外部副作用不会回滚。

标题保护失败返回“新对话”，推荐问题返回空列表；自动记忆来源命中则跳过，该来源不会进入提取模型。没有提取的来源不会新建 running。其余无命中来源保留 source/quote、作者、epoch/CAS、权限及候选审核规则；人工记忆不匿名化。

Langfuse 继续使用既有正文属性删除和 metadata 白名单，不保存“脱敏完整正文”。观察、执行及存储保护是不同边界。

## 更新、轮换与回退

1. 暂停新提交，drain 正在执行的 Run；确认没有活动 Worker 租约与未决提交。保留审批事实与文件，不清历史。
2. 通过原有部署凭据管理器统一更新 Runtime API/全部 Worker 配置，并核对同一政策版本；本期没有密钥分发/混配检测接口。
3. 同批重启进程，运行隔离合成探针。相同作用域同 key 的不同 Worker 结果一致；缺失/短 key 必须拒绝。不要记录密钥、匹配文本或映射。
4. 轮换会生成新 token，旧摘要/回答的 token 保留，无法与新 token 自动关联，也不能从旧 token 还原原值。业务需要关联时先创建新 Thread，不能伪造映射。
5. 关闭开关并同批重启恢复原始外发行为，不需迁移/删除数据。禁止 PII 外发的部署不得自动关闭来容灾，应暂停执行并由负责人决定回退已验证版本。

扫描同步执行，不能用 async timeout 保证中断。性能样本和繁忙主机限制见专项 verification；批量超长文本可能增加请求延迟，未设获批 SLO。图片/OCR/文件二进制、工具自身第三方出站和未接线教学图不在本期保证内。
