"""Immutable configuration normalization, versioning, diff, and retention."""

from configuration.service import ConfigurationService, configuration_diff, normalize_configuration

__all__ = ["ConfigurationService", "configuration_diff", "normalize_configuration"]
