from __future__ import annotations

from dataclasses import dataclass
from datetime import date

BUSINESS_TIMEZONE = "America/Lima"
CHANNELS = ("nacional", "internacional")
CHANNEL_CURRENCY = {"nacional": "PEN", "internacional": "USD"}


@dataclass(frozen=True, slots=True)
class Period:
    """Ventana de cobro inclusiva en ambos extremos, en hora de negocio America/Lima."""

    channel: str
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.channel not in CHANNELS:
            raise ValueError(f"unknown channel: {self.channel!r}")
        if self.start > self.end:
            raise ValueError("period start must be <= end")

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end

    @property
    def currency(self) -> str:
        return CHANNEL_CURRENCY[self.channel]

    @property
    def label(self) -> str:
        return f"{self.channel}:{self.start.isoformat()}:{self.end.isoformat()}"


def parse_date(value: object) -> date | None:
    """Acepta `date`, `datetime` o texto ISO; descarta la hora sin convertir zona."""
    if value is None or value == "" or value is False:
        return None
    if hasattr(value, "date") and callable(value.date):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    return date.fromisoformat(text)
