# 常见错误与排查手册

## 1. 目标

记录当前 `platform-api` + `platform-web` 联调下的高频问题与最小排查方式。

## 2. 常见问题

### 2.1 `401 unauthorized`

现象：访问 `/_management/*` 返回 401。

处理：

1. 重新登录前端
2. 检查浏览器 `localStorage` 中的 `oidc:token_set`
3. 确认请求头带有 `Authorization: Bearer ...`

### 2.2 `403 admin_required`

现象：访问用户/项目管理接口返回 403。

处理：

1. 使用 super admin 登录
2. 或确认当前用户在目标项目中具备 `admin` 角色

### 2.3 `403 insufficient_project_role`

现象：项目成员管理、项目删除等操作被拒绝。

处理：

1. 确认当前项目角色是否足够
2. 必要时补充 `admin`

### 2.4 最后一个项目管理员无法删除/降权

现象：成员删除或角色调整失败。

原因：后端最后一个 `admin` 保护生效。

### 2.5 前端构建失败

```bash
cd ../platform-web
pnpm install --frozen-lockfile
pnpm build
```

### 2.6 后端测试导入失败

```bash
PYTHONPATH=. uv run pytest tests/test_self_hosted_auth_basics.py
```

## 3. 推荐最小排查命令

```bash
PYTHONPATH=. uv run pytest tests/test_self_hosted_auth_basics.py
cd ../platform-web && pnpm build
```

## 4. 说明

- 本手册不再包含 Keycloak/OpenFGA 历史链路
- retired passthrough 路由不再作为当前排查对象
