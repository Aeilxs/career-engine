"""Dependency-free XLSX writer (OOXML parts assembled with zipfile).

External text is always written as a string cell (`inlineStr`); a value that starts with a
formula/control prefix additionally gets the `quotePrefix` style so spreadsheet apps keep it
literal when edited. Cell content is never altered. Output is byte-reproducible for the same
input (fixed zip timestamps and member order).
"""

import io
import re
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from xml.sax.saxutils import escape

CellValue = str | int | datetime | None

_EPOCH = datetime(1899, 12, 30)
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")
_LITERAL_ESCAPE = re.compile(r"_(?=x[0-9A-Fa-f]{4}_)")
_UNSAFE_XML_CHARS = re.compile("[\x00-\x08\x0b\x0c\x0d\x0e-\x1f\ufffe\uffff]")
_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_STYLE_DEFAULT, _STYLE_HEADER, _STYLE_DATETIME, _STYLE_TEXT_PREFIX = 0, 1, 2, 3


@dataclass(frozen=True)
class Column:
    header: str
    width: float = 18.0


@dataclass(frozen=True)
class Sheet:
    name: str
    columns: tuple[Column, ...]
    rows: tuple[tuple[CellValue, ...], ...]
    autofilter: bool = False


def column_letter(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def encode_text(value: str) -> str:
    """XML-safe text using the OOXML `_xHHHH_` escape for characters XML 1.0 cannot carry."""
    value = _LITERAL_ESCAPE.sub("_x005F_", value)
    value = _UNSAFE_XML_CHARS.sub(lambda match: f"_x{ord(match.group()):04X}_", value)
    return escape(value)


def excel_serial(moment: datetime) -> str:
    naive = moment.astimezone(UTC).replace(tzinfo=None) if moment.tzinfo else moment
    delta = naive - _EPOCH
    return repr(delta.days + delta.seconds / 86400)


def _cell(reference: str, value: CellValue) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return f'<c r="{reference}" s="{_STYLE_DATETIME}"><v>{excel_serial(value)}</v></c>'
    if isinstance(value, int) and not isinstance(value, bool):
        return f'<c r="{reference}"><v>{value}</v></c>'
    text = str(value)
    style = _STYLE_TEXT_PREFIX if text.startswith(_DANGEROUS_PREFIXES) else _STYLE_DEFAULT
    return (
        f'<c r="{reference}" s="{style}" t="inlineStr">'
        f'<is><t xml:space="preserve">{encode_text(text)}</t></is></c>'
    )


def _sheet_xml(sheet: Sheet) -> str:
    last_column = column_letter(len(sheet.columns) - 1)
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<worksheet xmlns="{_NS}">',
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        "</sheetView></sheetViews>",
        "<cols>",
    ]
    for position, column in enumerate(sheet.columns, start=1):
        parts.append(
            f'<col min="{position}" max="{position}" width="{column.width}" customWidth="1"/>'
        )
    parts.append("</cols><sheetData>")
    header_cells = "".join(
        f'<c r="{column_letter(i)}1" s="{_STYLE_HEADER}" t="inlineStr">'
        f'<is><t xml:space="preserve">{encode_text(column.header)}</t></is></c>'
        for i, column in enumerate(sheet.columns)
    )
    parts.append(f'<row r="1">{header_cells}</row>')
    for row_number, row in enumerate(sheet.rows, start=2):
        cells = "".join(
            _cell(f"{column_letter(i)}{row_number}", value) for i, value in enumerate(row)
        )
        parts.append(f'<row r="{row_number}">{cells}</row>')
    parts.append("</sheetData>")
    if sheet.autofilter:
        parts.append(f'<autoFilter ref="A1:{last_column}{len(sheet.rows) + 1}"/>')
    parts.append("</worksheet>")
    return "".join(parts)


_STYLES_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<styleSheet xmlns="{_NS}">'
    '<numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy\\-mm\\-dd\\ hh:mm:ss"/></numFmts>'
    '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
    '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
    '<fills count="2"><fill><patternFill patternType="none"/></fill>'
    '<fill><patternFill patternType="gray125"/></fill></fills>'
    '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="4">'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
    '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
    '<xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0" '
    'applyNumberFormat="1" quotePrefix="1"/>'
    "</cellXfs>"
    '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
    "</styleSheet>"
)


def build_workbook(sheets: tuple[Sheet, ...]) -> bytes:
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        + "".join(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        + "</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
    )
    defined_names = "".join(
        f'<definedName name="_xlnm._FilterDatabase" localSheetId="{i}" hidden="1">'
        f"'{encode_text(sheet.name)}'!$A$1:${column_letter(len(sheet.columns) - 1)}"
        f"${len(sheet.rows) + 1}</definedName>"
        for i, sheet in enumerate(sheets)
        if sheet.autofilter
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{_NS}" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        + "".join(
            f'<sheet name="{encode_text(sheet.name)}" sheetId="{i}" r:id="rId{i}"/>'
            for i, sheet in enumerate(sheets, start=1)
        )
        + "</sheets>"
        + (f"<definedNames>{defined_names}</definedNames>" if defined_names else "")
        + "</workbook>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/'
            f'2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        + f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'
    )
    members: list[tuple[str, str]] = [
        ("[Content_Types].xml", content_types),
        ("_rels/.rels", root_rels),
        ("xl/workbook.xml", workbook),
        ("xl/_rels/workbook.xml.rels", workbook_rels),
        ("xl/styles.xml", _STYLES_XML),
    ]
    members += [
        (f"xl/worksheets/sheet{i}.xml", _sheet_xml(sheet))
        for i, sheet in enumerate(sheets, start=1)
    ]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in members:
            info = zipfile.ZipInfo(name, date_time=_FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, content.encode("utf-8"))
    return buffer.getvalue()
