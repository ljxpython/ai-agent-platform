# 现役组合生命周期阶段证据

2026-09-27；当前本地stack的platform-api、Runtime API、worker均运行；测试项目 `5a5b7239-43e3-40e6-bba3-e64d96057607`。本轮只创建测试Thread/Run及专用测试身份，未修改现有账号、Runtime/GraphHarbor代码或配置，未迁移、部署或提交。所有时间为UTC；不记录token、secret或模型密钥。

| 场景 | 实际结果 | 判定 |
|---|---|---|
| R01 | 02:05:49平台接受标称延迟70秒Run `6b6ee229-42cf-4b83-b9c5-b5ce17f18b26`，Runtime记录02:05:53已`success`；kwargs保留`after_seconds=70`，实际未延迟。后续隔离Thread `2b3ecf30-be4a-4433-9ff2-60cc7ba56738`的真实`execute`审批后，新Run `5ae46b6f-61ed-4003-88dc-351185977dcf`于02:37:28.797 UTC创建、02:38:37.296 UTC成功，持续68.499秒；工具02:37:30.588开始、02:38:29.679完成，退出码0 | 通过：工具执行和Run终态均越过60秒委托TTL，未观察到因到期自动取消或重发；先前晚查询样本仍不计入证据 |
| R02 | 同Thread `e547d816-3ba8-4399-adce-f50de4351858`的SSE首次连接200，约61.6秒观察90个事件标记；到期后重连200并得到游标；重连前后Run列表为1条 | 已观察连接跨TTL与只订阅，不证明所有网络恢复场景 |
| R03 | 首个专用用户 `889fb778-28ee-469d-a86d-f34b616d5a3b`禁用后Catalog、SSE重连、取消均`403 user_not_active`，但其Run约0.2秒即失败。第二个专用用户 `e9b07bac-817f-425b-95e8-cf1b9f66eb92`于02:40:56 UTC通过平台审批后生成Run `3dd06ea6-fbd9-46bb-9249-17777ce394a2`，02:40:59禁用；Catalog和取消新请求均`403 user_not_active`。Run的`execute`于02:40:58.753开始、02:41:57.843完成，退出码0；Run于02:42:03.207成功，总耗时66.481秒 | 通过：撤权后的新请求被拒绝，已接受的在途Run未被自动取消；首个失败样本不计入在途证据 |
| R04 | 专用延迟Run `6d106bc9-97e0-41df-afb8-8169142a90bb`取消ACK为200，随后查询`interrupted`；`showcase_demo` Run `ce7adb5c-8264-4a9c-a252-15c84ba76664`产生真实`write_file` interrupt，平台按ID批准后新Run `0561a389-515f-4385-a7c8-70d617ca8cbe`为`success`；Catalog读取200、刷新200/4个graph；专用service account `30440ade-e366-47cc-af12-3d9349c4b2ef`授grant后Catalog读取200，禁用后旧API key为`401 invalid_api_key` | 取消ACK与终态、原Run与审批恢复Run分别记录；文件内容单独读取探针因路径格式返回400，未记文件验收 |

限制：测试服务账号和两个专用测试用户已禁用。标称延迟Run `3bdb9a73-0e07-4a66-9cdb-697fbf61b8d5`于创建后约0.18秒即`error/business_error`；只读终态事件给出`runtime.model.initialization_failed`，`after_seconds=70`未形成在途样本。第二个撤权探针在禁用后用管理员读取该用户Thread时被ACL拒绝`403 thread_action_denied`，随后仅以Runtime数据库只读记录核对Run及工具终态。测试项目保留本轮Thread/Run作为审计证据，未删除现有资源。消息内部原生Run回查的403已在自动化中复现，未声称消息业务完成。
