class DiagnosisError(Exception):
    """Base exception raised by the diagnosis SDK."""


class InvalidSignalError(DiagnosisError, ValueError):
    """The supplied signal does not satisfy the model input contract."""


class ArtifactCompatibilityError(DiagnosisError):
    """The model bundle is missing, corrupt, or incompatible."""


class PersistenceWarning(RuntimeWarning):
    """A diagnosis completed, but its history record could not be saved."""
