from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from app.services.observation_provider import (
    HourlyObservation,
    ObservationFetchResult,
    ObservationProvider,
)

logger = logging.getLogger(__name__)

IEM_ASOS_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

# Conversion constants
KNOTS_TO_MS = 0.514444
INHG_TO_HPA = 33.8639


def _f_to_c(f: float | None) -> float | None:
    if f is None:
        return None
    return (f - 32.0) * 5.0 / 9.0


def _parse_float(value: str | None) -> float | None:
    """Parse a CSV field, treating 'M' (missing) and empty strings as None."""
    if value is None or value.strip() == "" or value.strip() == "M":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


class IemAsosProvider(ObservationProvider):
    @property
    def source_name(self) -> str:
        return "iem_asos"

    def fetch(
        self,
        station_code: str,
        start_date: date,
        end_date: date,
        timezone: str,
    ) -> ObservationFetchResult:
        # IEM expects end date as exclusive, so add one day
        ets = end_date + timedelta(days=1)

        params = {
            "station": station_code,
            "data": "all",
            "tz": "UTC",
            "format": "onlycomma",
            "latlon": "no",
            "report_type": "3",
            "year1": str(start_date.year),
            "month1": str(start_date.month),
            "day1": str(start_date.day),
            "year2": str(ets.year),
            "month2": str(ets.month),
            "day2": str(ets.day),
        }

        logger.info(
            "IEM ASOS fetch: %s from %s to %s",
            station_code, start_date, end_date,
        )

        resp = httpx.get(IEM_ASOS_URL, params=params, timeout=30.0)
        resp.raise_for_status()
        text = resp.text

        tz = ZoneInfo(timezone)
        utc = ZoneInfo("UTC")
        records: list[HourlyObservation] = []
        raw_rows: list[dict[str, str]] = []

        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            raw_rows.append(dict(row))

            raw_time = row.get("valid", "").strip()
            if not raw_time:
                continue

            obs_utc = datetime.fromisoformat(raw_time).replace(tzinfo=utc)
            obs_local = obs_utc.astimezone(tz).replace(tzinfo=None)

            # Convert units at provider boundary
            sknt = _parse_float(row.get("sknt"))
            drct = _parse_float(row.get("drct"))
            gust = _parse_float(row.get("gust"))
            tmpf = _parse_float(row.get("tmpf"))
            alti = _parse_float(row.get("alti"))

            wind_speed = sknt * KNOTS_TO_MS if sknt is not None else None
            wind_dir = drct
            gust_speed = gust * KNOTS_TO_MS if gust is not None else None
            temperature = _f_to_c(tmpf)
            pressure = alti * INHG_TO_HPA if alti is not None else None

            records.append(
                HourlyObservation(
                    observation_time_utc=obs_utc,
                    observation_time_local=obs_local,
                    wind_speed=wind_speed,
                    wind_direction=wind_dir,
                    gust_speed=gust_speed,
                    temperature=temperature,
                    pressure=pressure,
                )
            )

        logger.info("IEM ASOS: fetched %d records for %s", len(records), station_code)
        return ObservationFetchResult(
            records=records,
            raw_payload={"rows": raw_rows},
        )
