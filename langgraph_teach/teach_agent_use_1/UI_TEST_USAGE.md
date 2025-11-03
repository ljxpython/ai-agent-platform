# UI自动化测试Agent使用指南

## 功能概述

UI自动化测试Agent是一个基于LangGraph + MCP + Chrome工具的智能测试系统，能够：

1. ✅ 自动设计测试用例
2. ✅ 执行UI自动化测试
3. ✅ 生成Excel测试用例文档
4. ✅ 生成图文并茂的HTML测试报告
5. ✅ 自动截图记录测试过程

## 快速开始

### 1. 启动服务

#### 启动Chrome MCP服务（如果未运行）
```bash
# 确保Chrome MCP服务在12306端口运行
lsof -i :12306
```

#### 启动后端服务
```bash
/Users/bytedance/PycharmProjects/test/langgraph_study/.venv/bin/python /Users/bytedance/PycharmProjects/test/langgraph_study/start_server.py
```

后端服务将在以下地址启动：
- 🌐 API服务: http://localhost:2025
- 📚 API文档: http://localhost:2025/docs
- 🎨 Studio UI: http://localhost:2025/ui

#### 启动前端服务
```bash
cd agent-chat-ui
npm run dev
```

前端服务将在以下地址启动：
- 🌐 前端UI: http://localhost:3001

### 2. 使用UI测试Agent

#### 方式一：通过前端UI（推荐）

1. 打开浏览器访问: http://localhost:3001
2. 选择 **ui_test_agent**
3. 在输入框中输入测试需求，例如：

```
打开新的窗口，https://www.saucedemo.com/，编写2条测试用例并进行测试，最后总结生成报告
```

4. Agent将自动：
   - 分析网站功能
   - 设计测试用例
   - 执行自动化测试
   - 截图记录过程
   - 生成Excel和HTML报告

#### 方式二：通过API调用

查看 `test_ui_agent.py` 文件了解如何通过API调用。

### 3. 查看测试报告

测试完成后，报告将保存在项目根目录下的 `ui_test_reports/` 文件夹中：

```
ui_test_reports/
├── test_cases_20250103_143022.xlsx    # Excel测试用例
└── test_report_20250103_143025.html   # HTML测试报告
```

- **Excel报告**: 包含详细的测试用例、步骤、预期结果、实际结果和状态
- **HTML报告**: 图文并茂的测试报告，包含截图、统计图表和详细信息

## 测试用例示例

### 示例1：登录功能测试
```
测试https://www.saucedemo.com/的登录功能，设计3个测试用例：
1. 正常登录
2. 错误密码登录
3. 空用户名登录
```

### 示例2：电商网站测试
```
测试https://www.saucedemo.com/，设计以下测试用例：
1. 用户登录
2. 浏览商品列表
3. 添加商品到购物车
4. 查看购物车
生成完整的测试报告
```

### 示例3：表单测试
```
打开https://example.com/contact，测试联系表单：
1. 填写所有必填字段并提交
2. 缺少必填字段提交
3. 输入无效邮箱格式
```

## Agent工作流程

```
用户输入测试需求
    ↓
分析网站并设计测试用例
    ↓
打开浏览器并导航到目标网站
    ↓
执行测试用例（逐个）
    ├─ 执行测试步骤
    ├─ 截图记录
    ├─ 验证结果
    └─ 记录状态（Pass/Fail）
    ↓
汇总测试结果
    ↓
生成Excel测试用例文档
    ↓
生成HTML测试报告
    ↓
返回报告路径给用户
```

## 可用工具

UI测试Agent集成了以下工具：

### Chrome MCP工具
- `chrome_navigate_chrome_mcp`: 导航到URL
- `chrome_get_web_content_chrome_mcp`: 获取页面内容
- `chrome_click_element_chrome_mcp`: 点击元素
- `chrome_fill_or_select_chrome_mcp`: 填写表单
- `chrome_screenshot_chrome_mcp`: 截图
- `chrome_get_interactive_elements_chrome_mcp`: 获取可交互元素
- 更多工具...

### 自定义测试工具
- `save_test_cases_to_excel`: 保存测试用例到Excel
- `generate_html_report`: 生成HTML测试报告
- `set_output_directory`: 设置输出目录
- `get_output_directory`: 获取输出目录

## 测试报告格式

### Excel报告包含
- 用例ID
- 用例标题
- 测试步骤（详细）
- 预期结果
- 实际结果
- 状态（Pass/Fail/Skip）
- 备注

### HTML报告包含
- 📊 测试摘要（总数、通过、失败、跳过、通过率）
- 📝 详细测试用例
- 📸 测试截图
- 🎨 美观的可视化界面
- ⏰ 测试时间记录

## 注意事项

1. **Chrome浏览器**: 确保Chrome MCP服务正常运行
2. **网络连接**: 测试需要访问目标网站
3. **测试时间**: 复杂测试可能需要较长时间
4. **报告目录**: 默认保存在 `ui_test_reports/` 目录
5. **截图大小**: 大量截图可能占用较多磁盘空间

## 故障排查

### 问题1: Chrome MCP服务未运行
```bash
# 检查服务状态
lsof -i :12306

# 如果未运行，请启动Chrome MCP服务
```

### 问题2: 后端服务启动失败
```bash
# 检查端口占用
lsof -i :2025

# 检查Python环境
/Users/bytedance/PycharmProjects/test/langgraph_study/.venv/bin/python --version
```

### 问题3: 前端无法访问
```bash
# 检查前端服务
lsof -i :3001

# 重新启动前端
cd agent-chat-ui && npm run dev
```

### 问题4: 测试报告未生成
- 检查 `ui_test_reports/` 目录是否存在
- 查看Agent执行日志
- 确认测试是否完整执行

## 技术架构

```
┌─────────────────────────────────────────────┐
│           前端UI (Next.js)                   │
│         http://localhost:3001                │
└──────────────────┬──────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────┐
│      LangGraph API Server                    │
│         http://localhost:2025                │
│  ┌─────────────────────────────────────┐    │
│  │  ui_test_agent (LangGraph Agent)    │    │
│  │  - DeepSeek LLM                     │    │
│  │  - Chrome MCP Tools                 │    │
│  │  - Custom Test Tools                │    │
│  └─────────────────────────────────────┘    │
└──────────────────┬──────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────┐
│      Chrome MCP Server                       │
│         http://localhost:12306               │
│  - Browser Automation                        │
│  - Screenshot Capture                        │
│  - Element Interaction                       │
└─────────────────────────────────────────────┘
```

## 示例输出

### Excel报告示例
| 用例ID | 用例标题 | 测试步骤 | 预期结果 | 实际结果 | 状态 |
|--------|----------|----------|----------|----------|------|
| TC_001 | 正常登录 | 1. 打开登录页<br>2. 输入用户名<br>3. 输入密码<br>4. 点击登录 | 成功登录并跳转到首页 | 成功登录并跳转到首页 | Pass |
| TC_002 | 错误密码 | 1. 打开登录页<br>2. 输入用户名<br>3. 输入错误密码<br>4. 点击登录 | 显示错误提示 | 显示"用户名或密码错误" | Pass |

### HTML报告预览
- 顶部显示测试摘要卡片（总数、通过、失败、通过率）
- 每个测试用例以卡片形式展示
- 包含测试步骤、结果和截图
- 使用颜色区分Pass/Fail状态
- 响应式设计，支持移动端查看

## 更多信息

- 项目仓库: `/Users/bytedance/PycharmProjects/test/langgraph_study`
- 工具文件: `ui_test_tools.py`
- Agent配置: `main.py`
- 图配置: `graph.json`

---

**开始测试吧！** 🚀
