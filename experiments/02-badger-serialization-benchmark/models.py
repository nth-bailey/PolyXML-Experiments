from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional


@dataclass(slots=True, kw_only=True)
class TextType:
    lang: Optional[str] = None
    value: str = ""


@dataclass(slots=True, kw_only=True)
class MultilingualString:
    content: List[TextType] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class PrivateCode:
    type_value: Optional[str] = None
    value: str = ""


@dataclass(slots=True, kw_only=True)
class PrivateCodes:
    private_code: List[PrivateCode] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class LocationStructure2:
    longitude: Decimal
    latitude: Decimal
    altitude: Optional[Decimal] = None


@dataclass(slots=True, kw_only=True)
class ScheduledStopPoint:
    id: str
    version: str
    name: Optional[MultilingualString] = None
    private_codes: Optional[PrivateCodes] = None
    location: Optional[LocationStructure2] = None
    stop_type: str = "busStop"
    url: Optional[str] = None


def generate_sample_stops(count: int = 10_000) -> List[ScheduledStopPoint]:
    """Generate realistic NeTEx ScheduledStopPoint instances."""
    stops = []
    base_lon = Decimal("4.895168")
    base_lat = Decimal("52.370216")

    for i in range(count):
        stop = ScheduledStopPoint(
            id=f"NL:OPENOV:ScheduledStopPoint:{i + 1}",
            version="1",
            name=MultilingualString(
                content=[
                    TextType(lang="nl", value=f"Halte Centrum {i + 1}"),
                    TextType(lang="en", value=f"Central Station Stop {i + 1}"),
                ]
            ),
            private_codes=PrivateCodes(
                private_code=[
                    PrivateCode(type_value="tariffZone", value=f"ZONE_{i % 50}"),
                    PrivateCode(type_value="quayRef", value=f"Q_{i + 1000}"),
                ]
            ),
            location=LocationStructure2(
                longitude=base_lon + Decimal(str(round((i % 1000) * 0.0001, 6))),
                latitude=base_lat + Decimal(str(round((i % 1000) * 0.0001, 6))),
            ),
            stop_type="busStop" if i % 2 == 0 else "tramStop",
            url=f"https://openov.nl/stops/{i + 1}",
        )
        stops.append(stop)

    return stops
