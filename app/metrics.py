import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
)

APP_INFO = Gauge(
    "app_info",
    "Static application version/build information",
    ["version", "git_sha"],
)

DB_UP = Gauge(
    "app_database_up",
    "Whether the last database readiness check succeeded (1) or failed (0)",
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        route = request.scope.get("route")
        path_template = route.path if route is not None else "unmatched"

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration = time.perf_counter() - start
            REQUEST_LATENCY.labels(method=request.method, path=path_template).observe(duration)
            REQUEST_COUNT.labels(method=request.method, path=path_template, status="500").inc()
            raise

        duration = time.perf_counter() - start
        REQUEST_LATENCY.labels(method=request.method, path=path_template).observe(duration)
        REQUEST_COUNT.labels(
            method=request.method, path=path_template, status=str(response.status_code)
        ).inc()
        return response


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
