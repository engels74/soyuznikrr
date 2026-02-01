"""Health check endpoints for Zondarr.

Provides health check endpoints for monitoring and orchestration:
- GET /health: Overall system status including all dependencies
- GET /health/live: Kubernetes liveness probe (always returns 200 if process is running)
- GET /health/ready: Kubernetes readiness probe (checks database connectivity)

Health status values:
- "healthy": All dependencies are operational
- "degraded": One or more dependencies are failing

Uses Litestar Controller pattern with proper dependency injection.
"""

from collections.abc import Sequence

from litestar import Controller, Response, get
from litestar.status_codes import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import HealthCheckResponse, LivenessResponse, ReadinessResponse


class HealthController(Controller):
    """Health check endpoints for monitoring and orchestration.

    Provides endpoints for:
    - Overall health status with dependency checks
    - Kubernetes liveness probes
    - Kubernetes readiness probes
    """

    path: str = "/health"
    tags: Sequence[str] | None = ["Health"]

    @get(
        "/",
        include_in_schema=False,
        cache=False,
        summary="Overall health check",
        description="Returns overall system status including all dependency checks.",
    )
    async def health_check(
        self,
        session: AsyncSession,
    ) -> Response[HealthCheckResponse]:
        """Overall health check including all dependencies.

        Checks database connectivity and returns aggregated status.
        Returns HTTP 200 if all checks pass, HTTP 503 if any check fails.

        Args:
            session: Database session for connectivity check.

        Returns:
            Response with HealthCheckResponse body and appropriate status code.
        """
        checks = {
            "database": await self._check_database(session),
        }
        all_healthy = all(checks.values())

        return Response(
            HealthCheckResponse(
                status="healthy" if all_healthy else "degraded",
                checks=checks,
            ),
            status_code=HTTP_200_OK if all_healthy else HTTP_503_SERVICE_UNAVAILABLE,
        )

    @get(
        "/live",
        include_in_schema=False,
        cache=False,
        summary="Liveness probe",
        description="Kubernetes liveness probe - always returns OK if process is running.",
    )
    async def liveness(self) -> LivenessResponse:
        """Kubernetes liveness probe - always returns OK if process is running.

        This endpoint indicates whether the application process is alive.
        It always returns HTTP 200 as long as the process can handle requests.

        Returns:
            LivenessResponse with status "alive".
        """
        return LivenessResponse(status="alive")

    @get(
        "/ready",
        include_in_schema=False,
        cache=False,
        summary="Readiness probe",
        description="Kubernetes readiness probe - checks if ready to serve traffic.",
    )
    async def readiness(
        self,
        session: AsyncSession,
    ) -> Response[ReadinessResponse]:
        """Kubernetes readiness probe - checks if ready to serve traffic.

        Verifies database connectivity to determine if the application
        can handle incoming requests.

        Args:
            session: Database session for connectivity check.

        Returns:
            Response with ReadinessResponse body.
            HTTP 200 if ready, HTTP 503 if not ready.
        """
        if await self._check_database(session):
            return Response(
                ReadinessResponse(status="ready"),
                status_code=HTTP_200_OK,
            )
        return Response(
            ReadinessResponse(status="not ready"),
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
        )

    async def _check_database(self, session: AsyncSession) -> bool:
        """Check database connectivity.

        Executes a simple query to verify the database connection is working.

        Args:
            session: Database session to use for the check.

        Returns:
            True if database is reachable, False otherwise.
        """
        try:
            _ = await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
