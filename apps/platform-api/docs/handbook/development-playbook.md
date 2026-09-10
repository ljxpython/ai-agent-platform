# Platform API 开发规范

2026-09-10 更新。适用于当前模块化单体；不再采用强制四层、Operations 或队列预留范式。

## 开发步骤

1. 确定能力归属：平台治理在本服务，图与工具执行在 Runtime。
2. 确定公开输入输出、权限、审计动作及事务边界。
3. 在现有模块中实现；只有出现独立职责时再新增文件。
4. 验证正常路径和相关失败边界；跨服务改动保留真实联调证据。
5. 同步 README、活规范与工程进度，不把代码完成当作验收完成。

## 同步 CRUD

HTTP endpoint 与 service 使用 def。路由解析参数和依赖，用例负责授权、业务规则与事务。
复杂或复用查询放 repository；简单业务不强制新增接口、基类或 DTO 转发层。

```python
from platform_api.core.db import session_scope

with session_scope(session_factory) as session:
    # 此处完成相关读写，成功提交、异常回滚，退出时关闭 Session。
    ...
```

## 异步编排

只在需要异步 HTTP/SSE 时使用 async def。数据库处理放在普通函数中：

```python
from starlette.concurrency import run_in_threadpool

def read_config():
    with session_scope(session_factory) as session:
        return load_config(session)  # 返回已物化结果，不返回 Session 或懒加载 ORM 对象

config = await run_in_threadpool(read_config)
result = await upstream.request(config)
```

Session 的创建、使用和关闭必须在同一个线程。不要把 commit 单独丢进线程池，也不要在事件循环中先创建 Session 再交给线程。
远端等待不占数据库事务；写结果时重新打开完整短事务。请求取消不能中途遗弃资源清理；审计收尾使用取消保护。
同步 service 的直接调用者使用普通调用；异步调用者显式 run_in_threadpool，不新增兼容旧 async 签名的包装。

## 目录与依赖

按[架构说明](architecture.md)组织；简单模块使用直接文件，复杂模块按需要保留分工。
从定义文件导入，避免 __init__.py 级联装配。跨模块查询由用例明确组合已有仓储，不为单个消费者机械新增 query port。
SDK、HTTP、SSE 细节在 adapters；业务 JWT 和模型授权仍属于 Platform/Runtime，不放进 GraphHarbor。
不新增通用事务框架、CRUD 基类、DI 容器、消息总线或无实际消费方的 Protocol。

## 验证要求

- CRUD：权限、校验、提交与异常回滚。
- 异步数据库：SQL 和 Session 生命周期离开事件循环，同一 Session 不跨线程，HTTP 等待时事务关闭。
- 网关：幂等、未知提交恢复、当前权限、审批 ID、项目隔离和公开字段过滤。
- 审计：成功、失败、取消均正确关联；不写入明文凭据。
- 目录调整：所有消费者、测试、初始化及打包导入同步变更，无旧路径兼容层。

执行命令见[服务 README](../../README.md)。本地真实验收先使用隔离库；前端、容器整体验收和完整 Server 等价性按工程计划另行推进。

移动或删除包目录后，在干净工作树构建 wheel，核查产物不含已删除路径；本机旧 build/ 缓存可能被 setuptools 继续打入增量产物，源码导入通过不代表 wheel 正确。
