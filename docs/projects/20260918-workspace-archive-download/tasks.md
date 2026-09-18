# 任务拆分与执行跟踪

## 任务列表

- [x] 1. runtime-service 核心实现
  - [x] 1.1 `WorkspaceBrowser` 新增 `create_archive()` 方法，使用 `zipfile` 遍历打包并防御软链接逃逸
  - [x] 1.2 `http/workspace.py` 新增 `GET /internal/threads/{thread_id}/workspace/zip`
  - [x] 1.3 编写 unit test 覆盖空目录、嵌套子目录、中文字符文件名打包并验证
- [x] 2. platform-api 网关层透传与鉴权
  - [x] 2.1 `http.py` 新增 `GET /threads/{thread_id}/workspace/zip`
  - [x] 2.2 `service.py` 补充 `workspace/zip` 资源透传
  - [x] 2.3 编写/运行网关测试确保路由与头信息正确透传
- [x] 3. platform-web 前端对接
  - [x] 3.1 `workspace.service.ts` 新增 `downloadWorkspaceZip`
  - [x] 3.2 `useThreadWorkspace.ts` 暴露 `downloadingArchive` 与 `downloadAllFiles`
  - [x] 3.3 `WorkspacePanel.vue` 工具栏新增【打包下载】按钮及 loading 状态
  - [x] 3.4 执行 vitest 与 vue-tsc 验证
- [x] 4. 链路集成与验收登记
  - [x] 4.1 全流程验收与四态记录
  - [x] 4.2 更新 `docs/FEATURES.md`
