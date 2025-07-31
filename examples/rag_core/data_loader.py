"""
数据加载模块
基于LlamaIndex的文档加载和分割功能
"""

from pathlib import Path
from typing import List, Optional, Union

from llama_index.core import Document, SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import BaseNode
from loguru import logger

from backend.conf.rag_config import CollectionConfig


class DocumentLoader:
    """文档加载器"""

    def __init__(
        self,
        collection_config: Optional[CollectionConfig] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        """
        初始化文档加载器

        Args:
            collection_config: Collection配置
            chunk_size: 分块大小
            chunk_overlap: 分块重叠
        """
        if collection_config:
            self.chunk_size = collection_config.chunk_size
            self.chunk_overlap = collection_config.chunk_overlap
        else:
            self.chunk_size = chunk_size
            self.chunk_overlap = chunk_overlap

        # 创建文本分割器
        self.text_splitter = SentenceSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

        logger.info(
            f"📚 文档加载器初始化 - 分块大小: {self.chunk_size}, 重叠: {self.chunk_overlap}"
        )

    def load_from_file(self, file_path: Union[str, Path]) -> List[Document]:
        """
        从单个文件加载文档

        Args:
            file_path: 文件路径

        Returns:
            List[Document]: 文档列表
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        logger.info(f"📖 开始加载文件: {file_path}")

        try:
            # 使用SimpleDirectoryReader加载单个文件
            reader = SimpleDirectoryReader(
                input_files=[str(file_path)], recursive=False
            )

            documents = reader.load_data()

            # 添加文件路径到元数据
            for doc in documents:
                doc.metadata.update(
                    {
                        "file_path": str(file_path),
                        "file_name": file_path.name,
                        "file_size": file_path.stat().st_size,
                    }
                )

            logger.success(f"✅ 文件加载完成: {len(documents)} 个文档")
            return documents

        except Exception as e:
            logger.error(f"❌ 文件加载失败: {e}")
            raise

    def load_from_directory(
        self, directory_path: Union[str, Path], recursive: bool = True, **kwargs
    ) -> List[Document]:
        """
        从目录加载文档

        Args:
            directory_path: 目录路径
            recursive: 是否递归加载
            **kwargs: 其他参数

        Returns:
            List[Document]: 文档列表
        """
        directory_path = Path(directory_path)

        if not directory_path.exists():
            raise FileNotFoundError(f"目录不存在: {directory_path}")

        logger.info(f"📁 开始加载目录: {directory_path}")

        try:
            # 使用SimpleDirectoryReader加载目录
            reader = SimpleDirectoryReader(
                input_dir=str(directory_path), recursive=recursive, **kwargs
            )

            documents = reader.load_data()

            # 添加目录信息到元数据
            for doc in documents:
                doc.metadata.update({"source_directory": str(directory_path)})

            logger.success(f"✅ 目录加载完成: {len(documents)} 个文档")
            return documents

        except Exception as e:
            logger.error(f"❌ 目录加载失败: {e}")
            raise

    def load_from_text(
        self, text: str, metadata: Optional[dict] = None
    ) -> List[Document]:
        """
        从文本字符串创建文档

        Args:
            text: 文本内容
            metadata: 元数据

        Returns:
            List[Document]: 文档列表
        """
        logger.info(f"📝 从文本创建文档，长度: {len(text)}")

        try:
            # 创建文档
            document = Document(text=text, metadata=metadata or {})

            logger.success("✅ 文本文档创建完成")
            return [document]

        except Exception as e:
            logger.error(f"❌ 文本文档创建失败: {e}")
            raise

    def split_documents(self, documents: List[Document]) -> List[BaseNode]:
        """
        分割文档为节点

        Args:
            documents: 文档列表

        Returns:
            List[BaseNode]: 节点列表
        """
        if not documents:
            logger.warning("⚠️ 文档列表为空，跳过分割")
            return []

        logger.info(f"✂️ 开始分割文档 - 文档数量: {len(documents)}")

        try:
            # 使用文本分割器分割文档
            nodes = self.text_splitter.get_nodes_from_documents(documents)

            logger.success(f"✅ 文档分割完成: {len(nodes)} 个节点")
            return nodes

        except Exception as e:
            logger.error(f"❌ 文档分割失败: {e}")
            raise

    def load_and_split(
        self, source: Union[str, Path], is_directory: bool = False, **kwargs
    ) -> List[BaseNode]:
        """
        加载并分割文档的便捷方法

        Args:
            source: 文件或目录路径
            is_directory: 是否为目录
            **kwargs: 其他参数

        Returns:
            List[BaseNode]: 节点列表
        """
        if is_directory:
            documents = self.load_from_directory(source, **kwargs)
        else:
            documents = self.load_from_file(source)

        return self.split_documents(documents)

    def load_and_split_text(
        self, text: str, metadata: Optional[dict] = None
    ) -> List[BaseNode]:
        """
        加载文本并分割为节点的便捷方法

        Args:
            text: 文本内容
            metadata: 元数据

        Returns:
            List[BaseNode]: 节点列表
        """
        documents = self.load_from_text(text, metadata)
        return self.split_documents(documents)

    def get_loader_info(self) -> dict:
        """
        获取加载器信息

        Returns:
            dict: 加载器信息
        """
        return {
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "splitter_type": type(self.text_splitter).__name__,
        }


def create_document_loader(
    collection_config: Optional[CollectionConfig] = None,
) -> DocumentLoader:
    """
    创建文档加载器

    Args:
        collection_config: Collection配置

    Returns:
        DocumentLoader: 文档加载器
    """
    return DocumentLoader(collection_config)


if __name__ == "__main__":
    logger.info("*******************🔄 文档加载器测试 🔄*******************")
    # 测试代码
    from backend.conf.rag_config import get_rag_config

    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    loader = create_document_loader(collection_config)

    # 测试文本加载
    test_text = """
    人工智能（AI）是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。
    机器学习是人工智能的一个子集，它使计算机能够从数据中学习而无需明确编程。
    深度学习是机器学习的一个子集，使用神经网络来模拟人脑的工作方式。
    自然语言处理（NLP）是人工智能的一个分支，专注于计算机与人类语言之间的交互。
    计算机视觉是人工智能的另一个重要分支，使计算机能够理解和解释视觉信息。
    """

    # 测试文本加载和分割
    nodes = loader.load_and_split_text(test_text, {"source": "test", "topic": "AI"})
    print(f"创建了 {len(nodes)} 个节点")

    for i, node in enumerate(nodes):
        print(f"节点 {i+1}: {node.text[:100]}...")
        print(f"元数据: {node.metadata}")
        print("---")

    # 获取加载器信息
    loader_info = loader.get_loader_info()
    print(f"加载器信息: {loader_info}")
