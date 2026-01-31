"""
NotebookLM 頁面物件模組。

每個頁面代表 NotebookLM 中的一個獨立視圖：
- base.py: 基礎頁面類別，提供共用方法
- notebooks.py: 筆記本列表頁面
- notebook_detail.py: 單一筆記本詳細頁面
"""

from .base import BasePage
from .notebooks import NotebooksPage, NotebookInfo
from .notebook_detail import NotebookDetailPage, NotebookDetail, SourceInfo, SourceType

__all__ = [
    "BasePage",
    "NotebooksPage",
    "NotebookInfo",
    "NotebookDetailPage",
    "NotebookDetail",
    "SourceInfo",
    "SourceType",
]
