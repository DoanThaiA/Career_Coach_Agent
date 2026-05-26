import os
import fitz
import docx
from pdf2image import convert_from_path
from typing import Dict, Any, List, Optional
from src.core.logger import get_logger
from langchain_core.documents import Document

logger = get_logger(__name__)

class DocumentExtractService:
    def __init__(self, use_ocr :bool = True):
        self.use_ocr = use_ocr
        self._ocr_model=None
    
    @property
    def ocr_model(self):
        """Khoi tao Paddle OCR"""
        if self._ocr_model is None and self.use_ocr:
            logger.info("loading ocr model")
            from paddleocr import PaddleOCR
            self._ocr_model = PaddleOCR(use_angle_cls=True, lang="vi",use_gpu=False)
        return self._ocr_model

    def process_file(self, file_path:str) -> Dict[str,Any]:
       if not os.path.exists(file_path):
            return {"status": "error", "error": "File không tồn tại", "documents": []}
       
       ext = os.path.splitext(file_path)[1].lower()
       logger.info(f"Processing file {file_path} with extension {ext}")
       
       documents = []
       if ext == '.txt':
            documents = self._extract_txt(file_path)
       elif ext == '.docx':
            documents = self._extract_docx(file_path)
       elif ext == '.pdf':
            documents = self._extract_pdf(file_path)
            # Fallback to scanned PDF if no text extracted
            if not documents or all(not doc.page_content.strip() for doc in documents):
                logger.info(f"PDF might be scanned. Falling back to OCR for {file_path}")
                documents = self._extract_scanned_pdf(file_path)
       elif ext in ['.png', '.jpg', '.jpeg']:
            documents = self._extract_image(file_path)
       else:
            return {"status": "error", "error": f"Định dạng {ext} chưa được hỗ trợ", "documents": []}
            
       total_length = sum(len(doc.page_content) for doc in documents)
            
       return {
                "status": "success",
                "file_path": file_path,
                "text": documents, 
                "documents": documents,
                "metadata": {
                    "extension": ext, 
                    "num_documents": len(documents),
                    "total_length": total_length
                }
            }
    def _extract_txt(self,file_path:str) -> List[Document]:
        with open(file_path,'r',encoding='utf-8') as f:
            text = f.read()
            return [Document(page_content=text,metadata={"source":file_path})]
    def _extract_docx(self,file_path:str) -> List[Document]:
        doc = docx.Document(file_path)
        doc_list = []
        for para in doc.paragraphs:
            if para.text:
                doc_list.append(Document(page_content=para.text,metadata={
                    "source": file_path,
                    "type": "paragraph",
                }))
        for table in doc.tables:
            for row in table.rows:
                row_data = [cell.text.strip() for cell in row.cells]
                doc_list.append(Document(page_content="\t".join(row_data),metadata={
                    "source": file_path,
                    "type": "table",
                }))
        return doc_list
    def _extract_pdf(self, file_path:str) -> List[Document]:
        doc = fitz.open(file_path)
        doc_list = []
        for page in doc:
            text = page.get_text()
            doc_list.append(Document(page_content=text,metadata={
                "source": file_path,
                "page": page.number,
                "type": "page",
            }))
        return doc_list
    def _extract_scanned_pdf(self,file_path:str) -> List[Document]:
        pages = convert_from_path(file_path,dpi= 200)
        doc_list = []
        import tempfile
        for i, page in enumerate(pages):
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                temp_path = temp_file.name
            
            try:
                page.save(temp_path, 'PNG')
                image_docs = self._extract_image(temp_path)
                
                # Gom text từ các dòng (List[Document]) thành một đoạn text duy nhất cho trang đó
                page_text = "\n".join([doc.page_content for doc in image_docs])
                
                doc_list.append(Document(page_content=page_text,metadata={
                    "source": file_path,
                    "type": "scanned_page",
                    "page": i + 1
                }))
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        return doc_list
    def _extract_image(self, file_path:str) -> List[Document]:
        if self.use_ocr:
            result = self.ocr_model.ocr(file_path)
            if result:
                doc_list = []
                for line in result[0]:
                    doc_list.append(Document(page_content=line[1][0],metadata={
                        "source": file_path,
                        "type": "image",
                    }))
                return doc_list
        return []

            

        
    