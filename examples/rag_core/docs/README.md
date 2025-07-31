# RAG服务使用文档

本文档提供RAG (Retrieval-Augmented Generation) 服务的完整使用指南，包括基本概念、完整流程和实际应用示例。

## 📋 目录

- [RAG基本概念](#rag基本概念)
- [RAG五个关键阶段](#rag五个关键阶段)
- [快速开始](#快速开始)
- [完整使用示例](#完整使用示例)
- [高级功能](#高级功能)
- [性能优化](#性能优化)
- [故障排除](#故障排除)

### 📋 文档结构

```
docs/
├── README.md                       # 本文件 - RAG服务使用指南
├── milvus_llamaindex_guide.md      # Milvus + LlamaIndex 完整功能指南
├── complete_feature_guide.md       # 完整功能测试验证指南
└── examples/                       # 示例代码目录
    ├── collection_creation_guide.md    # Collection创建指南
    ├── metadata_filtering_guide.md     # 元数据过滤指南
    └── crud_operations_guide.md        # CRUD操作指南
```

## 🧠 RAG基本概念

RAG (Retrieval-Augmented Generation) 是一种结合了信息检索和文本生成的AI技术。它通过以下流程工作：

```
用户查询 → 向量检索 → 相关文档 → 上下文增强 → LLM生成 → 最终回答
```

### 核心优势

- **知识更新**: 无需重新训练模型即可更新知识库
- **准确性**: 基于真实文档生成回答，减少幻觉
- **可追溯**: 可以追踪回答的来源文档
- **灵活性**: 支持多种数据源和查询方式

## 🔄 RAG五个关键阶段

### 1. 加载 (Loading)
从各种数据源导入数据到系统中：
- 文本文件 (.txt, .md)
- PDF文档
- 网页内容
- 数据库数据
- API数据

### 2. 索引 (Indexing)
创建数据结构以支持高效查询：
- 文本分割成合适的块
- 生成向量嵌入
- 提取和存储元数据
- 建立索引结构

### 3. 存储 (Storing)
持久化索引和元数据：
- 向量数据存储在Milvus
- 元数据存储和管理
- 索引优化和压缩

### 4. 查询 (Querying)
检索相关上下文：
- 查询向量化
- 相似性搜索
- 元数据过滤
- 结果排序和筛选

### 5. 生成 (Generation)
结合上下文生成最终回答：
- 构建增强提示
- LLM推理生成
- 后处理和格式化

## 🚀 快速开始

### 1. 基本设置

```python
import asyncio
from backend.rag_core.rag_system import RAGSystem

async def basic_setup():
    """基本设置示例"""
    async with RAGSystem() as rag:
        # 设置Collection
        await rag.setup_collection("my_knowledge", overwrite=True)
        print("✅ RAG系统初始化完成")

asyncio.run(basic_setup())
```

### 2. 添加文档

```python
async def add_documents():
    """添加文档示例"""
    async with RAGSystem() as rag:
        await rag.setup_collection("my_knowledge")

        # 添加单个文档
        success = await rag.add_document(
            content="人工智能是计算机科学的一个分支。",
            metadata={
                "title": "AI概述",
                "category": "technology",
                "source": "教程"
            },
            collection_name="my_knowledge"
        )

        if success:
            print("✅ 文档添加成功")

asyncio.run(add_documents())
```

### 3. 查询文档

```python
async def query_documents():
    """查询文档示例"""
    async with RAGSystem() as rag:
        # 基本搜索
        results = await rag.search(
            query="什么是人工智能？",
            collection_name="my_knowledge",
            top_k=3
        )

        print(f"找到 {len(results)} 个相关文档")
        for result in results:
            print(f"- {result['metadata']['title']}: {result['score']:.3f}")

asyncio.run(query_documents())
```

## 📖 完整使用示例

### 完整RAG工作流程

运行完整的RAG工作流程示例：

```bash
# 运行完整示例
cd backend/rag_core
PYTHONPATH=/path/to/project python3 rag_complete_example.py
```

这个示例展示了：
- ✅ 数据加载 (Loading)
- ✅ 数据索引 (Indexing)
- ✅ 数据存储 (Storing)
- ✅ 智能查询 (Querying)
- ✅ 回答生成 (Generation)

### 核心API使用

```python
async def complete_workflow():
    """完整工作流程示例"""
    async with RAGSystem() as rag:
        # 1. 设置Collection
        await rag.setup_collection("knowledge_base", overwrite=True)

        # 2. 批量添加文档
        documents = [
            {
                "content": "人工智能是计算机科学的一个分支...",
                "metadata": {"title": "AI概述", "category": "technology"}
            },
            {
                "content": "机器学习是AI的子集...",
                "metadata": {"title": "ML基础", "category": "technology"}
            }
        ]

        for doc in documents:
            await rag.add_document(
                content=doc["content"],
                metadata=doc["metadata"],
                collection_name="knowledge_base"
            )

        # 3. 智能查询
        results = await rag.search(
            query="什么是人工智能？",
            collection_name="knowledge_base",
            top_k=5
        )

        # 4. RAG问答（如果配置了LLM）
        try:
            response = await rag.query(
                query="请详细介绍人工智能",
                collection_name="knowledge_base"
            )
            print(f"AI回答: {response['answer']}")
        except Exception as e:
            print(f"需要配置LLM服务: {e}")
```

## 🔧 高级功能

### 1. 元数据过滤查询

```python
async def metadata_filtering():
    """元数据过滤示例"""
    async with RAGSystem() as rag:
        # 按类别过滤
        results = await rag.search_with_filter(
            query="技术文档",
            collection_name="knowledge_base",
            filters={"category": "technology"},
            top_k=3
        )

        # 多条件过滤
        results = await rag.search_with_filter(
            query="最新技术",
            collection_name="knowledge_base",
            filters={"category": "technology", "year": 2024},
            top_k=5
        )
```

### 2. 批量操作

```python
async def batch_operations():
    """批量操作示例"""
    async with RAGSystem() as rag:
        # 批量查询
        queries = ["AI定义", "ML类型", "DL应用"]
        results = []

        for query in queries:
            result = await rag.search(query, "knowledge_base", top_k=3)
            results.append(result)

        print(f"批量查询完成: {len(results)} 个结果")
```

### 3. 性能监控

```python
async def performance_monitoring():
    """性能监控示例"""
    async with RAGSystem() as rag:
        # 获取Collection统计
        stats = await rag.get_collection_stats("knowledge_base")
        print(f"Collection统计: {stats}")

        # 检查系统状态
        status = await rag.health_check()
        print(f"系统状态: {status}")
```

## ⚡ 性能优化

### 1. 批量处理

- 使用批量添加而非单个添加
- 合理设置batch_size (建议100-1000)
- 使用异步操作提高并发性能

### 2. 查询优化

- 合理设置top_k值 (建议3-10)
- 使用元数据过滤减少搜索范围
- 缓存常用查询结果

### 3. 资源管理

- 及时关闭RAGSystem连接
- 监控内存使用情况
- 定期清理无用数据

## 🔧 配置说明

### 基本配置

在 `backend/conf/settings.yaml` 中配置：

```yaml
rag:
  milvus:
    host: "localhost"
    port: 19530
    collections:
      general:
        name: "general_knowledge"
        dimension: 1024
        top_k: 5
        similarity_threshold: 0.7

  ollama:
    base_url: "http://localhost:11434"
    embedding_model: "bge-m3"
```

### 支持的Collection类型

- **general** - 通用知识库
- **testcase** - 测试用例知识库
- **ui_testing** - UI测试知识库
- **ai_chat** - AI对话知识库

## 🧪 测试验证

### 运行测试

```bash
# 核心功能测试
cd backend/rag_core
PYTHONPATH=/path/to/project python3 test_core_crud.py

# 完整工作流程测试
PYTHONPATH=/path/to/project python3 rag_complete_example.py
```

### 测试结果示例

```
============================================================
🧪 Milvus向量数据库核心CRUD功能测试
============================================================

📦 1. Collection管理测试
   ✅ Collection创建成功

📝 3. 节点创建测试 (Create)
   ✅ 基本添加: 3 个节点

📖 4. 节点查询测试 (Read)
   ✅ 基本查询: 2 个结果
   ✅ 元数据过滤查询: 2 个结果

🎉 所有核心CRUD操作测试完成！
============================================================
```

## 🚨 故障排除

### 常见问题

#### 1. 连接失败
```
❌ 错误: 无法连接到Milvus服务
```
**解决方案:**
- 检查Milvus服务是否运行
- 验证host和port配置
- 确认网络连接

#### 2. 向量维度不匹配
```
❌ 错误: 向量维度不匹配
```
**解决方案:**
- 检查嵌入模型输出维度
- 验证Collection配置中的dimension
- 重新创建Collection

#### 3. 查询无结果
```
⚠️ 警告: 查询返回0个结果
```
**解决方案:**
- 降低similarity_threshold
- 增加top_k值
- 检查查询文本和文档语言是否匹配

#### 4. 内存不足
```
❌ 错误: 内存不足
```
**解决方案:**
- 减少batch_size
- 使用流式处理
- 增加系统内存

### 调试技巧

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 检查系统状态
async with RAGSystem() as rag:
    stats = await rag.get_collection_stats("collection_name")
    print(f"Collection状态: {stats}")
```

## 📚 相关文档

- [Milvus + LlamaIndex 完整功能指南](milvus_llamaindex_guide.md)
- [完整功能测试验证指南](complete_feature_guide.md)
- [Collection创建指南](examples/collection_creation_guide.md)
- [元数据过滤指南](examples/metadata_filtering_guide.md)
- [CRUD操作指南](examples/crud_operations_guide.md)

## 🎯 最佳实践

### 1. 文档设计
- 合理分割文档长度 (500-2000字符)
- 设计有意义的元数据字段
- 保持文档质量和相关性

### 2. 查询优化
- 使用具体明确的查询词
- 合理设置top_k和相似度阈值
- 利用元数据过滤提高精度

### 3. 系统维护
- 定期备份重要数据
- 监控系统性能指标
- 及时清理无用数据

## 📞 技术支持

如遇问题，请：
1. 查看本文档的故障排除部分
2. 运行测试用例验证功能
3. 检查配置文件设置
4. 查看系统日志获取详细错误信息

---

**最后更新**: 2024-07-13
**版本**: 2.0.0
**状态**: 生产就绪 ✅
  milvus:
    host: "localhost"
    port: 19530
    dimension: 1024
  ollama:
    base_url: "http://localhost:11434"
    embedding_model: "bge-m3"
  deepseek:
    model: "deepseek-chat"
    api_key: "your-api-key"
    base_url: "https://api.deepseek.com/v1"
```

### 服务层使用

```python
from backend.services.rag.rag_service import RAGService

service = RAGService()
await service.initialize()

# 添加文本
result = await service.add_text(
    "测试用例设计需要考虑边界条件",
    "testcase"
)

# 查询
result = await service.query("如何设计测试用例？", "testcase")
print(result['answer'])
```

## 📡 API接口

### Collection管理

- `GET /api/v1/rag/collections` - 获取所有Collections信息
- `GET /api/v1/rag/collections/{collection_name}` - 获取指定Collection信息
- `POST /api/v1/rag/collections/setup` - 设置Collection
- `POST /api/v1/rag/collections/setup-all` - 设置所有Collections

### 文档管理

- `POST /api/v1/rag/documents/add-text` - 添加文本到知识库
- `POST /api/v1/rag/documents/add-file` - 添加文件到知识库

### 查询接口

- `POST /api/v1/rag/query` - RAG查询
- `POST /api/v1/rag/query/multiple` - 多Collection查询
- `POST /api/v1/rag/query/business` - 业务类型查询
- `POST /api/v1/rag/chat` - RAG聊天

### 系统管理

- `GET /api/v1/rag/stats` - 获取系统统计信息
- `GET /api/v1/rag/health` - 健康检查
- `DELETE /api/v1/rag/collections/{collection_name}/clear` - 清空Collection数据
- `DELETE /api/v1/rag/clear-all` - 清空所有数据

## 🔧 Collection配置

每个Collection可以独立配置：

```python
@dataclass
class CollectionConfig:
    name: str                    # Collection名称
    description: str             # 描述
    dimension: int = 768         # 向量维度
    business_type: str = "general"  # 业务类型
    top_k: int = 5              # 检索数量
    similarity_threshold: float = 0.7  # 相似度阈值
    chunk_size: int = 1000      # 分块大小
    chunk_overlap: int = 200    # 分块重叠
```

## 🧪 测试

运行集成测试：

```bash
cd backend/rag_core
python test_integration.py
```

测试内容：
- 配置验证
- 核心系统初始化
- 服务层功能
- 基本RAG功能（需要外部服务）

## 📁 目录结构

```
backend/rag_core/
├── __init__.py              # 模块初始化
├── collection_manager.py    # Collection管理器
├── data_loader.py          # 文档加载器
├── embedding_generator.py  # 嵌入生成器
├── llm_service.py          # LLM服务
├── query_engine.py         # 查询引擎
├── rag_system.py           # 主系统类
├── vector_store.py         # 向量数据库
├── test_integration.py     # 集成测试
└── docs/                   # 完整文档系统
    ├── README.md           # 本文件
    ├── architecture.md     # 系统架构
    ├── development_guide.md # 开发规范
    ├── api_reference.md    # API参考
    ├── configuration.md    # 配置管理
    ├── troubleshooting.md  # 故障排除
    ├── changelog.md        # 更新日志
    └── examples/           # 示例代码
        ├── basic_usage.py
        ├── advanced_usage.py
        ├── custom_collection.py
        ├── integration_examples.py
        └── test_rag_docs_completeness.py
```

## 📖 详细文档

### 🏗️ [系统架构](architecture.md)
了解RAG系统的整体架构设计、组件关系和数据流。

### 🛠️ [开发规范](development_guide.md)
开发RAG相关功能的规范、最佳实践和代码风格指南。

### 📡 [API参考](api_reference.md)
完整的API接口文档，包括所有类、方法和参数说明。

### ⚙️ [配置管理](configuration.md)
RAG系统的配置选项、环境变量和自定义配置方法。

### 🆕 [Milvus + LlamaIndex 使用指南](milvus_llamaindex_guide.md)
完整的 Milvus 向量数据库和 LlamaIndex 框架使用指南，包括环境准备、基础概念、配置说明、基本使用、高级功能、最佳实践和故障排除。

### 🆕 [Milvus 过滤查询指南](milvus_filter_query_guide.md)
详细介绍如何在 Milvus + LlamaIndex RAG 系统中使用过滤条件进行精确查询，包括元数据过滤、复杂表达式、最佳实践和调试技巧。

### 🆕 [问题解决方案总结](problem_solution_summary.md)
常见问题的详细分析和解决方案，特别是 DataNotMatchException 等向量数据库相关问题的技术要点。

### 💡 [示例代码](examples/)
丰富的示例代码，涵盖基础使用、高级功能和集成场景。包括新增的 Milvus 基础和高级使用示例。

### 🔧 [故障排除](troubleshooting.md)
常见问题的解决方案和调试技巧。

## 🎯 AI编程助手指南

### 开发新功能时的步骤

1. **查看架构文档** - 了解系统设计和组件关系
2. **参考API文档** - 确认可用的接口和方法
3. **查看示例代码** - 学习最佳实践和使用模式
4. **遵循开发规范** - 确保代码质量和一致性
5. **测试和验证** - 使用提供的测试模板

### 常用开发模式

```python
# 模式1: 基础RAG查询
async with RAGSystem() as rag:
    result = await rag.query("问题", "collection_name")

# 模式2: 多Collection查询
async with RAGSystem() as rag:
    results = await rag.query_multiple_collections("问题", ["col1", "col2"])

# 模式3: 业务类型查询
async with RAGSystem() as rag:
    results = await rag.query_business_type("问题", "testcase")

# 模式4: 文档管理
async with RAGSystem() as rag:
    await rag.add_file("document.pdf", "general")
    await rag.add_text("文本内容", "general")
```

## 🔗 集成说明

### 与现有服务集成

RAG系统已集成到后端架构中：

1. **配置系统**: 使用统一的配置管理
2. **服务层**: 遵循现有的服务层模式
3. **API层**: 集成到FastAPI路由系统
4. **日志系统**: 使用loguru统一日志

### 为业务服务提供支持

不同业务可以使用对应的collection：

```python
# 测试用例服务使用testcase collection
result = await rag_service.query_business_type(
    "如何设计边界测试用例？",
    "testcase"
)

# UI测试服务使用ui_testing collection
result = await rag_service.query_business_type(
    "如何定位页面元素？",
    "ui_testing"
)
```

## 🚨 注意事项

1. **依赖服务**: 需要Milvus和Ollama服务运行
2. **API密钥**: 需要配置DeepSeek API密钥
3. **资源管理**: 使用异步上下文管理器确保资源清理
4. **错误处理**: 所有操作都有完整的错误处理和日志记录

## 🔮 未来扩展

1. **更多向量数据库**: 支持其他向量数据库
2. **更多LLM**: 支持其他大语言模型
3. **高级检索**: 支持混合检索、重排序等
4. **缓存机制**: 添加查询结果缓存
5. **监控指标**: 添加性能监控和指标收集

## 🔗 相关链接

- [LlamaIndex文档](https://docs.llamaindex.ai/)
- [Milvus文档](https://milvus.io/docs)
- [DeepSeek API文档](https://platform.deepseek.com/api-docs/)
- [Ollama文档](https://ollama.ai/docs)

## 📞 支持

如果在使用过程中遇到问题：

1. 查看 [故障排除文档](troubleshooting.md)
2. 检查 [示例代码](examples/)
3. 参考 [API文档](api_reference.md)
4. 查看系统日志获取详细错误信息

## 🔄 版本信息

当前版本: v1.0.0

查看 [更新日志](changelog.md) 了解版本变更详情。
