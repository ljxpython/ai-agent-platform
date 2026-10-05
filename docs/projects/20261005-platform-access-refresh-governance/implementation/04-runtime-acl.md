# Runtime ACL 回查治理

## 改动
- Runtime auth/acl_client.py 承载共享客户端，webapp.py 管理生命周期；platform.py 文件路径加载仍使用同一 transport；HTTP 客户端按进程生命周期复用连接，默认超时统一为 10 秒并允许环境覆盖。
- ACL 无法确认返回 503；返回结构异常也不降级为 403；实际 allowed 列表不匹配仍返回 403。
- 日志增加项目、动作、目标数量和耗时字段。

## 验证
- Runtime 认证测试 114 项通过，Platform API 权限相关测试 13 项通过。

- 动态导入回归与 app lifespan 定向合计 41 项通过；独立 Runtime 重启后真实安全链路重验通过。

## 动态加载注意点
GraphHarbor 按文件路径导入 platform.py，该模块里的全局变量可能与普通包导入的同名模块不是同一实例。连接池放入普通导入的 auth/acl_client.py，鉴权与 webapp lifespan 共用；动态导入测试断言两者引用同一 post_acl 函数。
