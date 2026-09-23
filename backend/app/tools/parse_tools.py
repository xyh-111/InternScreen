"""解析工具：文本清洗与 PDF 提取。"""

import re

from langchain_core.tools import tool

from app.services.pdf_parser import extract_pdf_text


@tool
def parse_text_tool(text: str) -> str:
    """清洗纯文本简历"""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@tool
def parse_pdf_tool(file_path: str) -> str:
    """使用 pdfplumber 提取 PDF 文本"""
    return extract_pdf_text(file_path)
