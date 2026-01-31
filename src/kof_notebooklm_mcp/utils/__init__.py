"""
工具函式模組。

- validation.py: 輸入驗證和清理
- retry.py: 重試邏輯（指數退避）
- rate_limit.py: Token bucket 速率限制器
- circuit_breaker.py: 斷路器模式
- errors.py: 標準化錯誤處理
"""

from .validation import (
    ValidationResult,
    validate_url,
    validate_text_content,
    validate_title,
    validate_notebook_id,
    validate_source_type,
    MAX_QUESTION_LENGTH,
    MAX_TEXT_SOURCE_LENGTH,
    MAX_NOTEBOOK_NAME_LENGTH,
    MAX_TITLE_LENGTH,
)

from .retry import (
    RetryConfig,
    RetryContext,
    DEFAULT_RETRY_CONFIG,
    retry_async,
    with_retry,
    calculate_delay,
    is_retryable_exception,
)

from .rate_limit import (
    RateLimitConfig,
    RateLimitExceeded,
    TokenBucket,
    RateLimiter,
    get_rate_limiter,
    rate_limit,
)

from .circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    CircuitBreaker,
    CircuitState,
    get_circuit_breaker,
    circuit_breaker_status,
)

from .errors import (
    ErrorCode,
    McpError,
    NotebookLMError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    TimeoutError,
    RateLimitError,
    RETRYABLE_ERRORS,
    AUTH_ERRORS,
    classify_error,
    error_response,
    handle_exception,
)

__all__ = [
    # Validation
    "ValidationResult",
    "validate_url",
    "validate_text_content",
    "validate_title",
    "validate_notebook_id",
    "validate_source_type",
    "MAX_QUESTION_LENGTH",
    "MAX_TEXT_SOURCE_LENGTH",
    "MAX_NOTEBOOK_NAME_LENGTH",
    "MAX_TITLE_LENGTH",
    # Retry
    "RetryConfig",
    "RetryContext",
    "DEFAULT_RETRY_CONFIG",
    "retry_async",
    "with_retry",
    "calculate_delay",
    "is_retryable_exception",
    # Rate Limit
    "RateLimitConfig",
    "RateLimitExceeded",
    "TokenBucket",
    "RateLimiter",
    "get_rate_limiter",
    "rate_limit",
    # Circuit Breaker
    "CircuitBreakerConfig",
    "CircuitBreakerOpen",
    "CircuitBreaker",
    "CircuitState",
    "get_circuit_breaker",
    "circuit_breaker_status",
    # Errors
    "ErrorCode",
    "McpError",
    "NotebookLMError",
    "AuthenticationError",
    "NotFoundError",
    "ValidationError",
    "TimeoutError",
    "RateLimitError",
    "RETRYABLE_ERRORS",
    "AUTH_ERRORS",
    "classify_error",
    "error_response",
    "handle_exception",
]
