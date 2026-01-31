# KOF NotebookLM MCP Server - Architectural Decisions

> **Status**: Active
> **Last Updated**: 2026-01-28

This document records key architectural decisions, their rationale, alternatives considered, and what we deliberately chose not to do.

---

## Decision Log

### ADR-001: Use Browser Automation (Playwright) as Primary Approach

**Date**: 2025-01-28
**Status**: Accepted
**Deciders**: Implementation team

#### Context

Google NotebookLM does not have a public API. To integrate programmatically, we must choose between:

1. **Browser Automation** (Playwright/Puppeteer)
2. **Undocumented RPC/API** (reverse-engineering the web app)
3. **Existing Libraries** (third-party wrappers)
4. **Wait for Official API** (postpone the project)

#### Decision

We will use **Playwright browser automation** as the primary implementation approach.

#### Rationale

| Criterion | Browser Automation | Undocumented RPC | Existing Libraries | Wait for API |
|-----------|-------------------|------------------|-------------------|--------------|
| **Reliability** | Medium | Low | Unknown | N/A |
| **Maintenance** | Medium effort | High effort | Depends on lib | None |
| **Legal risk** | Low (normal user) | Medium (ToS gray area) | Varies | None |
| **Time to implement** | 3-5 days | 5-10 days | 1-2 days if exists | Unknown |
| **Observability** | High (can debug visually) | Low | Varies | N/A |
| **Breakage detection** | Easy (visible errors) | Hard (silent failures) | Varies | N/A |

**Why Playwright specifically:**
- Async-first design (better for MCP server)
- Built-in waiting/retry mechanisms
- Cross-browser support (can switch if needed)
- Active maintenance by Microsoft
- Good Python support

**Why not Selenium:**
- Older architecture, synchronous by default
- More complex setup
- Playwright has better modern web handling

**Why not undocumented RPC:**
- High reverse-engineering effort
- Likely to break without warning
- May violate Google ToS
- No documentation = harder debugging

**Why not existing libraries:**
- Searched PyPI, npm, GitHub: no mature NotebookLM libraries exist
- `notebooklm-api` packages are abandoned/incomplete
- Would still need to maintain fork if found

#### Consequences

**Positive:**
- Can observe and debug visually during development
- User authentication via normal Google login flow
- Resistant to minor UI changes (can adjust selectors)

**Negative:**
- Slower than API calls (~2-10s per operation)
- Requires browser runtime (~500MB)
- May break with major UI redesigns
- Cannot run in constrained environments (some serverless)

#### Alternatives Not Chosen

- **Hybrid approach** (RPC + browser fallback): Too complex for MVP
- **Chrome extension**: Requires user to install extension, UX friction

---

### ADR-002: Persistent Browser Profile for Authentication

**Date**: 2025-01-28
**Status**: Accepted

#### Context

Google authentication is complex (OAuth, 2FA, security checks). We need a strategy that:
- Works with any Google account
- Doesn't require storing passwords
- Survives server restarts
- Handles 2FA gracefully

#### Decision

Use **persistent Playwright browser profile** with manual initial authentication.

#### Rationale

| Approach | Complexity | Security | User Experience |
|----------|------------|----------|-----------------|
| Persistent profile | Low | Good (no creds stored) | One-time manual login |
| OAuth flow | High | Good | Requires Google Cloud project |
| Store credentials | Low | Bad | Never acceptable |
| Fresh login each time | Medium | OK | Poor (2FA every time) |

**Persistent profile approach:**
1. First run: open visible browser, user logs in manually
2. Cookies/session saved to disk (encrypted by Chromium)
3. Subsequent runs: load profile, session already valid
4. Refresh: when session expires, user re-runs init

#### Consequences

**Positive:**
- No credential handling
- Works with any auth method (password, 2FA, passkey)
- Session typically lasts 2-4 weeks
- Profile encrypted by Chromium

**Negative:**
- Initial setup requires human interaction
- Profile not portable between machines
- Must protect profile directory

---

### ADR-003: Python over Node.js for Implementation

**Date**: 2025-01-28
**Status**: Accepted

#### Context

MCP servers can be implemented in any language. The repository uses Python exclusively.

#### Decision

Implement in **Python** using `mcp` Python SDK (or `fastmcp`).

#### Rationale

- **Consistency**: All existing code is Python
- **Tooling**: Repository already has Python setup (venv, requirements.txt)
- **Playwright**: Excellent Python async support
- **MCP SDK**: Python SDK is well-maintained

**Why not Node.js:**
- Would introduce new language to monorepo
- Additional tooling (npm, node_modules)
- No existing Node.js patterns to follow

---

### ADR-004: Conservative Rate Limiting

**Date**: 2025-01-28
**Status**: Accepted

#### Context

NotebookLM is a free Google service with no documented rate limits. Aggressive usage could result in:
- Account suspension
- IP blocking
- Service degradation

#### Decision

Implement **self-imposed conservative rate limits**:
- 10 requests per minute overall
- 5 requests per minute for write operations

#### Rationale

- Better to be slow than blocked
- Can increase limits after observing actual behavior
- Users can override via environment variable if needed

#### Consequences

- Slower batch operations
- Safety margin against detection
- Configurable for power users

---

### ADR-005: Synchronous Operation Serialization

**Date**: 2025-01-28
**Status**: Accepted

#### Context

Browser automation with a single browser instance cannot safely handle concurrent operations.

#### Decision

**Serialize all NotebookLM operations** through a single browser instance with a queue.

#### Rationale

- Single browser = single page state
- Concurrent navigation would corrupt state
- Queue ensures predictable execution
- Simpler error handling

#### Consequences

- No parallel operations
- Predictable latency per operation
- Clear debugging (one operation at a time)

---

## Scope Boundaries

### What We Are NOT Doing (MVP)

| Feature | Reason | Reconsider When |
|---------|--------|-----------------|
| **create_notebook** | UI flow is complex, not essential for research workflows | V1 if frequently requested |
| **delete_notebook** | Destructive, requires confirmation UI | V1 with safety checks |
| **delete_source** | Destructive, lower priority | V1 |
| **Audio overview** | Long generation time (minutes), complex status tracking | V2 or never |
| **Sharing/collaboration** | Complex permissions, multi-user not in scope | Out of scope |
| **Google Drive integration** | Additional auth complexity | V2 if needed |
| **YouTube transcript extraction** | NotebookLM already handles this via URL | Not needed |
| **PDF upload** | Requires file handling, storage decisions | V1 |
| **Real-time sync** | No webhook support, would require polling | Out of scope |
| **Multi-account support** | Single profile design decision | V2 if needed |
| **Cloud deployment** | MVP is local-only | V2 with auth refactor |

### What We Explicitly Avoid

| Anti-pattern | Why |
|--------------|-----|
| Storing Google credentials | Security risk, unnecessary |
| Reverse-engineering RPC | Brittle, potential ToS violation |
| Headless-only mode | Some Google services detect headless |
| Parallel browser instances | State management nightmare |
| Automatic retries without backoff | Could trigger rate limiting |
| Caching NotebookLM responses | Data freshness concerns |

---

## Fallback Plan: UI/API Changes

### Detection Strategy

1. **Selector-based monitoring**: Store expected selectors in config
2. **Health check validation**: Verify key elements exist on each check
3. **Version detection**: Check for UI version indicators
4. **Error pattern matching**: Detect new error messages

### Response Playbook

| Change Type | Detection | Response |
|-------------|-----------|----------|
| Minor selector change | Element not found error | Update selector in config |
| Layout restructure | Multiple selector failures | Analyze new structure, update page objects |
| New auth flow | Login redirect not recognized | Update auth detection logic |
| API endpoint change | RPC fallback fails (if implemented) | Revert to pure browser automation |
| Complete redesign | Everything breaks | Major version bump, full rewrite of page objects |

### Mitigation Strategies

1. **Loose selectors**: Prefer semantic selectors (`[aria-label="..."]`, `[data-testid="..."]`) over structural (`.class > div > span`)

2. **Fallback selectors**: Define multiple selectors per element
   ```python
   NOTEBOOK_LIST_SELECTORS = [
       '[data-testid="notebook-list"]',
       '[aria-label="Notebooks"]',
       '.notebooks-container',
   ]
   ```

3. **Visual regression testing**: Screenshot comparison to detect unexpected changes

4. **Community monitoring**: Watch NotebookLM release notes, forums for change announcements

5. **Graceful degradation**: When specific features break, disable them rather than failing entirely

### Emergency Response

If NotebookLM makes breaking changes:

1. **Immediate**: Set health_check to return `degraded` status with message
2. **Short-term**: Analyze changes, create fix branch
3. **Medium-term**: Release patched version with updated selectors
4. **Communication**: Update README with known issues

---

## Future Considerations

### Potential V2 Features

If NotebookLM proves stable and useful:

- **create_notebook**: Full notebook lifecycle management
- **PDF upload**: Local file → NotebookLM source
- **Batch operations**: Add multiple sources in one call
- **Export**: Download notebook content as markdown
- **Audio overview**: Generate and retrieve audio

### Official API Wishlist

If Google releases an official API:

1. **Immediate migration**: Replace browser automation
2. **Keep abstraction layer**: Tools interface unchanged
3. **Deprecate browser code**: Maintain as fallback only
4. **Performance improvement**: Expect 10-100x faster operations

### Alternative Services

If NotebookLM becomes unusable:

| Alternative | Pros | Cons |
|-------------|------|------|
| Perplexity API | Official API, citation support | Paid, different capabilities |
| Custom RAG | Full control | High implementation effort |
| Notion AI | Existing integration | Different feature set |
| Google AI Studio | Official Google product | No source management |

---

## Decision Review Schedule

| Decision | Review Trigger |
|----------|----------------|
| ADR-001 (Browser automation) | Official API announced OR 3 major breakages |
| ADR-002 (Persistent profile) | Security concerns OR better auth method available |
| ADR-003 (Python) | Repo language strategy changes |
| ADR-004 (Rate limits) | Observed actual limits OR user complaints |
| ADR-005 (Serialization) | Performance requirements change |

---

## Changelog

| Date | Decision | Change |
|------|----------|--------|
| 2025-01-28 | Initial | Created ADR-001 through ADR-005 |
