"""
MCP 工具處理器模組。

每個工具在獨立的模組中實作：
- health_check.py - 驗證連線和認證狀態
- list_notebooks.py - 列出所有筆記本
- get_notebook.py - 取得筆記本詳細資訊
- list_sources.py - 列出筆記本中的來源
- add_source.py - 新增 URL 或文字來源
- ask.py - 向筆記本提問
"""

from .health_check import HealthCheckResult, health_check
from .list_notebooks import ListNotebooksResult, list_notebooks
from .get_notebook import GetNotebookResult, get_notebook
from .list_sources import ListSourcesResult, list_sources
from .add_source import AddSourceResult, add_source
from .ask import AskResult, Citation, ask

__all__ = [
    # M1: Auth Flow
    "health_check",
    "HealthCheckResult",
    # M2: Read Operations
    "list_notebooks",
    "ListNotebooksResult",
    "get_notebook",
    "GetNotebookResult",
    "list_sources",
    "ListSourcesResult",
    # M3: Write Operations
    "add_source",
    "AddSourceResult",
    # M4: Query
    "ask",
    "AskResult",
    "Citation",
]
