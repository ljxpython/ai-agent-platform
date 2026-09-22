# 新建用户页面重构为一页流与多项目分配支持

- **日期**：2026-09-22
- **影响服务**：`platform-web`
- **涉及文件**：
  - `apps/platform-web/src/modules/users/pages/UserCreatePage.vue`
  - `apps/platform-web/src/modules/users/pages/UserCreatePage.spec.ts`
  - `apps/platform-web/src/components/base/BaseSelect.vue`
  - `apps/platform-web/src/components/base/BaseSelect.spec.ts`

## 背景与动因

1. **凭据自动填充与下拉遮挡 bug**：新建用户页面原本受浏览器密码管理器干扰自动填充当前管理员账号密码；外层滥用 `<label>` 导致点击下拉框上方区域时浏览器触发合成点击使下拉框无法正常关闭。
2. **密码确认缺失**：单密码输入框容易因敲错导致账号不可用，需补充二次密码确认校验。
3. **两步流交互体验割裂**：原页面先创建账号再跳到“第二步”单选绑定项目，操作繁琐且仅支持绑定单个项目；底层数据模型本来支持用户多项目归属。

## 改动内容

1. **防自动填充与表单标签修正**：
   - 增加 `autocomplete="off"` 与 `autocomplete="new-password"`，修正输入框 `name` 属性。
   - 在 `BaseSelect.vue` 增加外部点击短时防抖保护，阻断由于外部 `<label>` 触发的浏览器合成点击重开。
2. **确认密码与双向校验**：
   - 增加确认密码输入框，提交前强校验一致性，上方统计卡片实时联动。
3. **一站式单表单流（一页流）与多项目动态分配**：
   - 彻底废除创建后跳转的“第二步”卡片，统一为一体化表单。
   - 增加所属项目分配动态列表，支持用户创建时选择 0 至多个项目并独立指定角色（项目执行者/编辑者/管理员）。
   - 动态排除已选项目，选择项目时异步预检 `project.member.write` 权限。
   - 提交时一次性创建账号并批量绑定项目，若部分绑定失败提供容错提示且保留账号。
