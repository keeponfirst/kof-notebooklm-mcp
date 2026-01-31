# KOF NotebookLM MCP Server - Implementation Plan

> **Status**: ✅ MVP Complete
> **Last Updated**: 2026-01-28
> **Author**: Claude (Opus 4.5)

---

## 1. Scope

### MVP (Minimum Viable Product)

The MVP focuses on **read-heavy research workflows** - using NotebookLM as a knowledge workspace that can be queried programmatically.

| Feature | MVP | V1 |
|---------|-----|-----|
| `health_check` | ✅ | ✅ |
| `list_notebooks` | ✅ | ✅ |
| `get_notebook` | ✅ | ✅ |
| `list_sources` | ✅ | ✅ |
| `add_source` (URL) | ✅ | ✅ |
| `add_source` (text/markdown) | ✅ | ✅ |
| `ask` (query notebook) | ✅ | ✅ |
| `create_notebook` | ❌ | ✅ |
| `delete_source` | ❌ | ✅ |
| `delete_notebook` | ❌ | ✅ |
| `get_audio_overview` | ❌ | ✅ |
| `export_notes` | ❌ | ✅ |

### Out of Scope (Deliberate)

- Audio overview generation (compute-intensive, long wait times)
- Collaborative features (sharing, permissions)
- NotebookLM Plus subscription features
- Mobile app integration
- Real-time sync/webhooks

---

## 2. Architecture Overview

### Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Client                                │
│                  (Claude Desktop / CLI)                          │
└─────────────────────────┬───────────────────────────────────────┘
                          │ stdio (JSON-RPC)
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                  kof-notebooklm-mcp                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    MCP Server Layer                       │   │
│  │         (mcp-python-sdk / FastMCP)                        │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                         │                                        │
│  ┌──────────────────────▼───────────────────────────────────┐   │
│  │                   Tool Handlers                           │   │
│  │    list_notebooks | get_notebook | add_source | ask       │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                         │                                        │
│  ┌──────────────────────▼───────────────────────────────────┐   │
│  │               NotebookLM Client Layer                     │   │
│  │                                                           │   │
│  │   ┌─────────────────┐    ┌─────────────────────────┐     │   │
│  │   │ Session Manager │    │  Browser Automation     │     │   │
│  │   │ (cookies, auth) │    │  (Playwright async)     │     │   │
│  │   └────────┬────────┘    └────────────┬────────────┘     │   │
│  │            │                          │                   │   │
│  │            └──────────┬───────────────┘                   │   │
│  │                       │                                   │   │
│  │   ┌───────────────────▼────────────────────────────┐     │   │
│  │   │           Page Object Models                    │     │   │
│  │   │   NotebooksPage | NotebookDetailPage | etc.     │     │   │
│  │   └────────────────────────────────────────────────┘     │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼ HTTPS
┌─────────────────────────────────────────────────────────────────┐
│                   notebooklm.google.com                          │
│                   (Google Authentication)                        │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow (Example: `ask` tool)

```
1. MCP Client sends: {"method": "tools/call", "params": {"name": "ask", ...}}
2. MCP Server routes to ask_handler()
3. ask_handler() calls notebooklm_client.ask(notebook_id, question)
4. Client navigates browser to notebook page
5. Client types question in chat input
6. Client waits for response (with timeout)
7. Client extracts answer text + source citations
8. Response flows back up: JSON → MCP → Client
```

---

## 3. Tool List (MVP)

| Tool | Description | Priority |
|------|-------------|----------|
| `health_check` | Verify session validity and service availability | P0 |
| `list_notebooks` | Return all notebooks in user's account | P0 |
| `get_notebook` | Get notebook details (name, source count, created date) | P0 |
| `list_sources` | List all sources in a notebook | P0 |
| `add_source` | Add URL or text content as a source | P1 |
| `ask` | Query the notebook and get AI-generated answer | P1 |

See `TOOLS.md` for detailed specifications.

---

## 4. Auth/Session Strategy

### Approach: Persistent Browser Profile + Manual Initial Login

**Why not OAuth/API tokens?**
NotebookLM has no public API. We must use browser automation with Google account authentication.

**Strategy:**

1. **First Run (Manual)**:
   - User runs `kof-notebooklm-init` command
   - Opens visible browser window
   - User manually logs into Google account
   - Browser profile saved to `~/.kof-notebooklm/profile/`
   - Session cookies persist across restarts

2. **Subsequent Runs (Automatic)**:
   - MCP server loads existing browser profile
   - Runs headless by default
   - Session typically valid for 2-4 weeks
   - Health check detects expired session

3. **Session Refresh**:
   - When health_check fails with auth error
   - User re-runs `kof-notebooklm-init`
   - Or: Set `NOTEBOOKLM_HEADLESS=false` to manually re-auth

### Environment Variables

```bash
# Required: none (uses browser profile)

# Optional:
NOTEBOOKLM_PROFILE_PATH=~/.kof-notebooklm/profile  # Browser profile location
NOTEBOOKLM_HEADLESS=true                            # Run browser headless
NOTEBOOKLM_TIMEOUT=30000                            # Default timeout (ms)
NOTEBOOKLM_SLOW_MO=0                                # Slow down operations (ms, for debugging)
```

### Security Considerations

- Browser profile contains session cookies (sensitive!)
- Profile directory must have restricted permissions (700)
- Never commit profile to git
- `.gitignore` includes `~/.kof-notebooklm/` pattern

---

## 5. Error Handling + Stability Strategy

### Error Categories

| Category | HTTP-like Code | Retry? | Example |
|----------|---------------|--------|---------|
| Auth Error | 401 | No | Session expired, login required |
| Not Found | 404 | No | Notebook/source doesn't exist |
| Rate Limit | 429 | Yes (backoff) | Too many requests |
| Timeout | 408 | Yes (1x) | Page load timeout |
| Element Not Found | 500 | Yes (1x) | UI changed, selector broken |
| Network Error | 503 | Yes (backoff) | Connection failed |

### Retry Strategy

```python
RETRY_CONFIG = {
    "max_retries": 3,
    "base_delay": 1.0,        # seconds
    "max_delay": 30.0,        # seconds
    "exponential_base": 2,    # delay = base_delay * (2 ^ attempt)
    "jitter": 0.1,            # ±10% randomization
}
```

### Rate Limiting

- Self-imposed limit: **10 requests per minute** (conservative)
- Token bucket algorithm
- Configurable via `NOTEBOOKLM_RATE_LIMIT`

### Health Check

The `health_check` tool verifies:

1. Browser can launch
2. Can navigate to notebooklm.google.com
3. User is logged in (not redirected to login page)
4. Notebooks list is accessible

Returns:
```json
{
  "status": "healthy" | "degraded" | "unhealthy",
  "authenticated": true | false,
  "latency_ms": 1234,
  "error": null | "error message"
}
```

### Circuit Breaker

After 5 consecutive failures:
- Circuit opens (fails fast for 60 seconds)
- Background probe attempts recovery
- Circuit closes on successful probe

---

## 6. Security Guardrails

### No Secrets in Repo

- ✅ `.gitignore` includes browser profile path
- ✅ No hardcoded credentials
- ✅ Environment variables for all config
- ✅ `.env.example` documents required vars (no values)

### Input Validation

```python
# All inputs validated before use
MAX_QUESTION_LENGTH = 10000      # characters
MAX_TEXT_SOURCE_LENGTH = 500000  # ~500KB
ALLOWED_URL_SCHEMES = ["https"]  # no http, file, javascript
MAX_NOTEBOOK_NAME_LENGTH = 200
```

### Least Privilege

- Browser runs in isolated profile
- No access to user's default browser data
- No filesystem access beyond profile directory
- Headless mode by default (no screen capture risk)

### Injection Prevention

- User input never passed to shell commands
- URL validation before navigation
- Text content sanitized for XSS patterns (defensive)

---

## 7. Testing Plan

### Manual Checklist (MVP)

- [ ] Fresh install: `pip install -e packages/kof-notebooklm-mcp`
- [ ] Init flow: `kof-notebooklm-init` opens browser, saves profile
- [ ] Health check passes after login
- [ ] `list_notebooks` returns expected notebooks
- [ ] `get_notebook` returns correct metadata
- [ ] `list_sources` shows sources in notebook
- [ ] `add_source` with URL creates source
- [ ] `add_source` with text creates source
- [ ] `ask` returns sensible answer
- [ ] Session persistence: restart server, tools still work
- [ ] Error handling: invalid notebook ID returns proper error
- [ ] Headless mode works (`NOTEBOOKLM_HEADLESS=true`)

### Automated Tests

```
tests/
├── unit/
│   ├── test_input_validation.py    # Input sanitization
│   ├── test_retry_logic.py         # Retry/backoff
│   └── test_rate_limiter.py        # Token bucket
├── integration/
│   ├── test_browser_launch.py      # Browser can start
│   └── test_page_objects.py        # Selectors work (mocked HTML)
└── e2e/
    └── test_full_flow.py           # Real NotebookLM (manual trigger)
```

**CI Strategy:**
- Unit tests: Run on every commit
- Integration tests: Run on every commit (mocked)
- E2E tests: Manual trigger only (requires auth)

---

## 8. Milestones

| Milestone | Description | Estimate | Status |
|-----------|-------------|----------|--------|
| **M0: Skeleton** | Project structure, dependencies, MCP server stub | 0.5 day | ✅ Complete |
| **M1: Auth Flow** | Browser profile management, init command, health_check | 1 day | ✅ Complete |
| **M2: Read Operations** | list_notebooks, get_notebook, list_sources | 1 day | ✅ Complete |
| **M3: Write Operations** | add_source (URL + text) | 1 day | ✅ Complete |
| **M4: Query** | ask tool with citation extraction | 1 day | ✅ Complete |
| **M5: Polish** | Error handling, retry logic, rate limiting | 0.5 day | ✅ Complete |
| **M6: Docs & Testing** | README, manual test, basic unit tests | 0.5 day | ✅ Complete |

**Total MVP Estimate: 5.5 half-days (~3 days)** - ✅ **MVP Complete**

---

## 9. KOF Workflow Integration

### Where NotebookLM Fits in PLAN → ASSETS → CODE

```
┌─────────────────────────────────────────────────────────────────┐
│                         KOF Workflow                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  📋 PLAN Phase                                                   │
│  └── Research & Context Gathering                                │
│      └── 🔗 NotebookLM: "Research Scratchpad"                   │
│          • Aggregate sources (docs, articles, repos)             │
│          • Ask questions to synthesize understanding             │
│          • Extract key decisions for /kof-decision               │
│                                                                  │
│  📦 ASSETS Phase                                                 │
│  └── Knowledge Base & References                                 │
│      └── 🔗 NotebookLM: "Citations Provider"                    │
│          • Query notebook for specific facts                     │
│          • Get source citations for documentation                │
│          • Validate assumptions against sources                  │
│                                                                  │
│  💻 CODE Phase                                                   │
│  └── Implementation & Review                                     │
│      └── 🔗 NotebookLM: "Technical Reference"                   │
│          • Ask "how does X library handle Y?"                    │
│          • Cross-reference implementation patterns               │
│          • Generate code comments with citations                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Use Case Examples

#### 1. Research Scratchpad (PLAN Phase)

```markdown
# Workflow: Deep Research for Technical Decision

1. Create notebook for research topic
2. Add sources:
   - Official documentation URLs
   - Relevant blog posts
   - GitHub repo READMEs
3. Ask synthesizing questions:
   - "What are the tradeoffs between X and Y?"
   - "Summarize the authentication approaches mentioned"
4. Capture decision in KOF:
   - /kof-decision with NotebookLM citations
```

**Example Prompt Pattern:**
```
Use kof-notebooklm-mcp to research [TOPIC]:

1. health_check - verify connection
2. list_notebooks - find existing research notebook or note we need new one
3. add_source - add these URLs: [URL1], [URL2]
4. ask - "What are the main approaches to [SPECIFIC_QUESTION]?"
5. Return findings formatted for /kof-decision
```

#### 2. Citations Provider (ASSETS Phase)

```markdown
# Workflow: Generate Documentation with Citations

1. Query existing research notebook
2. Ask specific factual questions
3. Extract source references from response
4. Format as markdown with citation links
```

**Example Prompt Pattern:**
```
Query notebook "[NOTEBOOK_NAME]" for documentation:

1. get_notebook - confirm notebook exists
2. list_sources - show available reference material
3. ask - "[SPECIFIC_QUESTION] - cite your sources"
4. Format response with [source_title](source_url) links
```

#### 3. Technical Reference (CODE Phase)

```markdown
# Workflow: Implementation Guidance

1. Add relevant technical docs to notebook
2. Ask implementation-specific questions
3. Get code patterns with explanations
```

**Example Prompt Pattern:**
```
Before implementing [FEATURE]:

1. add_source - add official docs: [DOCS_URL]
2. ask - "Show example code for [SPECIFIC_PATTERN]"
3. ask - "What edge cases should I handle for [SCENARIO]?"
4. Incorporate guidance into implementation
```

### Recommended Notebook Organization

| Notebook | Purpose | Lifecycle |
|----------|---------|-----------|
| `project-[name]-research` | Project-specific research | Per project |
| `tech-[topic]` | Reusable technical reference | Long-lived |
| `decision-[date]-[topic]` | One-off decision research | Archive after decision |

### Integration with Existing KOF Commands

```markdown
## Enhanced /kof-decision Workflow

1. Before drafting decision:
   - Query NotebookLM for relevant research
   - Include citations in decision rationale

2. After decision captured:
   - Add decision document as source to notebook
   - Build organizational knowledge base

## Enhanced /kof-idea Workflow

1. New idea captured:
   - Search existing notebooks for related research
   - Link to relevant prior work

2. Idea exploration:
   - Create temporary notebook
   - Add idea sources for deeper research
```

---

## 10. Known Limitations

### Technical Limitations

1. **No Official API**: Relies on browser automation; may break with UI changes
2. **Session Duration**: Google sessions expire; requires periodic re-auth
3. **Rate Limits**: Self-imposed conservative limits to avoid detection
4. **Latency**: Browser operations are slower than API calls (~2-10s per operation)
5. **Headless Restrictions**: Some Google services detect headless browsers

### Functional Limitations

1. **No Real-time Updates**: Must poll for changes
2. **No Webhooks**: Can't receive notifications
3. **Single User**: One Google account per server instance
4. **No Concurrent Operations**: Operations are serialized (browser constraint)

### Operational Limitations

1. **Local Only (MVP)**: No cloud deployment guidance
2. **Manual Auth**: Initial setup requires human interaction
3. **Profile Portability**: Browser profile tied to machine

---

## 11. Dependencies

### Python Packages

```
mcp>=1.0.0                  # MCP SDK (or fastmcp)
playwright>=1.40.0          # Browser automation
pydantic>=2.0.0             # Input validation
python-dotenv>=1.0.0        # Environment loading
```

### System Requirements

- Python 3.10+
- Chromium browser (installed by Playwright)
- ~500MB disk for browser + profile

---

## Appendix: File Structure

```
packages/kof-notebooklm-mcp/
├── pyproject.toml
├── README.md
├── src/
│   └── kof_notebooklm_mcp/
│       ├── __init__.py
│       ├── server.py           # MCP server entrypoint
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── health_check.py
│       │   ├── list_notebooks.py
│       │   ├── get_notebook.py
│       │   ├── list_sources.py
│       │   ├── add_source.py
│       │   └── ask.py
│       ├── client/
│       │   ├── __init__.py
│       │   ├── browser.py      # Playwright wrapper
│       │   ├── session.py      # Profile management
│       │   └── pages/
│       │       ├── __init__.py
│       │       ├── base.py
│       │       ├── notebooks.py
│       │       └── notebook_detail.py
│       └── utils/
│           ├── __init__.py
│           ├── validation.py
│           ├── retry.py
│           └── rate_limit.py
└── tests/
    ├── __init__.py
    ├── unit/
    ├── integration/
    └── e2e/
```
