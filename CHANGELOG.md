# Changelog

## 0.1.3 - 2026-07-22

### Fixed

- Reject NotebookLM workspace controls and generated-content menus when they are accidentally captured as an AI answer.
- Return an explicit `ANSWER_EXTRACTION_FAILED` error instead of treating untrusted page text as a successful answer.
- Restrict answer and generation-state selectors to verified chat elements, and require a new stable answer before returning.
- Wait for the notebook detail view to become ready instead of reporting a loading page as an unnamed notebook with zero sources.
- Return explicit notebook and source extraction errors when the current UI cannot be parsed reliably.
- Bound optional element reads to avoid long delays when NotebookLM changes or removes an element.
- Accept argument-less MCP health checks when the runtime passes `null` arguments.

### Validation

- Passed the complete 133-test suite, changed-file linting, package compilation, and distribution build checks.
- Verified health, authentication, notebook metadata, source counts, and answer extraction against a live authenticated NotebookLM session.

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
