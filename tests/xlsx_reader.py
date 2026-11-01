"""Independent minimal XLSX reader for tests (stdlib only; does not reuse the writer)."""

import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from xml.etree import ElementTree

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
_EPOCH = datetime(1899, 12, 30, tzinfo=UTC)


def _unescape(value: str) -> str:
    return re.sub(r"_x([0-9A-Fa-f]{4})_", lambda match: chr(int(match.group(1), 16)), value)


@dataclass
class ReadCell:
    value: Any
    cell_type: str | None
    quote_prefix: bool
    has_formula: bool


@dataclass
class ReadSheet:
    name: str
    cells: dict[str, ReadCell] = field(default_factory=dict)
    rows: list[list[Any]] = field(default_factory=list)
    autofilter: str | None = None
    frozen: bool = False


def read_xlsx(payload: bytes) -> dict[str, ReadSheet]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert archive.testzip() is None
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.get("Id"): rel.get("Target") for rel in rels}
        styles = ElementTree.fromstring(archive.read("xl/styles.xml"))
        xfs = styles.find("m:cellXfs", NS)
        assert xfs is not None
        style_info = [
            (xf.get("numFmtId"), xf.get("quotePrefix") == "1") for xf in xfs.findall("m:xf", NS)
        ]
        sheets: dict[str, ReadSheet] = {}
        sheets_element = workbook.find("m:sheets", NS)
        assert sheets_element is not None
        for sheet in sheets_element:
            name = sheet.get("name") or ""
            root = ElementTree.fromstring(archive.read("xl/" + str(targets[sheet.get(REL_NS)])))
            parsed = ReadSheet(name)
            parsed.frozen = root.find("m:sheetViews/m:sheetView/m:pane", NS) is not None
            auto = root.find("m:autoFilter", NS)
            parsed.autofilter = None if auto is None else auto.get("ref")
            for row in root.findall("m:sheetData/m:row", NS):
                values: list[Any] = []
                for cell in row.findall("m:c", NS):
                    ref = cell.get("r") or ""
                    column = ord(re.sub(r"\d", "", ref)[0]) - 65
                    while len(values) <= column:
                        values.append(None)
                    style = int(cell.get("s") or 0)
                    numfmt, quote = style_info[style]
                    cell_type = cell.get("t")
                    formula = cell.find("m:f", NS) is not None
                    if cell_type == "inlineStr":
                        text = "".join(t.text or "" for t in cell.iter(f"{{{NS['m']}}}t"))
                        value: Any = _unescape(text)
                    else:
                        raw = cell.findtext("m:v", namespaces=NS)
                        value = None if raw is None else float(raw)
                        if value is not None and numfmt == "164":
                            value = (_EPOCH + timedelta(days=value)).replace(microsecond=0)
                        elif value is not None and float(value).is_integer():
                            value = int(value)
                    values[column] = value
                    parsed.cells[ref] = ReadCell(value, cell_type, quote, formula)
                parsed.rows.append(values)
            sheets[name] = parsed
    return sheets
