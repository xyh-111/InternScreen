"""PDF 文本提取。"""

from pathlib import Path

import pdfplumber


def extract_pdf_text(file_path: str) -> str:
    """使用 pdfplumber 逐页提取 PDF 文本。"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF 文件不存在：{file_path}")

    texts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            texts.append(page.extract_text() or "")
    return "\n".join(texts)
