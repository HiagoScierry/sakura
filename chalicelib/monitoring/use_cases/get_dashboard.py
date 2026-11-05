from chalicelib.monitoring.models.dashboard import Dashboard, ServiceOverview
from chalicelib.monitoring.ports import ServiceRepository


class GetDashboard:
    def __init__(self, services: ServiceRepository) -> None:
        self._services = services

    def execute(self) -> Dashboard:
        services = sorted(self._services.list(), key=lambda s: s.name)
        enabled = [s for s in services if s.is_enabled]
        down = [ServiceOverview.of(s) for s in enabled if s.is_down]
        return Dashboard(
            ok=not down,
            monitored=[ServiceOverview.of(s) for s in enabled],
            down=down,
            never_checked=[ServiceOverview.of(s) for s in enabled if s.never_checked],
            disabled=[ServiceOverview.of(s) for s in services if not s.is_enabled],
        )
