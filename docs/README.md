# AI测试实验室 - 文档中心

[← 返回主项目](../README.md)

欢迎来到AI测试实验室的文档中心！这里包含了项目的完整文档，帮助您快速了解和使用本平台。

## 📚 文档导航

### 🚀 快速开始
- [项目概述](./overview/PROJECT_OVERVIEW.md) - 了解项目背景、目标和核心功能
- [开发环境搭建](./development/DEVELOPMENT_SETUP.md) - 快速搭建开发环境
- [Makefile使用指南](./setup/MAKEFILE_GUIDE.md) - 项目管理命令详解

### 🏗️ 系统架构
- [系统架构概览](./architecture/SYSTEM_ARCHITECTURE.md) - 整体架构设计
- [后端架构文档](./architecture/BACKEND_ARCHITECTURE.md) - 后端详细架构说明
- [前端架构文档](./architecture/FRONTEND_ARCHITECTURE.md) - 前端架构设计
- [AI模块架构](./architecture/AI_MODULES.md) - AI智能体协作架构
- [用户系统架构](./architecture/USER_SYSTEM.md) - 用户认证和权限管理
- [服务重构文档](./architecture/SERVICES_REFACTORING.md) - 后端服务模块化重构
- [服务优化总结](./architecture/SERVICES_OPTIMIZATION_SUMMARY.md) - 服务框架优化成果
- [AI核心框架文档](./architecture/AI_CORE_FRAMEWORK.md) - AI核心组件和LLM管理器
- [框架优化第三步](./architecture/FRAMEWORK_OPTIMIZATION_STEP3.md) - 服务抽象与智能体框架
- [测试用例服务重构](./architecture/TESTCASE_SERVICE_REFACTORING.md) - 基于AI核心框架的服务重构实践
- [AutoGen序列化问题修复](./architecture/AUTOGEN_SERIALIZATION_FIX.md) - AutoGen消息订阅和序列化问题解决方案
- [消息队列重构](./architecture/MESSAGE_QUEUE_REFACTORING.md) - 移除重复代码，复用AI核心框架队列功能
- [真实智能体实现](./architecture/REAL_AGENT_IMPLEMENTATION.md) - 从mock数据升级为真实的AI智能体功能
- [智能体继承重构](./architecture/AGENT_INHERITANCE_REFACTORING.md) - 智能体正确继承AI核心框架基类，复用框架功能
- [AI核心智能体基类重构](./architecture/AI_CORE_AGENTS_REFACTORING.md) - 参考examples/frame_v1设计，提供标准化智能体基类
- [完全参考testcase_service1.py的智能体实现](./architecture/TESTCASE_SERVICE1_AGENT_IMPLEMENTATION.md) - 不使用StreamingAgent，完全复用testcase_service1.py的逻辑
- [智能体初始化修复](./architecture/AGENT_INITIALIZATION_FIX.md) - 修复register_agents函数，使用工厂模式创建智能体
- [队列消息修复](./architecture/QUEUE_MESSAGE_FIX.md) - 修复智能体消息队列，使用正确的testcase_service队列管理
- [内存管理集成](./architecture/MEMORY_MANAGEMENT_INTEGRATION.md) - 集成AI核心框架的内存管理器，统一智能体记忆功能
- [内存管理优化](./architecture/MEMORY_OPTIMIZATION.md) - 优化内存管理底层健壮性，上层直接导入使用
- [AI核心模块健壮性增强](./architecture/AI_CORE_ROBUSTNESS_ENHANCEMENT.md) - 全面增强AI核心模块的容错机制和日志记录
- [TestCase服务文件方法修复](./architecture/TESTCASE_SERVICE_FILE_METHODS_FIX.md) - 修复智能体访问文件内容的方法缺失问题
- [智能体流式日志调试增强](./architecture/AGENT_STREAMING_DEBUG_ENHANCEMENT.md) - 增强智能体流式处理的详细日志记录和调试能力
- [测试用例智能体用户反馈功能实现](./architecture/TESTCASE_AGENT_USER_FEEDBACK_IMPLEMENTATION.md) - 实现测试用例智能体的团队协作和用户反馈机制

### 💻 开发指南
- [开发环境配置](./development/README.md) - 开发环境详细配置
- [前后端集成](./development/FRONTEND_BACKEND_INTEGRATION.md) - API集成和数据流
- [代码重构总结](./development/CODE_REFACTORING_SUMMARY.md) - 代码优化记录
- [日志系统](./development/LOGGING_GUIDE.md) - 日志配置和使用
- [Markdown渲染器](./development/MARKDOWN_RENDERER.md) - 前端Markdown支持

### 🎨 UI设计
- [UI设计指南](./ui-design/UI_DESIGN_GUIDE.md) - 设计规范和组件库
- [导航系统](./ui-design/NAVIGATION_SYSTEM.md) - 导航栏和侧边栏设计
- [测试用例页面优化](./ui-design/TESTCASE_PAGE_OPTIMIZATION.md) - 页面设计优化

### 🔧 项目配置
- [Factory模式配置](./setup/FACTORY_PATTERN.md) - FastAPI应用工厂模式
- [项目配置说明](./setup/README.md) - 配置文件和环境变量

### 🗄️ 数据库
- [数据库设计](./database/DATABASE_DESIGN.md) - 数据模型和关系设计
- [迁移管理](./database/MIGRATION_GUIDE.md) - Aerich迁移使用指南
- [数据初始化](./database/DATA_INITIALIZATION.md) - 默认数据和种子数据

### 🚨 故障排除
- [常见问题](./troubleshooting/README.md) - 常见问题和解决方案
- [进程管理](./troubleshooting/PROCESS_MANAGEMENT.md) - 服务进程管理
- [AutoGen修复](./troubleshooting/AUTOGEN_FIXES.md) - AutoGen相关问题
- [前端图标修复](./troubleshooting/FRONTEND_ICON_FIX.md) - 前端图标问题

### 🔧 修复记录
- [修复记录总览](./fixes/README.md) - 项目修复历史记录
- [后端修复](./fixes/backend/README.md) - 后端相关问题修复
- [前端修复](./fixes/frontend/README.md) - 前端相关问题修复
- [流式处理修复](./fixes/streaming/README.md) - SSE和流式处理修复

### ⚡ 优化记录
- [优化记录总览](./optimizations/README.md) - 项目优化历史记录
- [UI优化](./optimizations/ui/README.md) - 界面和交互优化
- [性能优化](./optimizations/performance/README.md) - 性能提升记录
- [架构优化](./optimizations/architecture/README.md) - 架构改进记录

### 📝 工作记录
- [工作记录总览](./work/README.md) - 项目开发工作记录
- [开发历程](./work/) - 详细的开发过程记录

## 📖 文档说明

### 文档组织原则
- **分类清晰**: 按功能模块和使用场景分类
- **层次分明**: 从概览到详细，从入门到进阶
- **双向链接**: 文档间相互引用，便于导航
- **持续更新**: 随项目发展同步更新

### 新的文档结构特点
- **主入口统一**: docs目录只保留一个README.md作为总入口
- **分类管理**: 相关文档归类到对应的子目录中
- **专题组织**: 修复记录、优化记录、工作记录分别管理
- **导航清晰**: 每个分类都有独立的导航和索引

### 文档分类说明

#### 🔧 修复记录 (fixes/)
记录项目开发过程中遇到的问题和解决方案：
- **后端修复**: API、数据库、日志等后端问题
- **前端修复**: UI、交互、显示等前端问题
- **流式处理修复**: SSE、实时通信等流式处理问题

#### ⚡ 优化记录 (optimizations/)
记录项目的各种优化改进：
- **UI优化**: 界面设计和用户体验优化
- **性能优化**: 系统性能和响应速度优化
- **架构优化**: 代码结构和系统架构优化

#### 📝 工作记录 (work/)
记录项目开发的历程和经验：
- **开发历程**: 详细的开发过程记录
- **经验总结**: 开发过程中的经验和教训

### 文档格式规范
- 使用Markdown格式编写
- 统一的标题层级和格式
- 清晰的代码示例和配置说明
- 丰富的图表和流程图

### 贡献指南
- 新增功能时同步更新相关文档
- 遵循现有的文档结构和格式
- 将文档放到合适的分类目录中
- 及时更新过时的信息

## 🔗 相关链接

- [项目主页](../README.md) - 返回项目根目录
- [在线API文档](http://localhost:8000/docs) - FastAPI自动生成的API文档
- [前端应用](http://localhost:3000) - 前端应用访问地址

## 📞 获取帮助

如果您在使用过程中遇到问题：

1. 首先查看[故障排除](./troubleshooting/README.md)文档
2. 查看相关的[修复记录](./fixes/README.md)
3. 搜索相关的文档和示例
4. 查看项目的Issue和讨论
5. 联系项目维护者

## 📊 文档统计

### 文档数量概览
- **核心文档**: 架构、开发、设计等核心文档 20+ 个
- **修复记录**: 问题修复历史记录 35+ 个
- **优化记录**: 项目优化改进记录 30+ 个
- **工作记录**: 开发历程和经验总结 10+ 个
- **总计**: 95+ 个文档

### 文档覆盖范围
- ✅ 项目概览和快速开始
- ✅ 系统架构和设计文档
- ✅ 开发指南和最佳实践
- ✅ 问题修复和优化记录
- ✅ 故障排除和运维指南
- ✅ 完整的历史记录和经验总结

---

**最后更新**: 2024年12月
**文档版本**: v2.0.0 - 重新整理版
