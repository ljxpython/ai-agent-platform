"""
RAG核心模块
基于Milvus向量数据库、Ollama大模型服务、llama_index框架的RAG知识库系统
支持多collection架构，为不同业务提供专业知识库
"""

from .collection_manager import CollectionManager
from .data_loader import DocumentLoader
from .embedding_generator import EmbeddingGenerator
from .llm_service import LLMService
from .query_engine import QueryResult, RAGQueryEngine
from .rag_system import RAGSystem
from .vector_store import MilvusVectorDB

__all__ = [
    "RAGSystem",
    "CollectionManager",
    "DocumentLoader",
    "EmbeddingGenerator",
    "LLMService",
    "RAGQueryEngine",
    "QueryResult",
    "MilvusVectorDB",
]
