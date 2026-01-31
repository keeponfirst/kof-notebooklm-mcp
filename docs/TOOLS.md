# KOF NotebookLM MCP Server - Tool Specifications

> **Version**: MVP (1.0.0)
> **Last Updated**: 2026-01-28

---

## Overview

This document specifies the MCP tools exposed by `kof-notebooklm-mcp`. Each tool follows the MCP tool schema with:
- **name**: Tool identifier
- **description**: What the tool does
- **inputSchema**: JSON Schema for inputs
- **outputSchema**: Expected response structure
- **errors**: Possible error conditions
- **examples**: Sample calls and responses

---

## Tool: `health_check`

### Description
Verify that the MCP server can connect to NotebookLM and the user session is valid.

### Input Schema
```json
{
  "type": "object",
  "properties": {},
  "required": []
}
```

### Output Schema
```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string",
      "enum": ["healthy", "degraded", "unhealthy"],
      "description": "Overall health status"
    },
    "authenticated": {
      "type": "boolean",
      "description": "Whether the user session is valid"
    },
    "latency_ms": {
      "type": "integer",
      "description": "Time to complete health check in milliseconds"
    },
    "browser_ok": {
      "type": "boolean",
      "description": "Whether browser launched successfully"
    },
    "error": {
      "type": ["string", "null"],
      "description": "Error message if status is not healthy"
    }
  },
  "required": ["status", "authenticated", "latency_ms", "browser_ok"]
}
```

### Error Cases
| Error Code | Condition | Recovery |
|------------|-----------|----------|
| `BROWSER_LAUNCH_FAILED` | Playwright cannot start browser | Check Playwright installation |
| `SESSION_EXPIRED` | Google session invalid | Run `kof-notebooklm-init` |
| `NETWORK_ERROR` | Cannot reach notebooklm.google.com | Check internet connection |
| `TIMEOUT` | Health check took too long | Retry or increase timeout |

### Example

**Request:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "health_check",
    "arguments": {}
  }
}
```

**Response (Success):**
```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"status\": \"healthy\", \"authenticated\": true, \"latency_ms\": 1523, \"browser_ok\": true, \"error\": null}"
    }
  ]
}
```

**Response (Auth Error):**
```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"status\": \"unhealthy\", \"authenticated\": false, \"latency_ms\": 2341, \"browser_ok\": true, \"error\": \"Session expired. Please run kof-notebooklm-init to re-authenticate.\"}"
    }
  ]
}
```

---

## Tool: `list_notebooks`

### Description
List all notebooks in the user's NotebookLM account.

### Input Schema
```json
{
  "type": "object",
  "properties": {
    "limit": {
      "type": "integer",
      "description": "Maximum number of notebooks to return",
      "default": 50,
      "minimum": 1,
      "maximum": 100
    }
  },
  "required": []
}
```

### Output Schema
```json
{
  "type": "object",
  "properties": {
    "notebooks": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string",
            "description": "Unique notebook identifier"
          },
          "name": {
            "type": "string",
            "description": "Notebook display name"
          },
          "source_count": {
            "type": "integer",
            "description": "Number of sources in the notebook"
          },
          "updated_at": {
            "type": ["string", "null"],
            "description": "Last updated timestamp (ISO 8601) if available"
          }
        },
        "required": ["id", "name"]
      }
    },
    "total": {
      "type": "integer",
      "description": "Total number of notebooks (may exceed limit)"
    }
  },
  "required": ["notebooks", "total"]
}
```

### Error Cases
| Error Code | Condition | Recovery |
|------------|-----------|----------|
| `AUTH_REQUIRED` | Not authenticated | Run health_check first |
| `TIMEOUT` | Page load timeout | Retry |
| `PARSE_ERROR` | Could not extract notebooks from page | Report bug (UI may have changed) |

### Example

**Request:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "list_notebooks",
    "arguments": {
      "limit": 10
    }
  }
}
```

**Response:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"notebooks\": [{\"id\": \"abc123\", \"name\": \"Research: MCP Servers\", \"source_count\": 5, \"updated_at\": \"2025-01-27T10:30:00Z\"}, {\"id\": \"def456\", \"name\": \"Project Alpha Notes\", \"source_count\": 12, \"updated_at\": \"2025-01-26T15:45:00Z\"}], \"total\": 2}"
    }
  ]
}
```

---

## Tool: `get_notebook`

### Description
Get detailed information about a specific notebook.

### Input Schema
```json
{
  "type": "object",
  "properties": {
    "notebook_id": {
      "type": "string",
      "description": "The notebook ID (from list_notebooks)"
    }
  },
  "required": ["notebook_id"]
}
```

### Output Schema
```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "description": "Notebook identifier"
    },
    "name": {
      "type": "string",
      "description": "Notebook display name"
    },
    "source_count": {
      "type": "integer",
      "description": "Number of sources"
    },
    "created_at": {
      "type": ["string", "null"],
      "description": "Creation timestamp if available"
    },
    "updated_at": {
      "type": ["string", "null"],
      "description": "Last updated timestamp if available"
    },
    "description": {
      "type": ["string", "null"],
      "description": "Notebook description if set"
    }
  },
  "required": ["id", "name", "source_count"]
}
```

### Error Cases
| Error Code | Condition | Recovery |
|------------|-----------|----------|
| `NOT_FOUND` | Notebook ID doesn't exist | Verify ID with list_notebooks |
| `AUTH_REQUIRED` | Not authenticated | Run health_check |
| `TIMEOUT` | Page load timeout | Retry |

### Example

**Request:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "get_notebook",
    "arguments": {
      "notebook_id": "abc123"
    }
  }
}
```

**Response:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"id\": \"abc123\", \"name\": \"Research: MCP Servers\", \"source_count\": 5, \"created_at\": \"2025-01-20T09:00:00Z\", \"updated_at\": \"2025-01-27T10:30:00Z\", \"description\": null}"
    }
  ]
}
```

---

## Tool: `list_sources`

### Description
List all sources in a notebook.

### Input Schema
```json
{
  "type": "object",
  "properties": {
    "notebook_id": {
      "type": "string",
      "description": "The notebook ID"
    }
  },
  "required": ["notebook_id"]
}
```

### Output Schema
```json
{
  "type": "object",
  "properties": {
    "sources": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string",
            "description": "Source identifier"
          },
          "title": {
            "type": "string",
            "description": "Source title"
          },
          "type": {
            "type": "string",
            "enum": ["url", "text", "pdf", "gdoc", "gslides", "youtube", "audio", "unknown"],
            "description": "Source type"
          },
          "url": {
            "type": ["string", "null"],
            "description": "Source URL if applicable"
          },
          "added_at": {
            "type": ["string", "null"],
            "description": "When source was added"
          }
        },
        "required": ["id", "title", "type"]
      }
    },
    "total": {
      "type": "integer",
      "description": "Total number of sources"
    }
  },
  "required": ["sources", "total"]
}
```

### Error Cases
| Error Code | Condition | Recovery |
|------------|-----------|----------|
| `NOT_FOUND` | Notebook doesn't exist | Verify notebook_id |
| `AUTH_REQUIRED` | Not authenticated | Run health_check |
| `TIMEOUT` | Page load timeout | Retry |

### Example

**Request:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "list_sources",
    "arguments": {
      "notebook_id": "abc123"
    }
  }
}
```

**Response:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"sources\": [{\"id\": \"src1\", \"title\": \"MCP Specification\", \"type\": \"url\", \"url\": \"https://modelcontextprotocol.io/docs\", \"added_at\": \"2025-01-25T14:00:00Z\"}, {\"id\": \"src2\", \"title\": \"My Notes on Architecture\", \"type\": \"text\", \"url\": null, \"added_at\": \"2025-01-26T09:30:00Z\"}], \"total\": 2}"
    }
  ]
}
```

---

## Tool: `add_source`

### Description
Add a new source to a notebook. Supports URLs (web pages) and raw text/markdown content.

### Input Schema
```json
{
  "type": "object",
  "properties": {
    "notebook_id": {
      "type": "string",
      "description": "The notebook ID to add source to"
    },
    "source_type": {
      "type": "string",
      "enum": ["url", "text"],
      "description": "Type of source to add"
    },
    "url": {
      "type": "string",
      "format": "uri",
      "description": "URL to add (required if source_type is 'url')"
    },
    "text": {
      "type": "string",
      "description": "Text/markdown content (required if source_type is 'text')",
      "maxLength": 500000
    },
    "title": {
      "type": "string",
      "description": "Title for text sources (optional, auto-generated if not provided)",
      "maxLength": 200
    }
  },
  "required": ["notebook_id", "source_type"],
  "oneOf": [
    {
      "properties": {
        "source_type": { "const": "url" }
      },
      "required": ["url"]
    },
    {
      "properties": {
        "source_type": { "const": "text" }
      },
      "required": ["text"]
    }
  ]
}
```

### Output Schema
```json
{
  "type": "object",
  "properties": {
    "success": {
      "type": "boolean",
      "description": "Whether source was added successfully"
    },
    "source_id": {
      "type": ["string", "null"],
      "description": "ID of the created source if available"
    },
    "title": {
      "type": "string",
      "description": "Title of the added source"
    },
    "processing_status": {
      "type": "string",
      "enum": ["complete", "processing", "failed"],
      "description": "NotebookLM processing status"
    },
    "message": {
      "type": ["string", "null"],
      "description": "Additional status message"
    }
  },
  "required": ["success", "title", "processing_status"]
}
```

### Error Cases
| Error Code | Condition | Recovery |
|------------|-----------|----------|
| `NOT_FOUND` | Notebook doesn't exist | Verify notebook_id |
| `INVALID_URL` | URL format invalid or unreachable | Check URL |
| `CONTENT_TOO_LARGE` | Text exceeds 500KB limit | Split into multiple sources |
| `UNSUPPORTED_URL` | URL type not supported by NotebookLM | Use different source |
| `RATE_LIMITED` | Too many add operations | Wait and retry |
| `AUTH_REQUIRED` | Not authenticated | Run health_check |
| `PROCESSING_FAILED` | NotebookLM couldn't process source | Check source content |

### Example: Add URL

**Request:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "add_source",
    "arguments": {
      "notebook_id": "abc123",
      "source_type": "url",
      "url": "https://docs.anthropic.com/en/docs/claude-code"
    }
  }
}
```

**Response:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"success\": true, \"source_id\": \"src_new1\", \"title\": \"Claude Code Documentation\", \"processing_status\": \"processing\", \"message\": \"Source added. NotebookLM is processing the content.\"}"
    }
  ]
}
```

### Example: Add Text

**Request:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "add_source",
    "arguments": {
      "notebook_id": "abc123",
      "source_type": "text",
      "title": "Architecture Decision Record",
      "text": "# ADR-001: Use Browser Automation\n\n## Context\nNotebookLM has no public API...\n\n## Decision\nWe will use Playwright for browser automation..."
    }
  }
}
```

**Response:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"success\": true, \"source_id\": \"src_new2\", \"title\": \"Architecture Decision Record\", \"processing_status\": \"complete\", \"message\": null}"
    }
  ]
}
```

---

## Tool: `ask`

### Description
Query a notebook and get an AI-generated answer with source citations.

### Input Schema
```json
{
  "type": "object",
  "properties": {
    "notebook_id": {
      "type": "string",
      "description": "The notebook ID to query"
    },
    "question": {
      "type": "string",
      "description": "The question to ask",
      "minLength": 1,
      "maxLength": 10000
    },
    "include_citations": {
      "type": "boolean",
      "description": "Whether to extract source citations from the response",
      "default": true
    }
  },
  "required": ["notebook_id", "question"]
}
```

### Output Schema
```json
{
  "type": "object",
  "properties": {
    "answer": {
      "type": "string",
      "description": "The AI-generated answer"
    },
    "citations": {
      "type": "array",
      "description": "Source citations referenced in the answer",
      "items": {
        "type": "object",
        "properties": {
          "source_id": {
            "type": "string",
            "description": "Source identifier"
          },
          "source_title": {
            "type": "string",
            "description": "Source title"
          },
          "excerpt": {
            "type": ["string", "null"],
            "description": "Relevant excerpt from source if available"
          }
        },
        "required": ["source_id", "source_title"]
      }
    },
    "confidence": {
      "type": ["string", "null"],
      "enum": ["high", "medium", "low", null],
      "description": "Confidence level if determinable"
    },
    "follow_up_questions": {
      "type": "array",
      "description": "Suggested follow-up questions if available",
      "items": {
        "type": "string"
      }
    }
  },
  "required": ["answer"]
}
```

### Error Cases
| Error Code | Condition | Recovery |
|------------|-----------|----------|
| `NOT_FOUND` | Notebook doesn't exist | Verify notebook_id |
| `NO_SOURCES` | Notebook has no sources | Add sources first |
| `QUESTION_TOO_LONG` | Question exceeds 10K chars | Shorten question |
| `TIMEOUT` | Response took too long | Retry with simpler question |
| `AUTH_REQUIRED` | Not authenticated | Run health_check |
| `RATE_LIMITED` | Too many queries | Wait and retry |

### Example

**Request:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "ask",
    "arguments": {
      "notebook_id": "abc123",
      "question": "What are the main approaches to implementing MCP servers?",
      "include_citations": true
    }
  }
}
```

**Response:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"answer\": \"Based on the sources, there are three main approaches to implementing MCP servers:\\n\\n1. **stdio transport**: The server communicates via standard input/output streams. This is the most common approach for local tools.\\n\\n2. **HTTP/SSE transport**: The server exposes HTTP endpoints with Server-Sent Events for streaming responses. Better for web deployments.\\n\\n3. **Custom transport**: Implementing your own transport layer for specialized use cases.\\n\\nThe MCP specification recommends stdio for CLI tools and HTTP/SSE for web services.\", \"citations\": [{\"source_id\": \"src1\", \"source_title\": \"MCP Specification\", \"excerpt\": \"MCP supports two standard transports: stdio for local processes and HTTP with SSE for remote services.\"}, {\"source_id\": \"src2\", \"source_title\": \"My Notes on Architecture\", \"excerpt\": \"For our use case, stdio is preferred because...\"}], \"confidence\": \"high\", \"follow_up_questions\": [\"How do I handle authentication in MCP servers?\", \"What are the performance differences between transports?\"]}"
    }
  ]
}
```

---

## Error Response Format

All tools return errors in a consistent format:

```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"error\": {\"code\": \"ERROR_CODE\", \"message\": \"Human-readable error message\", \"details\": {\"key\": \"value\"}, \"recoverable\": true}}"
    }
  ],
  "isError": true
}
```

### Error Schema

```json
{
  "type": "object",
  "properties": {
    "error": {
      "type": "object",
      "properties": {
        "code": {
          "type": "string",
          "description": "Machine-readable error code"
        },
        "message": {
          "type": "string",
          "description": "Human-readable error message"
        },
        "details": {
          "type": "object",
          "description": "Additional error context"
        },
        "recoverable": {
          "type": "boolean",
          "description": "Whether retrying might succeed"
        }
      },
      "required": ["code", "message", "recoverable"]
    }
  },
  "required": ["error"]
}
```

---

## Rate Limits

| Operation | Limit | Window |
|-----------|-------|--------|
| Any tool call | 10 | per minute |
| `add_source` | 5 | per minute |
| `ask` | 5 | per minute |

When rate limited, tools return:
```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded. Please wait 45 seconds.",
    "details": {
      "retry_after_seconds": 45,
      "limit": 10,
      "window": "minute"
    },
    "recoverable": true
  }
}
```

---

## Timeouts

| Operation | Default Timeout | Max Timeout |
|-----------|-----------------|-------------|
| `health_check` | 30s | 60s |
| `list_notebooks` | 30s | 60s |
| `get_notebook` | 30s | 60s |
| `list_sources` | 30s | 60s |
| `add_source` | 60s | 120s |
| `ask` | 90s | 180s |

Timeouts are configurable via `NOTEBOOKLM_TIMEOUT` environment variable.
