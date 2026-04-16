"""Tests for ``gfs_hindcast_provider`` — NCSS URL/params/plan/merge helpers.

Everything that touches the network is mocked.  No real HTTP calls are
made and no real NetCDF files are parsed (a fake xarray-like dataset
with a ``values`` attribute is enough for the extraction logic).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services import gfs_hindcast_provider as ghp
from app.services.gfs_hindcast_provider import (
    _VAR_GROUPS,
    GfsHindcastError,
    GfsHindcastProvider,
    _merge_group_dsets,
    _ncss_params,
    _ncss_url,
    _scalar,
    _wind_dir_deg,
    _wind_speed,
)


UTC = timezone.utc


# ---------------------------------------------------------------------------
# URL / params
# ---------------------------------------------------------------------------


class TestNcssUrl:
    def test_builds_yyyymmdd_path(self):
        mrt = datetime(2023, 6, 15, 0, tzinfo=UTC)
        url = _ncss_url(mrt, cycle_hour=0, fhour=12)
        assert "/2023/20230615/gfs.0p25.2023061500.f012.grib2" in url

    def test_cycle_hour_zero_padded(self):
        mrt = datetime(2023, 6, 15, 0, tzinfo=UTC)
        url = _ncss_url(mrt, cycle_hour=6, fhour=0)
        assert "2023061506.f000" in url

    def test_fhour_three_digits(self):
        mrt = datetime(2023, 6, 15, 0, tzinfo=UTC)
        url = _ncss_url(mrt, cycle_hour=0, fhour=9)
        assert ".f009.grib2" in url


class TestNcssParams:
    def test_variables_repeated(self):
        params = _ncss_params(
            ["u-component_of_wind_height_above_ground", "v-component_of_wind_height_above_ground"],
            34.0,
            -118.0,
            datetime(2023, 6, 15, 15, tzinfo=UTC),
        )
        var_values = [v for k, v in params if k == "var"]
        assert var_values == [
            "u-component_of_wind_height_above_ground",
            "v-component_of_wind_height_above_ground",
        ]

    def test_includes_point_and_time(self):
        params = dict(
            _ncss_params(
                ["Temperature_height_above_ground"],
                34.5,
                -118.25,
                datetime(2023, 6, 15, 15, tzinfo=UTC),
            )
        )
        assert params["latitude"] == "34.5"
        assert params["longitude"] == "-118.25"
        assert params["time"] == "2023-06-15T15:00:00Z"
        assert params["accept"] == "netcdf4"


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


class FakeVar:
    """Mimic the tiny slice of the xarray DataArray API that _scalar uses."""

    def __init__(self, value):
        import numpy as np
        self.values = np.array([value])


class FakeDataset:
    """Dict-like stand-in for an xarray.Dataset point subset."""

    def __init__(self, values: dict[str, float]):
        self._vars = {k: FakeVar(v) for k, v in values.items()}
        self.data_vars = set(values.keys())

    def __contains__(self, item):
        return item in self._vars

    def __getitem__(self, key):
        return self._vars[key]


class TestScalar:
    def test_returns_float(self):
        ds = FakeDataset({"foo": 3.5})
        assert _scalar(ds, "foo") == pytest.approx(3.5)

    def test_missing_variable_returns_none(self):
        ds = FakeDataset({"foo": 1.0})
        assert _scalar(ds, "bar") is None

    def test_nan_returns_none(self):
        ds = FakeDataset({"foo": float("nan")})
        assert _scalar(ds, "foo") is None


class TestWindHelpers:
    def test_zero_wind_is_zero_speed(self):
        assert _wind_speed(0.0, 0.0) == 0.0

    def test_pure_eastward_is_from_west(self):
        # u=5, v=0 → wind blowing to the east, coming from west → 270 deg
        assert _wind_dir_deg(5.0, 0.0) == pytest.approx(270.0)

    def test_pure_northward_is_from_south(self):
        # u=0, v=5 → wind to the north, from the south → 180 deg
        assert _wind_dir_deg(0.0, 5.0) == pytest.approx(180.0)


class TestMergeGroups:
    def test_full_payload(self):
        groups = {
            "wind": FakeDataset(
                {
                    "u-component_of_wind_height_above_ground": 3.0,
                    "v-component_of_wind_height_above_ground": 4.0,
                }
            ),
            "temp": FakeDataset(
                {"Temperature_height_above_ground": 293.15}  # 20 C in K
            ),
            "pres_cloud": FakeDataset(
                {
                    "Pressure_reduced_to_MSL_msl": 101325.0,  # 1013.25 hPa in Pa
                    "Total_cloud_cover_entire_atmosphere": 0.5,
                }
            ),
        }
        ws, wd, temp, pres, cloud = _merge_group_dsets(groups)
        assert ws == pytest.approx(5.0)
        assert wd is not None
        assert temp == pytest.approx(20.0, abs=0.01)
        assert pres == pytest.approx(1013.25, abs=0.1)
        assert cloud == pytest.approx(50.0)

    def test_cloud_cover_missing_ok(self):
        groups = {
            "pres_cloud": FakeDataset(
                {"Pressure_reduced_to_MSL_msl": 1013.0}
            ),
        }
        ws, wd, temp, pres, cloud = _merge_group_dsets(groups)
        assert cloud is None
        assert pres == pytest.approx(1013.0)
        assert ws is None and wd is None and temp is None


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


class TestPlanTasks:
    def test_single_day_generates_window_hours(self, monkeypatch):
        monkeypatch.setattr(ghp.settings, "gfs_analysis_local_start", 8)
        monkeypatch.setattr(ghp.settings, "gfs_analysis_local_end", 16)

        provider = GfsHindcastProvider()
        tasks = provider._plan_tasks(
            date(2023, 6, 15),
            date(2023, 6, 15),
            "America/Los_Angeles",
            8,
            16,
        )

        # 9 local hours (08..16) × 1 day.
        assert len(tasks) == 9
        # All tasks share the same target date and D 00Z model run.
        target_dates = {t[0] for t in tasks}
        assert target_dates == {date(2023, 6, 15)}
        mrts = {t[1] for t in tasks}
        assert mrts == {datetime(2023, 6, 15, 0, tzinfo=UTC)}
        # Forecast hours are strictly increasing.
        fhours = [t[2] for t in tasks]
        assert fhours == sorted(fhours)

    def test_multi_day(self, monkeypatch):
        monkeypatch.setattr(ghp.settings, "gfs_analysis_local_start", 8)
        monkeypatch.setattr(ghp.settings, "gfs_analysis_local_end", 16)

        provider = GfsHindcastProvider()
        tasks = provider._plan_tasks(
            date(2023, 6, 15),
            date(2023, 6, 17),
            "America/Los_Angeles",
            8,
            16,
        )
        target_dates = sorted({t[0] for t in tasks})
        assert target_dates == [date(2023, 6, 15), date(2023, 6, 16), date(2023, 6, 17)]
        assert len(tasks) == 9 * 3


# ---------------------------------------------------------------------------
# _request_group retries
# ---------------------------------------------------------------------------


def _fake_response(status: int, content: bytes = b"", text: str = ""):
    resp = SimpleNamespace(
        status_code=status,
        content=content,
        text=text,
    )

    def raise_for_status():
        if status >= 400:
            import requests
            raise requests.HTTPError(str(status), response=resp)

    resp.raise_for_status = raise_for_status
    return resp


class TestRequestGroupRetries:
    def test_400_is_not_retried(self):
        session = MagicMock()
        session.get.return_value = _fake_response(400, text="variable not found")

        # Bypass the xr None guard by ensuring it's truthy.
        with patch.object(ghp, "xr", object()):
            with pytest.raises(GfsHindcastError):
                ghp._request_group(
                    session,
                    "http://example/u",
                    ("Total_cloud_cover_entire_atmosphere",),
                    34.0,
                    -118.0,
                    datetime(2023, 6, 15, 15, tzinfo=UTC),
                    timeout=10,
                    max_retries=5,
                )
        assert session.get.call_count == 1

    def test_503_retries_and_eventually_raises(self):
        session = MagicMock()
        session.get.return_value = _fake_response(503)

        with patch.object(ghp, "xr", object()):
            with patch.object(ghp.time_mod, "sleep") as sleep_mock:
                with pytest.raises(GfsHindcastError):
                    ghp._request_group(
                        session,
                        "http://example/u",
                        ("Temperature_height_above_ground",),
                        34.0,
                        -118.0,
                        datetime(2023, 6, 15, 15, tzinfo=UTC),
                        timeout=10,
                        max_retries=3,
                    )
                # Three attempts → two sleeps between them.
                assert session.get.call_count == 3
                assert sleep_mock.call_count == 2

    def test_200_success_returns_dataset(self):
        session = MagicMock()
        session.get.return_value = _fake_response(200, content=b"not-real-nc")

        fake_ds = object()
        fake_xr = MagicMock()
        fake_xr.load_dataset.return_value = fake_ds

        with patch.object(ghp, "xr", fake_xr):
            out = ghp._request_group(
                session,
                "http://example/u",
                ("Temperature_height_above_ground",),
                34.0,
                -118.0,
                datetime(2023, 6, 15, 15, tzinfo=UTC),
                timeout=10,
                max_retries=3,
            )
        assert out is fake_ds
        assert session.get.call_count == 1


# ---------------------------------------------------------------------------
# Cloud-cover fallback
# ---------------------------------------------------------------------------


class TestFetchUnitCloudFallback:
    def test_pres_cloud_400_retries_without_cloud(self):
        provider = GfsHindcastProvider()
        fake_pres_only_ds = object()

        call_log: list[tuple[str, ...]] = []

        def fake_request_group(session, url, variables, *args, **kwargs):
            call_log.append(tuple(variables))
            # First call for pres_cloud raises 400 about cloud cover.
            if "Total_cloud_cover_entire_atmosphere" in variables:
                raise GfsHindcastError("NCSS 400 for cloud cover")
            return fake_pres_only_ds

        session = MagicMock()
        with patch.object(ghp, "xr", object()):
            with patch.object(ghp, "_request_group", side_effect=fake_request_group):
                groups = provider._fetch_unit(
                    session,
                    34.0,
                    -118.0,
                    date(2023, 6, 15),
                    datetime(2023, 6, 15, 0, tzinfo=UTC),
                    fhour=15,
                    timeout=10,
                    max_retries=3,
                )

        # Three groups fetched, pres_cloud retried with fewer vars.
        assert "wind" in groups
        assert "temp" in groups
        assert "pres_cloud" in groups
        # The pres_cloud fallback strips the cloud variable.
        assert any(
            "Total_cloud_cover_entire_atmosphere" not in vars_tuple
            and "Pressure_reduced_to_MSL_msl" in vars_tuple
            for vars_tuple in call_log
        )


# ---------------------------------------------------------------------------
# Static sanity
# ---------------------------------------------------------------------------


class TestVarGroups:
    def test_three_groups(self):
        assert set(_VAR_GROUPS.keys()) == {"wind", "temp", "pres_cloud"}

    def test_cloud_is_in_pres_cloud(self):
        assert (
            "Total_cloud_cover_entire_atmosphere" in _VAR_GROUPS["pres_cloud"]
        )

    def test_provider_source_name(self):
        assert GfsHindcastProvider().source_name == "gfs_hindcast"


# Keep unused-import linters quiet in test-file edits.
_ = timedelta
