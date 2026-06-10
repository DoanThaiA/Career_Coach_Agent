from src.services.retriever_service import get_retriever_service
from src.core.logger import get_logger
import asyncio

logger = get_logger(__name__)

async def main():
    retriever = get_retriever_service()
    queries = ["THÔNG TIN TUYỂN DỤNG THÔNG TIN CHUNG VỊ TRÍ/CHỨC DANH NHÂN VIÊN CHĂM SÓC KHÁCH HÀNG ĐA KÊNH TÊN DỰ ÁN/ĐỐI TÁC TẬP ĐOÀN CÔNG NGHỆ CMC la gi","what is the skill and project of Doan Quoc Thai"]
    for q in queries:
        docs = await retriever.retrieve(q)
        logger.info(f"Query: {q}")
        for doc, score in docs:
            logger.info(f"Score: {score} - {doc.page_content}")

if __name__ == "__main__":
    asyncio.run(main())