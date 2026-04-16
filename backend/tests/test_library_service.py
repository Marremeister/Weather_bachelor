"""Tests for ``library_service`` — date-range helper and status filter.

Pure unit tests: the build loop and DB internals are not exercised
here (they require Postgres).  The helpers tested below are the new
surface introduced by the GFS hindcast library work.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services import library_service as lib
from app.services.library_service import (
    _date_range_for_source,
    _season_date_chunks,
    get_library_status,
)


# ---------------------------------------------------------------------------
# _date_range_for_source
# ---------------------------------------------------------------------------


class TestDateRangeForSource:
    def test_era5_reads_era5_settings(self, monkeypatch):
        monkeypatch.setattr(lib.settings, "era5_start_year", 2015)
        monkeypatch.setattr(lib.settings, "era5_end_year", 2024)
        monkeypatch.setattr(lib.settings, "era5_months", "05,06,07")

        start, end, months, chunk_months = _date_range_for_source("era5")
        assert start == 2015
        assert end == 2024
        assert months == [5, 6, 7]
        # ERA5 uses season-sized chunks (12).
        assert chunk_months == 12

    def test_gfs_hindcast_reads_gfs_settings(self, monkeypatch):
        monkeypatch.setattr(lib.settings, "gfs_hindcast_start_year", 2016)
        monkeypatch.setattr(lib.settings, "gfs_hindcast_end_year", 2024)
        monkeypatch.setattr(lib.settings, "gfs_hindcast_months", "05,06,07,08,09")
        monkeypatch.setattr(lib.settings, "gfs_hindcast_chunk_months", 1)

        start, end, months, chunk_months = _date_range_for_source("gfs_hindcast")
        assert start == 2016
        assert end == 2024
        assert months == [5, 6, 7, 8, 9]
        # GFS hindcast uses monthly chunks.
        assert chunk_months == 1

    def test_unknown_source_raises(self):
        with pytest.raises(ValueError):
            _date_range_for_source("not-a-source")


# ---------------------------------------------------------------------------
# _season_date_chunks
# ---------------------------------------------------------------------------


class TestSeasonDateChunks:
    def test_year_chunks_match_full_season(self):
        chunks = _season_date_chunks(2022, 2023, [5, 6, 7, 8, 9], chunk_months=12)
        # One chunk per year, May 1..Sept 30.
        assert len(chunks) == 2
        assert chunks[0] == (date(2022, 5, 1), date(2022, 9, 30))
        assert chunks[1] == (date(2023, 5, 1), date(2023, 9, 30))

    def test_monthly_chunks_gfs_hindcast(self):
        chunks = _season_date_chunks(2022, 2022, [5, 6, 7, 8, 9], chunk_months=1)
        # 5 months × 1 year = 5 chunks.
        assert len(chunks) == 5
        assert chunks[0] == (date(2022, 5, 1), date(2022, 5, 31))
        assert chunks[1] == (date(2022, 6, 1), date(2022, 6, 30))
        assert chunks[-1] == (date(2022, 9, 1), date(2022, 9, 30))

    def test_monthly_chunks_multi_year(self):
        chunks = _season_date_chunks(2016, 2024, [5, 6, 7, 8, 9], chunk_months=1)
        # 9 years × 5 months = 45 chunks.
        assert len(chunks) == 9 * 5

    def test_empty_months(self):
        assert _season_date_chunks(2022, 2023, [], chunk_months=1) == []

    def test_end_year_inclusive(self):
        chunks = _season_date_chunks(2022, 2022, [5], chunk_months=12)
        assert chunks == [(date(2022, 5, 1), date(2022, 5, 31))]

    def test_december_end_uses_dec_31(self):
        chunks = _season_date_chunks(2022, 2022, [11, 12], chunk_months=12)
        assert chunks == [(date(2022, 11, 1), date(2022, 12, 31))]


# ---------------------------------------------------------------------------
# get_library_status source filter
# ---------------------------------------------------------------------------


def _fake_job(
    *,
    id: int,
    location_id: int,
    source: str,
    total_chunks: int = 1,
    completed_chunks: int = 0,
    status: str = "completed",
    error_message: str | None = None,
):
    return SimpleNamespace(
        id=id,
        location_id=location_id,
        source=source,
        total_chunks=total_chunks,
        completed_chunks=completed_chunks,
        status=status,
        error_message=error_message,
        started_at=None,
        finished_at=None,
    )


class TestGetLibraryStatusSourceFilter:
    def test_no_jobs_returns_none(self):
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = None
        assert get_library_status(db, 1) is None
        assert get_library_status(db, 1, source="gfs_hindcast") is None

    def test_source_filter_is_applied_to_query(self):
        """When a source is passed, the query must restrict by source.

        We verify this structurally: the compiled SQL for a filtered
        call must include a ``source`` predicate that the unfiltered
        variant does not.
        """
        db = MagicMock()
        captured_statements: list = []

        def capture(stmt):
            captured_statements.append(stmt)
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            return result

        db.execute.side_effect = capture

        get_library_status(db, location_id=7)  # no source filter
        get_library_status(db, location_id=7, source="era5")
        get_library_status(db, location_id=7, source="gfs_hindcast")

        assert len(captured_statements) == 3

        def compile_literals(stmt) -> str:
            return str(stmt.compile(compile_kwargs={"literal_binds": True}))

        unfiltered = compile_literals(captured_statements[0])
        era5 = compile_literals(captured_statements[1])
        gfs = compile_literals(captured_statements[2])

        # Unfiltered query must not reference the source column in the
        # WHERE clause at all.
        assert "source = " not in unfiltered
        # Filtered queries must pin the source explicitly.
        assert "source = 'era5'" in era5
        assert "source = 'gfs_hindcast'" in gfs

    def test_returns_job_payload(self):
        db = MagicMock()
        job = _fake_job(
            id=5,
            location_id=1,
            source="gfs_hindcast",
            total_chunks=45,
            completed_chunks=45,
            status="completed",
        )
        db.execute.return_value.scalar_one_or_none.return_value = job

        info = get_library_status(db, 1, source="gfs_hindcast")
        assert info is not None
        assert info["id"] == 5
        assert info["source"] == "gfs_hindcast"
        assert info["total_chunks"] == 45
        assert info["completed_chunks"] == 45
        assert info["status"] == "completed"
