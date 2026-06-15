import asyncio
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP
from fastapi import HTTPException

from src.api.routes.interview import (
    start_interview,
    InterviewStartRequest,
    answer_question,
    InterviewAnswerRequest,
    get_interview_status,
    InterviewResponse,
)
from src.core.logger import get_logger

logger = get_logger(__name__)

# Khởi tạo MCP Server
mcp = FastMCP("Interview Agent MCP")

@mcp.tool()
async def start_interview_tool(cv_parsed: Dict[str, Any], jd_parsed: Dict[str, Any]) -> str:
    """
    Bắt đầu một phiên phỏng vấn mới với dữ liệu CV và JD.
    
    Args:
        cv_parsed: Dữ liệu CV đã được phân tích dưới dạng JSON object (dict).
        jd_parsed: Dữ liệu JD đã được phân tích dưới dạng JSON object (dict).
        
    Returns:
        Chuỗi JSON chứa thông tin khởi tạo phiên phỏng vấn (bao gồm thread_id và câu hỏi đầu tiên).
    """
    try:
        request = InterviewStartRequest(cv_parsed=cv_parsed, jd_parsed=jd_parsed)
        response: InterviewResponse = await start_interview(request)
        return response.model_dump_json()
    except HTTPException as e:
        logger.error(f"Lỗi khi bắt đầu phỏng vấn qua MCP: {e.detail}")
        return f'{{"error": "{e.detail}"}}'
    except Exception as e:
        logger.error(f"Lỗi không xác định khi bắt đầu phỏng vấn: {e}")
        return f'{{"error": "Lỗi hệ thống: {str(e)}"}}'

@mcp.tool()
async def answer_question_tool(thread_id: str, answer: str) -> str:
    """
    Gửi câu trả lời của ứng viên cho câu hỏi hiện tại.
    
    Args:
        thread_id: Mã định danh phiên phỏng vấn (nhận được từ start_interview_tool).
        answer: Nội dung câu trả lời của ứng viên.
        
    Returns:
        Chuỗi JSON chứa câu hỏi tiếp theo hoặc kết quả của buổi phỏng vấn.
    """
    try:
        request = InterviewAnswerRequest(thread_id=thread_id, answer=answer)
        response: InterviewResponse = await answer_question(request)
        return response.model_dump_json()
    except HTTPException as e:
        logger.error(f"Lỗi khi gửi câu trả lời qua MCP: {e.detail}")
        return f'{{"error": "{e.detail}"}}'
    except Exception as e:
        logger.error(f"Lỗi không xác định khi gửi câu trả lời: {e}")
        return f'{{"error": "Lỗi hệ thống: {str(e)}"}}'

@mcp.tool()
async def get_interview_status_tool(thread_id: str) -> str:
    """
    Lấy trạng thái hiện tại của phiên phỏng vấn.
    
    Args:
        thread_id: Mã định danh phiên phỏng vấn.
        
    Returns:
        Chuỗi JSON mô tả trạng thái hiện tại (bao gồm status, câu hỏi, điểm số, etc).
    """
    try:
        response: InterviewResponse = await get_interview_status(thread_id)
        return response.model_dump_json()
    except HTTPException as e:
        logger.error(f"Lỗi khi lấy trạng thái qua MCP: {e.detail}")
        return f'{{"error": "{e.detail}"}}'
    except Exception as e:
        logger.error(f"Lỗi không xác định khi lấy trạng thái: {e}")
        return f'{{"error": "Lỗi hệ thống: {str(e)}"}}'

if __name__ == "__main__":
    mcp.run()
