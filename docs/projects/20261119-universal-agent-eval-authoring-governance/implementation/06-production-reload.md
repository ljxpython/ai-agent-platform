# 正式 EvalFlow 重载与人工验收交接

2026-11-19，用户明确授权正式 EvalFlow 加载合并新版，并要求随后亲自按步骤验收。唯一进度仍在[Task6](../tasks.md#task-6正式服务加载新版并提供逐步人工验收文档)，[操作手册](../manual-acceptance.md)给出网页、按钮、完整输入与预期；本记录只保存工程事实。

## 重载前后

重载前主仓 `sshmy1:/opt/mlflow-eval-platform` 的 main 为 `9373c1e4d74173d0fe7bf0218c3044c9215e1364`，工作区干净。实际进程的 `EVALFLOW_STATE_DIR` 指向主仓 `.local-stack`。扫描主目录与server连接共5份任务、10份工作项，未发现排队、运行、取消中、等待审批任务，亦无未完成出题作业／发布运行操作。保存进程身份、三份配置和十份旧工作项哈希后执行：

```bash
ssh sshmy1 "systemctl restart mlflow-eval.service"
```

正式服务于 **2026-11-19 15:46:59（Asia/Shanghai）**启动，MainPID从2115014变为2308114，ActiveState=active、SubState=running、NRestarts=0，WorkingDirectory为主仓。重载后用服务进程环境执行模块导入检查，`mlflow`、`eval_platform.evaluation_assistant`和`eval_platform.work_items`均解析到`/opt/mlflow-eval-platform/`，没有指向已删除Worktree。

5000与9128健康均200；三份配置与十份旧工作项哈希保持。Agent Platform API、Runtime API和Worker的PID、启动时间、状态与NRestarts均与重载前相同。本轮没有改配置、数据库或产品源码，没有重启Agent三服务，也未恢复旧测试Worktree。

## 认证和旧资产的真实结果

| 入口 | 管理员 | 不携带凭据 | 错误凭据 |
|---|---|---|---|
| 后端5000任务接口 | 200 | 401 | 401 |
| 正式代理9128任务接口 | 200 | 200，既有代理注入默认身份 | 401 |

首次后置脚本假定9128匿名应返回401，实际200而中止。随后使用无cookie、关闭环境代理／netrc继承的独立请求复查，确认不是HTML页面或客户端自动带凭据。只读检查现有Nginx配置发现无Authorization时自动注入默认Basic身份；外部Mac同样能无凭据读取任务JSON。本轮没有修改该配置，也不把这个结果写成“公网匿名拒绝通过”。其访问边界风险是没有提供凭据的访问者可能取得代理默认身份；是否调整代理认证需要另行决定，不通过本轮重载擅自改变。

旧`server`工作项`9e092086-02f6-55cb-a63b-aeac0b773466`正常认证读取200。browser-skill在独立Agent窗口核对正式列表、`UPGRADE-20261118-server`题目、旧发布版、历史成功及失败结果和“发起评测”弹窗；仅打开并取消弹窗，没有点击开考。Agent正式聊天页也核对到test项目、dearflow_agent选择器、消息输入和模型入口。

跨连接旧资产检查曾因`default`回源503中止，错误为“平台暂时不可连接，原资料保留；请稍后重试原请求”。本轮未恢复其Mac来源服务／隧道，不将default在线读取记作通过；全部十份本地工作项哈希不变。人工操作手册固定使用可用的`server`，不要求用户切旧连接。两次检查失败及后续诊断均保留，不重复重启服务来迎合检查。

## 证据、复用与边界

现场私有证据目录：`sshmy1:/opt/mlflow-eval-platform/.local-stack/deliveries/20261119-universal-authoring/production-reload/`。

- `precheck.json`、`services-before.txt`、`process-before.json`：重载前活动检查与服务身份。
- `before-hashes.json`：配置和资产哈希，不包含配置正文或凭据。
- `restart.log`、`services-after.txt`、`services-verified.txt`：实际重载与后续服务状态。
- `reload-summary.json`：2026-11-19 15:53:15核对结果、源码路径、HTTP正负例、旧资产结果及两次检查失败说明。
- `auth-boundary.json`：既有Nginx配置哈希、空凭据默认身份匹配结果，不含凭据值。

本轮无产品代码变化，复用合并版本689 passed／21 warnings及真实模型全链路证据；没有再次运行689项或固定十题，也没有把页面只读核对当成完整浏览器E2E。用户本次人工验收尚未执行，结论在手册中留空；未验证default恢复、HTTPS、独立盲评或大规模压测。编写和检查文档不计入产品测试数量。

文档检查实际执行：Agent仓`python3 scripts/check_docs.py`通过；两仓新增／受影响项目文档相对链接有效、代码围栏成对，`git diff --check`通过。逐步手册共11步，六项用户结果均留待填写。两次browser-skill会话均已关闭，最终会话列表为空。
