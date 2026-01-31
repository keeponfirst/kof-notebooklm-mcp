# kof-notebooklm-mcp 開發總結

> **建立日期**：2026-01-28
> **狀態**：MVP 完成

---

## 一、完成項目總覽

### 1.1 專案目標

建立一個 MCP (Model Context Protocol) 伺服器，讓 KOF 工作流程能夠程式化存取 Google NotebookLM，實現：
- 將 NotebookLM 作為研究工作區
- 自動化新增來源（URL、文字）
- 透過 AI 查詢筆記本並取得帶引用的回答

### 1.2 完成的功能

| 功能 | 說明 | 檔案 |
|------|------|------|
| **health_check** | 驗證連線和認證狀態 | `tools/health_check.py` |
| **list_notebooks** | 列出所有筆記本 | `tools/list_notebooks.py` |
| **get_notebook** | 取得筆記本詳細資訊 | `tools/get_notebook.py` |
| **list_sources** | 列出筆記本中的來源 | `tools/list_sources.py` |
| **add_source** | 新增 URL 或文字來源 | `tools/add_source.py` |
| **ask** | 向筆記本提問並取得 AI 回答 | `tools/ask.py` |

### 1.3 基礎設施

| 模組 | 說明 | 檔案 |
|------|------|------|
| **設定管理** | 環境變數載入、預設值 | `config.py` |
| **瀏覽器管理** | Playwright 持久化設定檔 | `client/browser.py` |
| **工作階段管理** | 互動式登入、工作階段驗證 | `client/session.py` |
| **頁面物件** | NotebookLM UI 自動化 | `client/pages/*.py` |
| **輸入驗證** | URL、文字、ID 驗證 | `utils/validation.py` |
| **重試邏輯** | 指數退避重試 | `utils/retry.py` |
| **速率限制** | Token Bucket 演算法 | `utils/rate_limit.py` |
| **斷路器** | 連續失敗保護 | `utils/circuit_breaker.py` |
| **錯誤處理** | 標準化錯誤碼和回應 | `utils/errors.py` |

### 1.4 程式碼統計

```
Python 程式碼：6,109 行
Markdown 文件：2,347 行
單元測試：81 個
總檔案數：37 個
```

---

## 二、技術實作方式

### 2.1 架構設計

```
┌─────────────────────────────────────────────────────────────┐
│                      MCP Client                              │
│                 (Claude Desktop / CLI)                       │
└─────────────────────────┬───────────────────────────────────┘
                          │ stdio (JSON-RPC)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   kof-notebooklm-mcp                         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                 MCP Server (server.py)                 │  │
│  │         速率限制 → 斷路器 → 工具處理器                   │  │
│  └───────────────────────┬───────────────────────────────┘  │
│                          │                                   │
│  ┌───────────────────────▼───────────────────────────────┐  │
│  │                   Tool Handlers                        │  │
│  │  health_check | list_notebooks | add_source | ask      │  │
│  └───────────────────────┬───────────────────────────────┘  │
│                          │                                   │
│  ┌───────────────────────▼───────────────────────────────┐  │
│  │                 NotebookLM Client                      │  │
│  │                                                        │  │
│  │   BrowserManager ─────► Playwright (Chromium)         │  │
│  │        │                                               │  │
│  │   SessionManager ─────► 持久化瀏覽器設定檔              │  │
│  │        │                                               │  │
│  │   Page Objects ───────► NotebookLM UI 自動化           │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼ HTTPS
┌─────────────────────────────────────────────────────────────┐
│                  notebooklm.google.com                       │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 關鍵技術決策

| 決策 | 選擇 | 原因 |
|------|------|------|
| **自動化方式** | Playwright 瀏覽器自動化 | NotebookLM 無官方 API |
| **認證方式** | 持久化瀏覽器設定檔 | 避免儲存密碼，支援 2FA |
| **程式語言** | Python | 與專案其他部分一致 |
| **速率限制** | Token Bucket | 防止過度請求被封鎖 |
| **錯誤處理** | 斷路器模式 | 連續失敗時保護系統 |

### 2.3 頁面物件模式 (Page Object Pattern)

為了應對 NotebookLM UI 可能的變化，採用多重選擇器策略：

```python
SELECTORS = {
    "notebook_cards": [
        '[data-testid="notebook-card"]',  # 優先：測試 ID
        '[role="listitem"]',               # 備選：語意角色
        '.notebook-card',                  # 備選：CSS 類別
        'a[href*="/notebook/"]',           # 備選：連結模式
    ],
}
```

### 2.4 錯誤處理策略

```
請求 → 速率限制檢查 → 斷路器檢查 → 執行操作
                                        │
                                        ▼
                              成功？─── 是 ───► 回傳結果
                                │              記錄成功
                               否
                                │
                                ▼
                         可重試錯誤？
                           │    │
                          是   否
                           │    │
                           ▼    ▼
                         重試  記錄失敗
                         (最多3次) 回傳錯誤
```

---

## 三、里程碑回顧

| 里程碑 | 內容 | 程式碼行數 |
|--------|------|------------|
| **M0: Skeleton** | 專案結構、pyproject.toml、基本骨架 | ~200 |
| **M1: Auth Flow** | config.py、browser.py、session.py、health_check | ~1,100 |
| **M2: Read Operations** | 頁面物件、list_notebooks、get_notebook、list_sources | ~1,100 |
| **M3: Write Operations** | validation.py、add_source（URL + 文字） | ~1,100 |
| **M4: Query** | 聊天 UI 自動化、ask 工具、引用提取 | ~950 |
| **M5: Polish** | retry.py、rate_limit.py、circuit_breaker.py、errors.py | ~1,800 |
| **M6: Docs & Testing** | README.md、TESTING.md、更新文件 | ~800 |

---

## 四、建議的未來功能

### 4.1 V1 功能（高優先級）

| 功能 | 說明 | 複雜度 |
|------|------|--------|
| **create_notebook** | 建立新筆記本 | 中 |
| **delete_source** | 刪除來源 | 低 |
| **rename_notebook** | 重新命名筆記本 | 低 |
| **get_source_content** | 取得來源內容摘要 | 中 |

### 4.2 V2 功能（中優先級）

| 功能 | 說明 | 複雜度 |
|------|------|--------|
| **delete_notebook** | 刪除筆記本（需確認機制） | 中 |
| **export_notes** | 匯出筆記為 Markdown | 中 |
| **batch_add_sources** | 批次新增多個來源 | 中 |
| **search_notebooks** | 搜尋筆記本 | 中 |

### 4.3 V3 功能（低優先級）

| 功能 | 說明 | 複雜度 |
|------|------|--------|
| **get_audio_overview** | 取得音訊概覽（生成耗時） | 高 |
| **share_notebook** | 分享筆記本 | 高 |
| **multi_account** | 支援多個 Google 帳號 | 高 |
| **cloud_deployment** | 雲端部署支援 | 高 |

### 4.4 改進建議

1. **選擇器穩定性**
   - 持續監控 NotebookLM UI 變化
   - 建立選擇器版本管理機制
   - 新增 UI 變化偵測警告

2. **效能優化**
   - 實作頁面快取（減少重複導航）
   - 平行處理多個獨立操作
   - 預載入常用頁面

3. **測試強化**
   - 新增整合測試（使用 mock 瀏覽器）
   - 建立 CI/CD 自動化測試流程
   - 視覺回歸測試

4. **使用者體驗**
   - 新增進度回報（長時間操作）
   - 改進錯誤訊息的可讀性
   - 新增操作歷史記錄

---

## 五、發布到 PyPI

### 5.1 前置準備

1. **建立 PyPI 帳號**
   - 前往 https://pypi.org/account/register/
   - 建議同時在 https://test.pypi.org/ 建立測試帳號

2. **設定 API Token**
   ```bash
   # 在 PyPI 網站建立 API token
   # 儲存到 ~/.pypirc
   cat > ~/.pypirc << 'EOF'
   [distutils]
   index-servers =
       pypi
       testpypi

   [pypi]
   username = __token__
   password = pypi-xxxxxxxxxxxxxxxx

   [testpypi]
   username = __token__
   password = pypi-xxxxxxxxxxxxxxxx
   EOF

   chmod 600 ~/.pypirc
   ```

### 5.2 更新套件資訊

編輯 `pyproject.toml`：

```toml
[project]
name = "kof-notebooklm-mcp"
version = "0.1.0"
description = "MCP server for Google NotebookLM integration"
readme = "README.md"
license = "MIT"
requires-python = ">=3.10"
authors = [
    { name = "Your Name", email = "your.email@example.com" }
]
keywords = ["mcp", "notebooklm", "google", "ai", "knowledge-management"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
]

[project.urls]
Homepage = "https://github.com/yourname/keeponfirst-local-brain"
Documentation = "https://github.com/yourname/keeponfirst-local-brain/tree/main/docs/kof-notebooklm-mcp"
Repository = "https://github.com/yourname/keeponfirst-local-brain"
Issues = "https://github.com/yourname/keeponfirst-local-brain/issues"
```

### 5.3 建置套件

```bash
cd packages/kof-notebooklm-mcp

# 安裝建置工具
pip install build twine

# 清理舊的建置檔案
rm -rf dist/ build/ *.egg-info

# 建置套件
python -m build

# 檢查套件
twine check dist/*
```

### 5.4 上傳到 Test PyPI（測試）

```bash
# 上傳到測試環境
twine upload --repository testpypi dist/*

# 測試安裝
pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    kof-notebooklm-mcp
```

### 5.5 上傳到 PyPI（正式）

```bash
# 確認版本號正確
grep "version" pyproject.toml

# 上傳到正式環境
twine upload dist/*

# 驗證安裝
pip install kof-notebooklm-mcp
```

### 5.6 版本管理

```bash
# 版本號規則 (Semantic Versioning)
# MAJOR.MINOR.PATCH
#
# 0.1.0 - 初始 MVP 版本
# 0.1.1 - Bug 修復
# 0.2.0 - 新增功能
# 1.0.0 - 穩定版本

# 更新版本時：
# 1. 修改 pyproject.toml 中的 version
# 2. 修改 src/kof_notebooklm_mcp/__init__.py 中的 __version__
# 3. 建立 git tag
git tag -a v0.1.0 -m "Release v0.1.0 - MVP"
git push origin v0.1.0
```

### 5.7 自動化發布（GitHub Actions）

建立 `.github/workflows/publish.yml`：

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build twine

      - name: Build package
        working-directory: packages/kof-notebooklm-mcp
        run: python -m build

      - name: Publish to PyPI
        working-directory: packages/kof-notebooklm-mcp
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: twine upload dist/*
```

### 5.8 安裝驗證清單

發布後驗證：

- [ ] `pip install kof-notebooklm-mcp` 成功
- [ ] `kof-notebooklm --help` 顯示說明
- [ ] `kof-notebooklm-init` 可執行
- [ ] `kof-notebooklm-health` 可執行
- [ ] `kof-notebooklm-mcp` 啟動 MCP 伺服器
- [ ] 在 Claude Desktop 中可正常使用

---

## 六、專案檔案結構

```
packages/kof-notebooklm-mcp/
├── pyproject.toml              # 套件設定
├── README.md                   # 使用指南
├── TESTING.md                  # 測試計畫
├── src/kof_notebooklm_mcp/
│   ├── __init__.py            # 套件入口
│   ├── config.py              # 設定管理 (75 行)
│   ├── server.py              # MCP 伺服器 (290 行)
│   ├── cli.py                 # CLI 指令 (94 行)
│   ├── client/
│   │   ├── __init__.py
│   │   ├── browser.py         # 瀏覽器管理 (164 行)
│   │   ├── session.py         # 工作階段管理 (167 行)
│   │   └── pages/
│   │       ├── __init__.py
│   │       ├── base.py        # 基礎頁面 (90 行)
│   │       ├── notebooks.py   # 筆記本列表 (200 行)
│   │       └── notebook_detail.py  # 筆記本詳細 (900 行)
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── health_check.py    # 健康檢查 (103 行)
│   │   ├── list_notebooks.py  # 列出筆記本 (70 行)
│   │   ├── get_notebook.py    # 取得筆記本 (75 行)
│   │   ├── list_sources.py    # 列出來源 (80 行)
│   │   ├── add_source.py      # 新增來源 (165 行)
│   │   └── ask.py             # 提問 (200 行)
│   └── utils/
│       ├── __init__.py
│       ├── validation.py      # 輸入驗證 (135 行)
│       ├── retry.py           # 重試邏輯 (180 行)
│       ├── rate_limit.py      # 速率限制 (220 行)
│       ├── circuit_breaker.py # 斷路器 (230 行)
│       └── errors.py          # 錯誤處理 (200 行)
└── tests/
    ├── __init__.py
    └── unit/
        ├── test_config.py         # 6 個測試
        ├── test_validation.py     # 15 個測試
        ├── test_health_check.py   # 3 個測試
        ├── test_page_objects.py   # 6 個測試
        ├── test_ask.py            # 8 個測試
        ├── test_retry.py          # 10 個測試
        ├── test_rate_limit.py     # 8 個測試
        ├── test_circuit_breaker.py # 10 個測試
        └── test_errors.py         # 15 個測試

docs/kof-notebooklm-mcp/
├── PLAN.md                    # 實作計畫
├── TOOLS.md                   # 工具規格
├── DECISIONS.md               # 架構決策
└── SUMMARY.md                 # 本文件
```

---

## 七、快速開始

```bash
# 1. 安裝
cd packages/kof-notebooklm-mcp
pip install -e ".[dev]"
playwright install chromium

# 2. 認證
kof-notebooklm-init

# 3. 驗證
kof-notebooklm-health

# 4. 執行測試
pytest tests/unit/ -v

# 5. 設定 Claude Desktop
# 編輯 ~/Library/Application Support/Claude/claude_desktop_config.json

# 6. 開始使用！
```

---

## 八、聯絡與貢獻

- **問題回報**：GitHub Issues
- **功能建議**：GitHub Discussions
- **貢獻指南**：參閱 CONTRIBUTING.md

---

> 本文件由 Claude (Opus 4.5) 於 2026-01-28 生成
