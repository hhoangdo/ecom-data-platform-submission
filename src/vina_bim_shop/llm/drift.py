"""Async, precomputed-population Section 03 drift service."""

from __future__ import annotations

import asyncio
import math
import random
from datetime import date, datetime, time, timedelta, timezone
from typing import Callable
from uuid import NAMESPACE_URL, uuid5

from .contracts import DriftDetectRequest, DriftDetectResponse, FeatureHealthPoint, Section03FeatureRow, TimeWindow, UtcDateTime
from .ports import FeastPort


DEPENDENCY_TIMEOUT_SECONDS = 1.5
SECTION03_MANIFEST_SHA256 = "af7189d00a187e539bb777d89111d2860a97822f34c2c911adc3eadf6166f8ad"
PUBLISHED_MONITORING_END = date(2026, 5, 1)


class FeatureUnavailableError(LookupError):
    """Raised when no verified active Section 03 health source is available."""


class DependencyTimeoutError(TimeoutError):
    """Raised when one bounded dependency attempt and retry cannot complete."""


class DriftDetectionService:
    """Read fixed daily health rows without recomputing population PSI."""

    def __init__(
        self,
        feast: FeastPort | None = None,
        *,
        feature_service_version: str = "unavailable",
        baseline_date: date | None = None,
        published_monitoring_end: date | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._feast = feast
        self._feature_service_version = feature_service_version
        self._baseline_date = baseline_date
        self._published_monitoring_end = published_monitoring_end or PUBLISHED_MONITORING_END
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def detect(self, request: DriftDetectRequest) -> DriftDetectResponse:
        """Return a deterministic population result from published daily health rows."""

        if self._feast is None or self._baseline_date is None:
            raise FeatureUnavailableError("feature_unavailable")
        self._validate_windows(request)
        published_window = TimeWindow(
            start=datetime.combine(self._baseline_date, time.min, timezone.utc),
            end=request.candidate_window.end,
        )
        points = list(await self._dependency(
            lambda: self._feast.read_feature_health(
                feature_name=request.feature_name, window=published_window
            )
        ))
        baseline, selected = self._validate_published_points(points, request)
        peak = max(selected, key=lambda point: (point.psi_vs_baseline, point.monitoring_date))
        context: Section03FeatureRow | None = None
        if request.id is not None:
            context = await self._dependency(lambda: self._feast.read_customer_snapshot(id=request.id or "", as_of=request.candidate_window.end))
        status = _status(peak.psi_vs_baseline)
        observed_at = self._clock().astimezone(timezone.utc)
        identity = f"{request.model_dump_json()}:{peak.monitoring_date}:{peak.psi_vs_baseline}"
        return DriftDetectResponse(
            request_id=uuid5(NAMESPACE_URL, identity), scope="population", feature_name=request.feature_name,
            window_days=7, baseline_window=request.baseline_window, candidate_window=request.candidate_window,
            population_size=peak.customer_count, candidate_day_count=len(selected),
            baseline_mean=baseline.mean_value,
            candidate_mean=peak.mean_value, psi=peak.psi_vs_baseline, status=status,
            drift_detected=status != "stable", feature_service_version=self._feature_service_version,
            customer_context=context, observed_at=observed_at,
        )

    async def read_section03_join(self, id: str, as_of: UtcDateTime) -> Section03FeatureRow | None:
        """Read optional cutoff-safe context without altering the population result."""

        if self._feast is None:
            raise FeatureUnavailableError("feature_unavailable")
        return await self._dependency(lambda: self._feast.read_customer_snapshot(id=id, as_of=as_of))

    async def is_ready(self) -> bool:
        """Return readiness only for a verified active Section 03 adapter."""

        if self._feast is None:
            return False
        method = getattr(self._feast, "active_section03_manifest_hash", None)
        if not callable(method):
            return False
        try:
            return await self._dependency(method) == SECTION03_MANIFEST_SHA256
        except DependencyTimeoutError:
            return False

    def _validate_windows(self, request: DriftDetectRequest) -> None:
        expected_start = datetime.combine(self._baseline_date - timedelta(days=6), time.min, timezone.utc)
        expected_end = datetime.combine(self._baseline_date + timedelta(days=1), time.min, timezone.utc)
        if request.baseline_window.start != expected_start or request.baseline_window.end != expected_end:
            raise ValueError("baseline_window must equal the manifest complete baseline day")
        candidate = request.candidate_window
        if candidate.start.time() != time.min or candidate.end.time() != time.min:
            raise ValueError("candidate_window must contain complete UTC days")
        if candidate.start.date() <= self._baseline_date:
            raise ValueError("candidate_window must begin after baseline_date")
        days = (candidate.end - candidate.start).days
        if not 1 <= days <= 30:
            raise ValueError("candidate_window must contain 1-30 complete UTC days")
        if candidate.end.date() - timedelta(days=1) > self._published_monitoring_end:
            raise ValueError("candidate_window exceeds the published monitoring range")

    def _validate_published_points(
        self,
        points: list[FeatureHealthPoint],
        request: DriftDetectRequest,
    ) -> tuple[FeatureHealthPoint, list[FeatureHealthPoint]]:
        """Fail closed unless the baseline and every requested UTC day are present once."""

        assert self._baseline_date is not None
        expected_dates = [self._baseline_date] + [
            request.candidate_window.start.date() + timedelta(days=offset)
            for offset in range((request.candidate_window.end - request.candidate_window.start).days)
        ]
        if [point.monitoring_date for point in points] != expected_dates:
            raise FeatureUnavailableError("feature_unavailable")
        baseline = points[0]
        if baseline.customer_count <= 0:
            raise FeatureUnavailableError("feature_unavailable")
        for point in points:
            if (
                point.feature_name != request.feature_name
                or point.window_days != 7
                or point.baseline_date != self._baseline_date
                or point.customer_count != baseline.customer_count
                or not math.isfinite(point.mean_value)
                or not math.isfinite(point.psi_vs_baseline)
                or point.psi_vs_baseline < 0
                or point.drift_status != _status(point.psi_vs_baseline)
            ):
                raise FeatureUnavailableError("feature_unavailable")
        return baseline, points[1:]

    async def _dependency(self, operation):
        for attempt in range(2):
            try:
                async with asyncio.timeout(DEPENDENCY_TIMEOUT_SECONDS):
                    return await operation()
            except ConnectionError:
                if attempt == 0:
                    await asyncio.sleep(random.uniform(0.01, 0.05))
                    continue
                raise DependencyTimeoutError("dependency_timeout") from None
            except TimeoutError:
                raise DependencyTimeoutError("dependency_timeout") from None
        raise DependencyTimeoutError("dependency_timeout")


def _status(psi: float) -> str:
    if psi >= 0.15:
        return "alert"
    if psi >= 0.10:
        return "warning"
    return "stable"


__all__ = ["DEPENDENCY_TIMEOUT_SECONDS", "DependencyTimeoutError", "DriftDetectionService", "FeatureUnavailableError", "PUBLISHED_MONITORING_END", "SECTION03_MANIFEST_SHA256"]
