"""Errors raised by the Safari Xiaohongshu publisher."""


class XiaohongshuPublishError(RuntimeError):
    """Base error for the local publisher."""


class PublishPreflightError(XiaohongshuPublishError):
    """The request or authenticated Safari state is not ready."""


class SafariAutomationError(XiaohongshuPublishError):
    """Safari could not be controlled as expected before submission."""


class SubmissionRejectedError(XiaohongshuPublishError):
    """Xiaohongshu visibly rejected a submitted note."""


class SubmissionUncertainError(XiaohongshuPublishError):
    """Submission started but no reliable final result was found."""
