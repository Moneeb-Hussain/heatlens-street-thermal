"""Domain errors. The API layer maps these to HTTP; CLIs print them."""


class HeatLensError(Exception):
    code = "HEATLENS_ERROR"

    def __init__(self, message: str, code=None):
        super().__init__(message)
        if code:
            self.code = code


class ConfigurationError(HeatLensError):
    code = "CONFIGURATION"


class NotFoundError(HeatLensError):
    code = "NOT_FOUND"


class ValidationFailed(HeatLensError):
    code = "VALIDATION"


class UpstreamError(HeatLensError):
    code = "UPSTREAM"


class CapabilityUnavailable(HeatLensError):
    """A feature exists in the API but its artefact or key is missing."""

    def __init__(self, code, message):
        super().__init__(message, code=code)
