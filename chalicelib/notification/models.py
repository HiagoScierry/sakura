from datetime import datetime
from typing import Self

from pydantic import BaseModel

from chalicelib.monitoring.models.dashboard import Dashboard, ServiceOverview


class DailyReport(BaseModel):
    """Dados do resumo diário (as regras ficam em `notification/rules.py`)."""
    generated_at: datetime
    monitored: list[ServiceOverview]
    down: list[ServiceOverview]
    never_checked: list[ServiceOverview]

    @classmethod
    def from_dashboard(cls, dashboard: Dashboard, now: datetime) -> Self:
        return cls(generated_at=now, monitored=dashboard.monitored,
                   down=dashboard.down, never_checked=dashboard.never_checked)
