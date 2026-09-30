"""Errors raised while loading declarative policy definitions."""

from pathlib import Path


class PolicyLoadError(Exception):
    """Base error for a policy file that cannot produce a valid definition."""

    def __init__(self, policy_path: Path, message: str) -> None:
        super().__init__(message)
        self.policy_path = policy_path


class PolicyFileNotFoundError(PolicyLoadError):
    """Raised when the requested policy file does not exist."""


class PolicyFileReadError(PolicyLoadError):
    """Raised when an existing policy file cannot be read."""


class MalformedPolicyYamlError(PolicyLoadError):
    """Raised when a policy file is not syntactically valid safe YAML."""


class InvalidPolicyStructureError(PolicyLoadError):
    """Raised when valid YAML does not satisfy the policy domain schema."""
