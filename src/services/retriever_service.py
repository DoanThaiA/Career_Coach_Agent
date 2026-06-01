from __future__ import annotations

import asyncio
from typing import List, Optional, Tuple

from langchain_core.documents import Document

from src.core.logger import get_logger
from src.db.qdrant import QdrantDocumentStore, QdrantConfig
from src.services.embedding_service import EmbeddingService
from src.services.rerank_service import RerankerService

logger = get_logger(__name__)

class RetrieverService:
    def __init__(self):
        qdrant_config = QdrantConfig()
        embedding_service = EmbeddingService()
        self.qdrant_store = QdrantDocumentStore(qdrant_config, embedding_service)
        self.reranker= RerankerService()
    
    async def retrieve(
            self,
            query: str,
            qdrant_top_k: int = 10,
            rerank_top_k: int = 3,
            filter_dict: Optional[dict] = None,
            rerank_threshold: Optional[float] = 0.5,
        ) -> List[Tuple[Document, float]]: 
        qdrant_docs: List[Document] = await self.qdrant_store.search(
            query=query,
            top_k=qdrant_top_k,
            filter_dict=filter_dict,
        )

        texts = [doc.page_content for doc in qdrant_docs]
        rerank_results = await asyncio.to_thread(
            self.reranker.rerank,
            query,
            texts,
            rerank_top_k,
            rerank_threshold,
        )
        return rerank_results

_retriever_instance: RetrieverService | None = None


def get_retriever_service() -> RetrieverService:
    """Lazy singleton — tạo RetrieverService 1 lần duy nhất."""
    global _retriever_instance
    if _retriever_instance is None:
        logger.info("[singleton] Khởi tạo RetrieverService instance...")
        _retriever_instance = RetrieverService()
    return _retriever_instance