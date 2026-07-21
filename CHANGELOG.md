# Changelog

## 0.1.2 - 2026-07-21

### Fixed

- Restore source, notebook title, copied-text dialog, response, and citation extraction against the current NotebookLM UI.
- Wait for a genuinely new, stable streamed answer instead of returning the previous or partial response.
- Extract citation titles and excerpts, and remove duplicate citation results.
- Avoid source-link lookup delays when a source has no link element.
- Keep health checks from being interpreted as tool errors or mutating the shared circuit breaker.
- Redact source text, questions, and URLs from informational logs.
- Classify dangerous URL schemes as unsafe input before general protocol validation.

### Validation

- Verified against a live authenticated NotebookLM session with copied-text sources, repeated questions, long streamed answers, and citation extraction.
