"""Error categories used by retry, dead-letter, and recovery decisions."""

from __future__ import annotations

from enum import StrEnum


class ErrorClass(StrEnum):
    TRANSIENT_NETWORK = "TRANSIENT_NETWORK"
    RATE_LIMITED = "RATE_LIMITED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    POLICY_REJECTED = "POLICY_REJECTED"
    REMOTE_NOT_SUBMITTED = "REMOTE_NOT_SUBMITTED"
    REMOTE_AMBIGUOUS = "REMOTE_AMBIGUOUS"
    PLUGIN_BUG = "PLUGIN_BUG"
    PERMANENT_REMOTE = "PERMANENT_REMOTE"


class PipelineError(RuntimeError):
    error_class = ErrorClass.PLUGIN_BUG
    retryable = False

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


class TransientError(PipelineError):
    error_class = ErrorClass.TRANSIENT_NETWORK
    retryable = True


class AuthenticationRequired(PipelineError):
    error_class = ErrorClass.AUTH_REQUIRED


class PolicyRejected(PipelineError):
    error_class = ErrorClass.POLICY_REJECTED


class ValidationFailure(PipelineError):
    error_class = ErrorClass.VALIDATION_FAILED


class RemoteNotSubmitted(PipelineError):
    error_class = ErrorClass.REMOTE_NOT_SUBMITTED
    retryable = True


class RemoteAmbiguous(PipelineError):
    error_class = ErrorClass.REMOTE_AMBIGUOUS


def concise_error(error: BaseException, limit: int = 1000) -> str:
    return " ".join(str(error).split())[:limit]
