# RAG服务文档和代码结构

本文档描述了RAG服务的最终文档结构和代码组织。

## 📁 整体结构

```
backend/rag_core/
├── 📚 核心模块
│   ├── rag_system.py              # RAG系统主入口 - 对外统一接口
│   ├── collection_manager.py      # Collection管理器
│   ├── query_engine.py           # 查询引擎 - 检索和生成
│   ├── vector_store.py           # 向量数据库接口 - Milvus操作
│   ├── embedding_generator.py    # 嵌入向量生成器 - BGE-M3
│   ├── llm_service.py            # LLM服务 - DeepSeek集成
│   └── data_loader.py            # 数据加载器 - 文档处理
│
├── 📖 文档系统
│   ├── docs/
│   │   ├── README.md                      # 📋 RAG服务使用文档 (主文档)
│   │   ├── rag_service_guide.md           # 🎯 RAG服务完整使用指南
│   │   ├── milvus_llamaindex_guide.md     # 🔧 Milvus+LlamaIndex技术指南
│   │   └── examples/                      # 📚 详细示例和指南
│   │       ├── collection_creation_guide.md    # Collection创建指南
│   │       ├── metadata_filtering_guide.md     # 元数据过滤指南
│   │       └── crud_operations_guide.md        # CRUD操作指南
│
├── 🧪 测试和示例
│   ├── rag_complete_example.py    # 🎯 完整RAG工作流程演示
│   └── test_core_crud.py         # ✅ 核心CRUD功能测试
│
└── 📁 运行时目录
    ├── logs/                      # 日志文件
    └── uploads/                   # 上传文件存储
```

## 📚 文档系统说明

### 主要文档

1. **README.md** - RAG服务使用文档
   - RAG基本概念和五个关键阶段
   - 快速开始指南
   - 核心API使用示例
   - 配置说明和故障排除

2. **rag_service_guide.md** - RAG服务完整使用指南
   - 基于RAGSystem的完整API文档
   - 实际测试结果展示
   - 最佳实践和性能优化
   - 生产环境使用指南

3. **milvus_llamaindex_guide.md** - 技术实现指南
   - Milvus + LlamaIndex 完整功能说明
   - 向量数据库CRUD操作详解
   - 元数据过滤和高级查询
   - 技术架构和实现细节

### 详细示例文档

4. **collection_creation_guide.md** - Collection创建指南
   - Collection的创建和管理
   - 配置参数详解
   - 最佳实践和故障排除

5. **metadata_filtering_guide.md** - 元数据过滤指南
   - 各种过滤操作的详细示例
   - 实际应用场景
   - 性能优化建议

6. **crud_operations_guide.md** - CRUD操作指南
   - 完整的增删改查操作
   - 异步操作和批量处理
   - 高级功能使用

## 🧪 测试和示例代码

### 核心示例

1. **rag_complete_example.py** - 完整RAG工作流程演示
   - 展示RAG的五个关键阶段
   - 从数据加载到回答生成的完整流程
   - 包含性能测试和高级功能演示

2. **test_core_crud.py** - 核心功能测试
   - Collection管理测试
   - 节点CRUD操作测试
   - 异步操作和批量处理测试

## 🎯 核心模块说明

### 对外接口

- **RAGSystem** (`rag_system.py`)
  - 统一的对外接口
  - 管理所有子组件
  - 提供完整的RAG功能

### 核心组件

- **CollectionManager** (`collection_manager.py`)
  - 管理多个Collection
  - 按需初始化
  - 业务类型分类

- **QueryEngine** (`query_engine.py`)
  - 检索和生成引擎
  - 结合向量搜索和LLM
  - 上下文增强

- **VectorStore** (`vector_store.py`)
  - Milvus向量数据库操作
  - 完整的CRUD功能
  - 元数据过滤支持

- **EmbeddingGenerator** (`embedding_generator.py`)
  - BGE-M3嵌入模型
  - 批量向量生成
  - Ollama集成

- **LLMService** (`llm_service.py`)
  - DeepSeek模型集成
  - 流式输出支持
  - 上下文管理

- **DocumentLoader** (`data_loader.py`)
  - 文档解析和处理
  - 文本分割
  - 元数据提取

## 🔧 配置和部署

### 配置文件

RAG系统的配置在 `backend/conf/settings.yaml` 中：

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
        chunk_size: 1000
        chunk_overlap: 200

  ollama:
    base_url: "http://localhost:11434"
    embedding_model: "bge-m3"

  deepseek:
    api_key: "your_api_key"
    model: "deepseek-chat"
```

### 依赖要求

- Python 3.8+
- LlamaIndex >= 0.9.0
- pymilvus >= 2.3.0
- 运行中的Milvus服务
- 运行中的Ollama服务 (BGE-M3模型)
- DeepSeek API密钥

## 🚀 快速开始

### 1. 运行完整示例

```bash
cd backend/rag_core
PYTHONPATH=/path/to/project python3 rag_complete_example.py
```

### 2. 运行核心测试

```bash
PYTHONPATH=/path/to/project python3 test_core_crud.py
```

### 3. 基本使用

```python
from backend.rag_core.rag_system import RAGSystem

async def basic_usage():
    async with RAGSystem() as rag:
        # 设置Collection
        await rag.setup_collection("my_knowledge")

        # 添加文档
        await rag.add_text("人工智能是...", "my_knowledge")

        # 查询
        result = await rag.query("什么是AI？", "my_knowledge")
        print(result.answer)
```

## 📊 功能验证状态

### ✅ 已验证功能

- **RAG完整流程**: 加载 → 索引 → 存储 → 查询 → 生成
- **Collection管理**: 创建、删除、统计、清空
- **文档处理**: 文本添加、文件导入、批量处理
- **向量操作**: 嵌入生成、相似性搜索、CRUD操作
- **元数据过滤**: 多种操作符、逻辑组合
- **异步操作**: 完整的异步支持
- **LLM集成**: DeepSeek模型、上下文增强

### 🎯 测试结果

根据实际运行测试：
- ✅ 成功索引5个示例文档
- ✅ 文本分割、向量嵌入、元数据提取正常
- ✅ 数据持久化到Milvus成功
- ✅ 系统资源管理和清理正常

## 📝 维护说明

### 文档更新

1. 主要功能变更时更新 `README.md`
2. API变更时更新 `rag_service_guide.md`
3. 技术实现变更时更新 `milvus_llamaindex_guide.md`
4. 新增示例时在 `examples/` 目录添加

### 代码维护

1. 保持RAGSystem作为统一入口
2. 新功能优先在核心模块实现
3. 测试用例与功能同步更新
4. 保持文档与代码的一致性

---

**文档版本**: 2.0.0
**最后更新**: 2024-07-13
**状态**: 生产就绪 ✅
