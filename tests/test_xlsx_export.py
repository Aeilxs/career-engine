"""T14/T21: XLSX is a faithful, inert, reproducible projection of SQL."""

from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from helpers import fixture_bytes, posting
from xlsx_reader import read_xlsx

from career_engine.application.applications import create_application, transition_application
from career_engine.application.exports import (
    APPLICATION_COLUMNS,
    build_applications_workbook,
    write_applications_export,
)
from career_engine.application.offers import import_posting
from career_engine.config import database_path_for
from career_engine.db import connect, initialize
from career_engine.infrastructure.xlsx import Column, Sheet, build_workbook, encode_text

EXPORTED_AT = datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC)
CONTRACT_COLUMNS = [
    "application_id", "offer_id", "company", "position", "location", "URL", "imported_at",
    "technical_stage", "recruiter_status", "revision", "approved_at", "confirmed_submitted_at",
    "last_error", "next_action", "dossier_path",
]  # fmt: skip


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    initialize(database_path_for(tmp_path))
    return tmp_path


def sql_rows(data_dir: Path) -> list[Any]:
    with closing(connect(database_path_for(data_dir))) as connection:
        return connection.execute(
            "SELECT a.id, a.offer_id, r.company, r.title, r.locations_json, r.apply_url, "
            "o.created_at, a.stage, r.revision_number, a.dossier_path FROM application a "
            "JOIN offer o ON o.id = a.offer_id JOIN offer_revision r ON r.id = a.offer_revision_id "
            "ORDER BY a.created_at, a.rowid"
        ).fetchall()


def test_columns_match_the_contract_and_readback_equals_sql(data_dir: Path) -> None:
    first = import_posting(data_dir, fixture_bytes("sample-business-manager.txt"))
    second = import_posting(data_dir, posting(title=None, company=None, source_id="s/2"))
    a1 = create_application(data_dir, first.offer_id)
    create_application(data_dir, second.offer_id)
    transition_application(data_dir, a1["id"], "PREPARING", "go", 1)

    sheets = read_xlsx(build_applications_workbook(data_dir, EXPORTED_AT))
    sheet = sheets["Applications"]
    assert [c.header for c in APPLICATION_COLUMNS] == CONTRACT_COLUMNS == sheet.rows[0]
    assert sheet.autofilter == "A1:O3" and sheet.frozen
    expected = sql_rows(data_dir)
    assert len(sheet.rows) - 1 == len(expected) == 2
    for exported, record in zip(sheet.rows[1:], expected, strict=True):
        assert exported[0] == record["id"] and exported[1] == record["offer_id"]
        assert exported[2] == record["company"] and exported[3] == record["title"]
        assert exported[5] == record["apply_url"]
        assert exported[6] == datetime.fromisoformat(record["created_at"])  # typed date, not text
        assert exported[7] == record["stage"] and exported[9] == record["revision_number"]
        assert exported[14] == record["dossier_path"]
    assert sheet.rows[1][7] == "PREPARING" and sheet.rows[2][7] == "DRAFT"
    assert sheet.rows[1][4] == "Marseille, France"
    # Unknown values are empty cells, not invented text.
    assert sheet.rows[2][2] is None and sheet.rows[2][3] is None
    assert all(sheet.rows[1][i] is None for i in (8, 10, 11, 12, 13))


def test_metadata_sheet_records_schema_time_and_filters(data_dir: Path) -> None:
    meta = read_xlsx(build_applications_workbook(data_dir, EXPORTED_AT))["Metadata"]
    values = {row[0]: row[1] for row in meta.rows[1:]}
    assert values["schema_version"] == "1"
    assert values["exported_at"] == "2026-11-01T12:00:00+00:00"
    assert values["filters"] == "none" and values["row_count"] == "0"


@pytest.mark.parametrize("hostile", ["=1+1", "+SUM(A1)", "-2+3", "@SUM(A1)", "=cmd|' /C calc'!A0"])
def test_formula_like_external_text_is_inert_and_unaltered(data_dir: Path, hostile: str) -> None:
    result = import_posting(data_dir, posting(title=hostile, company=hostile))
    create_application(data_dir, result.offer_id)
    sheet = read_xlsx(build_applications_workbook(data_dir, EXPORTED_AT))["Applications"]
    for ref in ("C2", "D2"):
        cell = sheet.cells[ref]
        assert cell.value == hostile  # content identical to SQL: no apostrophe injected
        assert cell.cell_type == "inlineStr" and not cell.has_formula
        assert cell.quote_prefix  # spreadsheet apps keep it literal when edited


def test_ordinary_text_is_not_marked_with_quote_prefix(data_dir: Path) -> None:
    create_application(data_dir, import_posting(data_dir, posting()).offer_id)
    sheet = read_xlsx(build_applications_workbook(data_dir, EXPORTED_AT))["Applications"]
    assert not sheet.cells["D2"].quote_prefix and sheet.cells["D2"].value == "Backend Engineer"


def test_control_characters_and_markup_round_trip(data_dir: Path) -> None:
    title = "A\x07B\x0bC _x0041_ <b>&amp;</b> \u00e9\U0001f600 end\r"
    sheet = read_xlsx(build_workbook((Sheet("S", (Column("h"),), ((title,),)),)))["S"]
    assert sheet.rows[1] == [title]
    assert encode_text("_x0041_") == "_x005F_x0041_"


def test_export_is_reproducible_for_identical_sql_state(data_dir: Path) -> None:
    create_application(data_dir, import_posting(data_dir, posting()).offer_id)
    assert build_applications_workbook(data_dir, EXPORTED_AT) == build_applications_workbook(
        data_dir, EXPORTED_AT
    )


def test_file_export_replaces_atomically_and_leaves_no_temp_files(
    data_dir: Path, tmp_path: Path
) -> None:
    create_application(data_dir, import_posting(data_dir, posting()).offer_id)
    output = tmp_path / "out" / "applications.xlsx"
    output.parent.mkdir()
    output.write_bytes(b"previous content")
    size = write_applications_export(data_dir, output, EXPORTED_AT)
    assert output.stat().st_size == size
    assert read_xlsx(output.read_bytes())["Applications"].rows[1][3] == "Backend Engineer"
    assert [p.name for p in output.parent.iterdir()] == ["applications.xlsx"]


def test_empty_tracker_exports_header_only(data_dir: Path) -> None:
    sheet = read_xlsx(build_applications_workbook(data_dir, EXPORTED_AT))["Applications"]
    assert len(sheet.rows) == 1 and sheet.autofilter == "A1:O1"
