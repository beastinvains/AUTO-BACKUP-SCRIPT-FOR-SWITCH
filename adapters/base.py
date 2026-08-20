from __future__ import annotations

from abc import ABC, abstractmethod

from core.models import DiscoveryResult, DiscoveryTarget


class AdapterError(RuntimeError):
    """A safe, categorized failure while talking to one device."""


class UnsupportedOperationError(AdapterError):
    pass


class BaseDeviceAdapter(ABC):
    """Vendor boundary. Implementations may perform only allowlisted read operations."""

    @abstractmethod
    def discover(self, target: DiscoveryTarget) -> DiscoveryResult:
        raise NotImplementedError

    @abstractmethod
    def get_device_info(self, target: DiscoveryTarget):
        raise NotImplementedError

    @abstractmethod
    def get_health(self, target: DiscoveryTarget):
        raise NotImplementedError

    @abstractmethod
    def get_interfaces(self, target: DiscoveryTarget):
        raise NotImplementedError

    @abstractmethod
    def get_neighbors(self, target: DiscoveryTarget):
        raise NotImplementedError

    def get_configuration(self, target: DiscoveryTarget):
        raise UnsupportedOperationError("Configuration operations begin in Phase 2")

    def backup_configuration(self, target: DiscoveryTarget):
        raise UnsupportedOperationError("Configuration operations begin in Phase 2")

