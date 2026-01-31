# kof-notebooklm-mcp

[![PyPI version](https://badge.fury.io/py/kof-notebooklm-mcp.svg)](https://badge.fury.io/py/kof-notebooklm-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![中文文檔](https://img.shields.io/badge/文檔-繁體中文-blue)](./README_zh-TW.md)

**MCP Server for Google NotebookLM** — Create notebooks, add sources, and query AI with citations directly from your IDE.

> 🧠 Part of the [KOF-LocalBrain](https://github.com/keeponfirst/keeponfirst-local-brain) ecosystem

---

## Features

- 🆕 **Create Notebooks** — Programmatically create and name NotebookLM notebooks
- 📄 **Add Sources** — Upload URLs or paste text directly into notebooks
- 💬 **Ask Questions** — Query the AI and get answers with source citations
- 📋 **List & Inspect** — Browse notebooks and their sources
- 🔐 **Persistent Auth** — Login once, reuse session across runs

---

## Installation

```bash
pip install kof-notebooklm-mcp
```

### Post-install Setup

```bash
# Install Playwright browsers
playwright install chromium

# Initialize authentication (opens browser for Google login)
kof-notebooklm-init
```

---

## Quick Start

### As MCP Server

Add to your MCP configuration (`mcp_config.json`):

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

### Available Tools

| Tool | Description |
|------|-------------|
| `health_check` | Verify connection and auth status |
| `list_notebooks` | List all notebooks |
| `create_notebook` | Create a new notebook (with optional title) |
| `get_notebook` | Get notebook details |
| `list_sources` | List sources in a notebook |
| `add_source` | Add URL or text source |
| `ask` | Query notebook AI with citations |

### Example Usage (via MCP client)

```python
# Create a research notebook
result = await mcp.call_tool("create_notebook", {"title": "Market Research 2026"})
notebook_id = result["notebook_id"]

# Add a source
await mcp.call_tool("add_source", {
    "notebook_id": notebook_id,
    "source_type": "url",
    "url": "https://example.com/report.pdf"
})

# Ask a question
answer = await mcp.call_tool("ask", {
    "notebook_id": notebook_id,
    "question": "What are the key market trends?"
})
print(answer["answer"])
print(answer["citations"])
```

---

## Configuration

Environment variables (optional):

| Variable | Description | Default |
|----------|-------------|---------|
| `KOF_NOTEBOOKLM_HEADLESS` | Run browser in headless mode | `true` |
| `KOF_NOTEBOOKLM_PROFILE_DIR` | Browser profile directory | `~/.kof-notebooklm/profile` |

---

## Development

```bash
git clone https://github.com/keeponfirst/kof-notebooklm-mcp.git
cd kof-notebooklm-mcp

pip install -e ".[dev]"
pytest
```

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Related Projects

- [KOF-LocalBrain](https://github.com/keeponfirst/keeponfirst-local-brain) — Local-first brain capture system
- [Model Context Protocol](https://modelcontextprotocol.io/) — The standard for AI tool integration
