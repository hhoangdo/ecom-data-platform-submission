"""Section 03 drift application boundary with no live runtime dependency."""

from __future__ import annotations

from .contracts import DriftDetectRequest, DriftDetectResponse, Section03FeatureRow, UtcDateTime
from .ports import FeastPort


class DriftDetectionService:
    """Delegate fixed-feature drift and cutoff-safe context reads through Feast."""

    def __init__(
        self,
        feast: FeastPort | None = None,
        *,
        feature_service_version: str = "unavailable",
    ) -> None:
        self._feast = feast
        self._feature_service_version = feature_service_version

    async def detect(self, request: DriftDetectRequest) -> DriftDetectResponse:
        """Expose the typed drift boundary without fabricating observations."""

        raise NotImplementedError("drift computation belongs to successor topics")

    async def read_section03_join(self, id: str, as_of: UtcDateTime) -> Section03FeatureRow:
        """Expose the exact Section 03 point-in-time join boundary."""

        if self._feast is None:
            raise LookupError("feature_unavailable")
        raise NotImplementedError("Section 03 adapter belongs to successor topics")


__all__ = ["DriftDetectionService"]
