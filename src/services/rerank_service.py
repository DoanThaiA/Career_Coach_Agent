from typing import Optional,List,Tuple
from sentence_transformers import CrossEncoder
from src.core.config import settings
from src.core.logger import get_logger
from langchain_core.documents import Document

logger = get_logger(__name__)

class RerankerService:
    def __init__(self):
        logger.info(f"Initializing RerankerService with model: {settings.RERANK_MODEL}")
        self.model = CrossEncoder(settings.RERANK_MODEL)

    def rerank(
        self, 
        query: str, 
        documents: List[Document], 
        top_k: int = 5,
        score_threshold: Optional[float] = None
    ) -> List[Tuple[Document, float]]:
        """
        Chấm điểm lại sự liên quan giữa câu hỏi và các tài liệu
        """
        if not documents:
            return []
        
        texts = [doc.page_content for doc in documents]
        pairs = [[query, text] for text in texts]
        scores = self.model.predict(pairs)
        
        # Kết hợp document với score
        scored_results = list(zip(documents, scores))
        
        # Lọc theo threshold nếu có
        if score_threshold is not None:
            scored_results = [res for res in scored_results if res[1] >= score_threshold]
            
        # Sắp xếp và lấy top_k
        results = sorted(scored_results, key=lambda x: x[1], reverse=True)
        return results[:top_k]
