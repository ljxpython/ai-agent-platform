# RAG服务完整使用指南

本文档提供RAG (Retrieval-Augmented Generation) 服务的完整使用指南，基于RAGSystem作为统一入口。

## 🎯 RAG系统概述

RAGSystem是我们RAG服务的统一对外接口，实现了完整的RAG工作流程：

```
用户查询 → 向量检索 → 相关文档 → 上下文增强 → LLM生成 → 最终回答
```

## 🔄 RAG五个关键阶段

### 1. 加载 (Loading)
从各种数据源导入数据：
- 文本内容直接添加
- 文件路径批量导入
- 支持多种格式和编码

### 2. 索引 (Indexing)
创建向量索引：
- 自动文本分割 (chunk_size: 1000, overlap: 200)
- BGE-M3模型生成1024维向量
- 元数据提取和存储

### 3. 存储 (Storing)
持久化到Milvus：
- 向量数据存储
- 元数据索引
- Collection管理

### 4. 查询 (Querying)
智能检索：
- 语义相似性搜索
- 元数据过滤
- 多Collection查询

### 5. 生成 (Generation)
LLM回答生成：
- DeepSeek模型推理
- 上下文增强
- 结构化输出

## 🚀 核心API使用

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

        # 添加文本内容
        result = await rag.add_text(
            text="人工智能是计算机科学的一个分支，致力于创建智能系统。",
            collection_name="my_knowledge",
            metadata={
                "title": "AI概述",
                "category": "technology",
                "source": "教程",
                "year": 2024
            }
        )

        print(f"✅ 添加了 {result} 个文档节点")

asyncio.run(add_documents())
```

### 3. 文件批量导入

```python
async def import_files():
    """文件导入示例"""
    async with RAGSystem() as rag:
        await rag.setup_collection("documents")

        # 从文件导入
        result = await rag.add_file(
            file_path="path/to/document.txt",
            collection_name="documents"
        )

        print(f"✅ 从文件导入了 {result} 个文档节点")

asyncio.run(import_files())
```

### 4. 智能查询

```python
async def intelligent_query():
    """智能查询示例"""
    async with RAGSystem() as rag:
        # RAG查询（检索+生成）
        result = await rag.query(
            question="什么是人工智能？",
            collection_name="my_knowledge"
        )

        print(f"🤖 AI回答: {result.answer}")
        print(f"📚 参考文档: {len(result.contexts)} 个")

        # 显示上下文
        for i, context in enumerate(result.contexts, 1):
            print(f"   {i}. {context.metadata.get('title', 'Unknown')}")

asyncio.run(intelligent_query())
```

### 5. 元数据过滤查询

```python
async def filtered_query():
    """元数据过滤查询示例"""
    async with RAGSystem() as rag:
        # 按类别和年份过滤
        result = await rag.query_with_filters(
            question="最新的AI技术发展",
            collection_name="my_knowledge",
            metadata_filters={
                "category": "technology",
                "year": 2024
            }
        )

        print(f"🔍 过滤查询结果: {result.answer}")

asyncio.run(filtered_query())
```

## 📊 实际测试结果

根据我们的完整测试，RAG系统已成功实现：

```
================================================================================
🤖 RAG系统完整工作流程演示
================================================================================

📂 阶段1: 数据加载(Loading)
✅ 准备了 5 个示例文档
   1. 人工智能概述 (zh)
   2. 机器学习基础 (zh)
   3. 深度学习原理 (zh)
   4. 自然语言处理技术 (zh)
   5. Large Language Models (en)

🔍 阶段2: 数据索引(Indexing)
✅ Collection 'general' 设置完成
✅ 成功索引 5 个文档
   - 文本分割完成
   - 向量嵌入生成完成
   - 元数据提取完成

💾 阶段3: 数据存储(Storing)
✅ 数据已持久化存储到Milvus
   - Collection: general_knowledge
   - 维度: 1024
   - 连接状态: 正常
```

## 🔧 支持的Collection类型

系统预配置了多种业务类型的Collection：

| Collection | 用途 | 说明 |
|-----------|------|------|
| `general` | 通用知识库 | 默认Collection，适用于一般文档 |
| `testcase` | 测试用例知识库 | 专门存储测试相关文档 |
| `ui_testing` | UI测试知识库 | UI测试相关的知识和案例 |
| `ai_chat` | AI对话知识库 | 对话和聊天相关的知识 |

## 🎯 核心方法总览

### Collection管理
- `setup_collection(name, overwrite=False)` - 设置Collection
- `setup_all_collections(overwrite=False)` - 设置所有Collection

### 文档添加
- `add_text(text, collection_name, metadata=None)` - 添加文本
- `add_file(file_path, collection_name)` - 添加文件

### 查询功能
- `query(question, collection_name, **kwargs)` - RAG查询
- `query_with_filters(question, collection_name, metadata_filters, **kwargs)` - 过滤查询
- `query_multiple_collections(question, collection_names, **kwargs)` - 多Collection查询
- `query_business_type(question, business_type, **kwargs)` - 按业务类型查询

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
        description: "通用知识库"
        business_type: "general"
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

### 关键参数说明

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| `dimension` | 向量维度 | 1024 (BGE-M3) |
| `top_k` | 检索文档数 | 3-10 |
| `similarity_threshold` | 相似度阈值 | 0.7 |
| `chunk_size` | 文本分块大小 | 1000 |
| `chunk_overlap` | 分块重叠 | 200 |

## 🧪 运行测试

### 完整工作流程测试

```bash
# 运行完整RAG工作流程演示
cd backend/rag_core
PYTHONPATH=/path/to/project python3 rag_complete_example.py
```

### 核心功能测试

```bash
# 运行核心CRUD功能测试
PYTHONPATH=/path/to/project python3 test_core_crud.py
```

## 🚨 常见问题

### 1. 连接失败
```
❌ 错误: 无法连接到Milvus服务
```
**解决方案:**
- 检查Milvus服务是否运行
- 验证配置文件中的host和port
- 确认网络连接

### 2. 向量维度不匹配
```
❌ 错误: 向量维度不匹配
```
**解决方案:**
- 确保配置的dimension与BGE-M3模型匹配(1024)
- 重新创建Collection

### 3. 查询无结果
```
⚠️ 警告: 查询返回0个结果
```
**解决方案:**
- 降低similarity_threshold
- 检查文档是否已正确添加
- 验证查询语言与文档语言匹配

## 🎯 最佳实践

### 1. 文档管理
- 合理设计元数据字段
- 保持文档质量和相关性
- 定期清理过时文档

### 2. 查询优化
- 使用具体明确的查询词
- 合理利用元数据过滤
- 根据业务场景选择合适的Collection

### 3. 性能优化
- 批量添加文档而非单个添加
- 合理设置top_k和相似度阈值
- 监控系统资源使用

### 4. 系统维护
- 定期备份重要数据
- 监控Collection状态
- 及时更新配置参数

## 📚 相关文档

- [Milvus + LlamaIndex 完整功能指南](milvus_llamaindex_guide.md)
- [Collection创建指南](examples/collection_creation_guide.md)
- [元数据过滤指南](examples/metadata_filtering_guide.md)
- [CRUD操作指南](examples/crud_operations_guide.md)

## 🎉 总结

RAGSystem提供了完整的RAG服务功能：

✅ **完整的工作流程**: 加载 → 索引 → 存储 → 查询 → 生成
✅ **多种数据源**: 文本、文件、批量导入
✅ **智能检索**: 语义搜索、元数据过滤、多Collection查询
✅ **LLM集成**: DeepSeek模型、上下文增强、结构化输出
✅ **生产就绪**: 完整的错误处理、日志记录、资源管理

现在你可以使用RAGSystem构建强大的知识库应用！

---

**最后更新**: 2024-07-13
**版本**: 2.0.0
**状态**: 生产就绪 ✅
