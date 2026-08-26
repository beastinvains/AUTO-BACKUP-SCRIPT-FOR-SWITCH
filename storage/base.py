from __future__ import annotations

from abc import ABC, abstractmethod


class ArtifactStorage(ABC):
    """Immutable artifact store; callers use opaque relative URIs only."""

    @abstractmethod
    def put_configuration(self, *, device_name: str, version_id: str, content: bytes, collected_at) -> str:
        raise NotImplementedError

    @abstractmethod
    def get(self, uri: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def delete(self, uri: str) -> None:
        raise NotImplementedError
