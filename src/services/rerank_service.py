from typing import Optional,List,Tuple
import cohere
from src.core.config import settings
from src.core.logger import get_logger
from langchain_core.documents import Document

logger = get_logger(__name__)

class RerankerService:
    def __init__(self):
        logger.info(f"Initializing RerankerService with model: {settings.RERANK_MODEL}")
        self.client = cohere.ClientV2(api_key=settings.COHERE_API_KEY)

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
        
        response = self.client.rerank(
            model=settings.RERANK_MODEL,
            query=query,
            documents=texts,
            top_n=top_k
        )
        
        scored_results = []
        for result in response.results:
            score = result.relevance_score
            if score_threshold is None or score >= score_threshold:
                scored_results.append((documents[result.index], score))
                
        return scored_results
