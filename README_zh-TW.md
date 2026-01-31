# kof-notebooklm-mcp

[![PyPI version](https://badge.fury.io/py/kof-notebooklm-mcp.svg)](https://badge.fury.io/py/kof-notebooklm-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![English](https://img.shields.io/badge/Docs-English-blue)](./README.md)

**Google NotebookLM 的 MCP Server** — 直接從 IDE 建立筆記本、新增來源、詢問 AI 並獲得附帶引用的答案。

> 🧠 [KOF-LocalBrain](https://github.com/keeponfirst/keeponfirst-local-brain) 生態系的一部分

---

## 功能特色

- 🆕 **建立筆記本** — 程式化建立並命名 NotebookLM 筆記本
- 📄 **新增來源** — 直接上傳網址或貼上文字
- 💬 **詢問問題** — 查詢 AI 並獲得附帶來源引用的答案
- 📋 **列表與檢視** — 瀏覽筆記本及其來源
- 🔐 **持久化登入** — 登入一次，跨運行重複使用 Session

---

## 安裝

```bash
pip install kof-notebooklm-mcp
```

### 安裝後設定

```bash
# 安裝 Playwright 瀏覽器
playwright install chromium

# 初始化認證（會開啟瀏覽器進行 Google 登入）
kof-notebooklm-init
```

---

## 快速開始

### 作為 MCP Server

加入您的 MCP 設定檔（`mcp_config.json`）：

```json
{
  "mcpServers": {
    "notebooklm": {
      "command": "kof-notebooklm-mcp",
      "args": []
    }
  }
}
```

### 可用工具

| 工具 | 說明 |
|------|------|
| `health_check` | 驗證連線與登入狀態 |
| `list_notebooks` | 列出所有筆記本 |
| `create_notebook` | 建立新筆記本（可指定標題） |
| `get_notebook` | 取得筆記本詳細資訊 |
| `list_sources` | 列出筆記本內的來源 |
| `add_source` | 新增網址或文字來源 |
| `ask` | 詢問 AI 並獲得附帶引用的答案 |

### 使用範例（透過 MCP 客戶端）

```python
# 建立研究筆記本
result = await mcp.call_tool("create_notebook", {"title": "市場研究 2026"})
notebook_id = result["notebook_id"]

# 新增來源
await mcp.call_tool("add_source", {
    "notebook_id": notebook_id,
    "source_type": "url",
    "url": "https://example.com/report.pdf"
})

# 詢問問題
answer = await mcp.call_tool("ask", {
    "notebook_id": notebook_id,
    "question": "主要的市場趨勢是什麼？"
})
print(answer["answer"])
print(answer["citations"])
```

---

## 設定

環境變數（選填）：

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `KOF_NOTEBOOKLM_HEADLESS` | 以 Headless 模式運行瀏覽器 | `true` |
| `KOF_NOTEBOOKLM_PROFILE_DIR` | 瀏覽器 Profile 目錄 | `~/.kof-notebooklm/profile` |

---

## 開發

```bash
git clone https://github.com/keeponfirst/kof-notebooklm-mcp.git
cd kof-notebooklm-mcp

pip install -e ".[dev]"
pytest
```

---

## 授權

MIT License - 詳見 [LICENSE](LICENSE)

---

## 相關專案

- [KOF-LocalBrain](https://github.com/keeponfirst/keeponfirst-local-brain) — 本地優先的大腦擷取系統
- [Model Context Protocol](https://modelcontextprotocol.io/) — AI 工具整合標準
