"""
Parsers for Chinese bank, WeChat Pay, and Alipay transaction exports.

Extracts: date, amount, counterparty, description, reference_number, direction.
"""

from __future__ import annotations

import csv
import io
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from smart_import.mappings import DIRECTION_INFLOW, DIRECTION_OUTFLOW

FORMAT_AUTO = "auto"
FORMAT_BANK_CSV = "bank_csv"
FORMAT_WECHAT_CSV = "wechat_csv"
FORMAT_ALIPAY_CSV = "alipay_csv"
FORMAT_BANK_XLS = "bank_xls"

CANONICAL_EXPORT_HEADERS = [
    "txn_date",
    "amount",
    "direction",
    "counterparty",
    "description",
    "reference_number",
]


@dataclass
class ParsedTransaction:
    txn_date: date
    amount: float
    direction: str
    counterparty: str
    description: str
    reference_number: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["txn_date"] = self.txn_date.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParsedTransaction:
        txn_date = data["txn_date"]
        if isinstance(txn_date, str):
            txn_date = date.fromisoformat(txn_date[:10])
        return cls(
            txn_date=txn_date,
            amount=float(data["amount"]),
            direction=str(data["direction"]),
            counterparty=str(data.get("counterparty", "")),
            description=str(data.get("description", "")),
            reference_number=str(data.get("reference_number", "")),
        )


class ParseError(ValueError):
    """Raised when a file cannot be parsed."""


def dedup_key(
    account_set_id: str,
    txn_date: date,
    amount: float,
    reference_number: str,
) -> tuple[str, str, str, str]:
    """Deduplication key (Req 19.6)."""
    normalized_amount = f"{Decimal(str(amount)).quantize(Decimal('0.0001'))}"
    return (
        account_set_id,
        txn_date.isoformat(),
        normalized_amount,
        reference_number or "",
    )


def detect_format(file_name: str, headers: list[str]) -> str:
    """Infer file format from filename and header row."""
    joined = ",".join(headers)
    lowered = joined.lower()
    name_lower = file_name.lower()

    if "微信" in joined or "wechat" in name_lower or "微信支付" in joined:
        return FORMAT_WECHAT_CSV
    if "支付宝" in joined or "alipay" in name_lower:
        return FORMAT_ALIPAY_CSV
    if name_lower.endswith((".xls", ".xlsx")):
        return FORMAT_BANK_XLS
    if any(k in joined for k in ("交易日期", "记账日期", "发生额", "收入", "支出")):
        return FORMAT_BANK_CSV
    raise ParseError(f"Unable to detect import format from headers: {headers[:8]}")


def parse_file_content(
    *,
    file_name: str,
    content: bytes,
    file_format: str = FORMAT_AUTO,
) -> list[ParsedTransaction]:
    """Parse uploaded file bytes into structured transactions."""
    if file_format == FORMAT_AUTO:
        if file_name.lower().endswith((".xls", ".xlsx")):
            return _parse_bank_xls(content)
        text = _decode_text(content)
        headers, rows = _read_csv_rows(text)
        detected = detect_format(file_name, headers)
        return _parse_rows(detected, headers, rows)

    if file_format == FORMAT_BANK_XLS:
        return _parse_bank_xls(content)

    text = _decode_text(content)
    headers, rows = _read_csv_rows(text)
    return _parse_rows(file_format, headers, rows)


def export_canonical_csv(transactions: list[ParsedTransaction]) -> str:
    """Serialize transactions to canonical CSV for round-trip parsing."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CANONICAL_EXPORT_HEADERS)
    writer.writeheader()
    for txn in transactions:
        writer.writerow(
            {
                "txn_date": txn.txn_date.isoformat(),
                "amount": f"{txn.amount:.4f}",
                "direction": txn.direction,
                "counterparty": txn.counterparty,
                "description": txn.description,
                "reference_number": txn.reference_number,
            }
        )
    return buf.getvalue()


def parse_canonical_csv(content: str | bytes) -> list[ParsedTransaction]:
    """Re-parse canonical CSV export (round-trip)."""
    if isinstance(content, bytes):
        content = _decode_text(content)
    reader = csv.DictReader(io.StringIO(content))
    transactions: list[ParsedTransaction] = []
    for row in reader:
        transactions.append(ParsedTransaction.from_dict(row))
    return transactions


def _parse_rows(
    file_format: str,
    headers: list[str],
    rows: list[list[str]],
) -> list[ParsedTransaction]:
    if file_format == FORMAT_WECHAT_CSV:
        return _parse_wechat(headers, rows)
    if file_format == FORMAT_ALIPAY_CSV:
        return _parse_alipay(headers, rows)
    if file_format in (FORMAT_BANK_CSV, FORMAT_BANK_XLS):
        return _parse_bank(headers, rows)
    raise ParseError(f"Unsupported format: {file_format}")


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "gbk", "gb18030", "utf-8"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ParseError("Unable to decode file content.")


def _read_csv_rows(text: str) -> tuple[list[str], list[list[str]]]:
    sample = text[:4096]
    delimiter = "\t" if sample.count("\t") > sample.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [list(row) for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        raise ParseError("File contains no data rows.")
    headers = [_normalize_header(cell) for cell in rows[0]]
    return headers, rows[1:]


def _normalize_header(value: str) -> str:
    return value.strip().replace("\ufeff", "")


def _header_index(headers: list[str], *aliases: str) -> int | None:
    normalized_aliases = {a.lower() for a in aliases}
    for idx, header in enumerate(headers):
        if header.lower() in normalized_aliases or header in aliases:
            return idx
    return None


def _parse_date(value: str) -> date:
    value = value.strip()
    if not value:
        raise ParseError("Missing transaction date.")
    for fmt in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
        "%Y%m%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
    ):
        try:
            return datetime.strptime(value[:19], fmt).date()
        except ValueError:
            continue
    raise ParseError(f"Unrecognized date format: {value!r}")


def _parse_amount(value: str) -> Decimal:
    cleaned = (
        value.strip()
        .replace(",", "")
        .replace("¥", "")
        .replace("￥", "")
        .replace("元", "")
    )
    if not cleaned:
        return Decimal("0")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ParseError(f"Invalid amount: {value!r}") from exc


def _parse_bank(headers: list[str], rows: list[list[str]]) -> list[ParsedTransaction]:
    date_idx = _header_index(headers, "交易日期", "记账日期", "日期", "date")
    amount_idx = _header_index(headers, "交易金额", "发生额", "金额", "amount")
    income_idx = _header_index(headers, "收入", "贷方金额", "贷方发生额")
    expense_idx = _header_index(headers, "支出", "借方金额", "借方发生额")
    counterparty_idx = _header_index(
        headers, "对方户名", "对方账号名称", "对方名称", "交易对方", "counterparty"
    )
    desc_idx = _header_index(headers, "摘要", "用途", "备注", "description", "商品")
    ref_idx = _header_index(
        headers, "凭证号", "流水号", "交易流水号", "交易单号", "reference"
    )

    if date_idx is None:
        raise ParseError("Bank CSV missing date column.")

    transactions: list[ParsedTransaction] = []
    for row in rows:
        if date_idx >= len(row):
            continue
        txn_date = _parse_date(row[date_idx])
        direction = DIRECTION_INFLOW
        amount = Decimal("0")

        if income_idx is not None and expense_idx is not None:
            income = _parse_amount(row[income_idx]) if income_idx < len(row) else Decimal("0")
            expense = _parse_amount(row[expense_idx]) if expense_idx < len(row) else Decimal("0")
            if income > 0 and expense == 0:
                amount = income
                direction = DIRECTION_INFLOW
            elif expense > 0 and income == 0:
                amount = expense
                direction = DIRECTION_OUTFLOW
            elif income > 0:
                amount = income
                direction = DIRECTION_INFLOW
            else:
                continue
        elif amount_idx is not None and amount_idx < len(row):
            raw = _parse_amount(row[amount_idx])
            amount = abs(raw)
            direction = DIRECTION_INFLOW if raw >= 0 else DIRECTION_OUTFLOW
        else:
            continue

        if amount <= 0:
            continue

        counterparty = row[counterparty_idx].strip() if counterparty_idx is not None and counterparty_idx < len(row) else ""
        description = row[desc_idx].strip() if desc_idx is not None and desc_idx < len(row) else ""
        reference = row[ref_idx].strip() if ref_idx is not None and ref_idx < len(row) else ""

        transactions.append(
            ParsedTransaction(
                txn_date=txn_date,
                amount=float(amount),
                direction=direction,
                counterparty=counterparty,
                description=description,
                reference_number=reference,
            )
        )
    return transactions


def _parse_wechat(headers: list[str], rows: list[list[str]]) -> list[ParsedTransaction]:
    date_idx = _header_index(headers, "交易时间", "记账时间")
    type_idx = _header_index(headers, "交易类型")
    counterparty_idx = _header_index(headers, "交易对方", "商户名称")
    product_idx = _header_index(headers, "商品", "商品名称")
    direction_idx = _header_index(headers, "收/支", "收支")
    amount_idx = _header_index(headers, "金额(元)", "金额")
    ref_idx = _header_index(headers, "交易单号", "商户单号")
    note_idx = _header_index(headers, "备注")

    if date_idx is None or amount_idx is None:
        raise ParseError("WeChat CSV missing required columns.")

    transactions: list[ParsedTransaction] = []
    for row in rows:
        if date_idx >= len(row):
            continue
        amount = _parse_amount(row[amount_idx])
        if amount <= 0:
            continue
        direction_raw = row[direction_idx].strip() if direction_idx is not None and direction_idx < len(row) else ""
        if "支" in direction_raw:
            direction = DIRECTION_OUTFLOW
        elif "收" in direction_raw:
            direction = DIRECTION_INFLOW
        else:
            direction = DIRECTION_OUTFLOW if amount < 0 else DIRECTION_INFLOW
        amount = abs(amount)

        counterparty = row[counterparty_idx].strip() if counterparty_idx is not None and counterparty_idx < len(row) else ""
        product = row[product_idx].strip() if product_idx is not None and product_idx < len(row) else ""
        txn_type = row[type_idx].strip() if type_idx is not None and type_idx < len(row) else ""
        note = row[note_idx].strip() if note_idx is not None and note_idx < len(row) else ""
        description = " / ".join(part for part in (txn_type, product, note) if part)
        reference = row[ref_idx].strip() if ref_idx is not None and ref_idx < len(row) else ""

        transactions.append(
            ParsedTransaction(
                txn_date=_parse_date(row[date_idx]),
                amount=float(amount),
                direction=direction,
                counterparty=counterparty,
                description=description,
                reference_number=reference,
            )
        )
    return transactions


def _parse_alipay(headers: list[str], rows: list[list[str]]) -> list[ParsedTransaction]:
    date_idx = _header_index(headers, "交易时间", "交易创建时间")
    category_idx = _header_index(headers, "交易分类", "类型")
    counterparty_idx = _header_index(headers, "交易对方", "对方名称")
    product_idx = _header_index(headers, "商品说明", "商品名称")
    direction_idx = _header_index(headers, "收/支")
    amount_idx = _header_index(headers, "金额", "金额（元）", "金额(元)")
    ref_idx = _header_index(headers, "交易订单号", "商家订单号")
    note_idx = _header_index(headers, "备注")

    if date_idx is None or amount_idx is None:
        raise ParseError("Alipay CSV missing required columns.")

    transactions: list[ParsedTransaction] = []
    for row in rows:
        if date_idx >= len(row):
            continue
        amount = abs(_parse_amount(row[amount_idx]))
        if amount <= 0:
            continue
        direction_raw = row[direction_idx].strip() if direction_idx is not None and direction_idx < len(row) else ""
        if "支出" in direction_raw or "支" in direction_raw:
            direction = DIRECTION_OUTFLOW
        elif "收入" in direction_raw or "收" in direction_raw:
            direction = DIRECTION_INFLOW
        else:
            direction = DIRECTION_INFLOW

        counterparty = row[counterparty_idx].strip() if counterparty_idx is not None and counterparty_idx < len(row) else ""
        category = row[category_idx].strip() if category_idx is not None and category_idx < len(row) else ""
        product = row[product_idx].strip() if product_idx is not None and product_idx < len(row) else ""
        note = row[note_idx].strip() if note_idx is not None and note_idx < len(row) else ""
        description = " / ".join(part for part in (category, product, note) if part)
        reference = row[ref_idx].strip() if ref_idx is not None and ref_idx < len(row) else ""

        transactions.append(
            ParsedTransaction(
                txn_date=_parse_date(row[date_idx]),
                amount=float(amount),
                direction=direction,
                counterparty=counterparty,
                description=description,
                reference_number=reference,
            )
        )
    return transactions


def _parse_bank_xls(content: bytes) -> list[ParsedTransaction]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise ParseError("openpyxl is required for Excel imports.") from exc

    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    sheet = wb.active
    rows_iter = sheet.iter_rows(values_only=True)
    try:
        header_row = next(rows_iter)
    except StopIteration as exc:
        raise ParseError("Excel file is empty.") from exc

    headers = [_normalize_header(str(cell)) if cell is not None else "" for cell in header_row]
    data_rows = [
        [str(cell) if cell is not None else "" for cell in row]
        for row in rows_iter
        if any(cell is not None and str(cell).strip() for cell in row)
    ]
    wb.close()
    return _parse_bank(headers, data_rows)


def transactions_equivalent(
    left: list[ParsedTransaction],
    right: list[ParsedTransaction],
) -> bool:
    """Compare two parsed transaction lists for round-trip equivalence."""
    if len(left) != len(right):
        return False

    def sort_key(txn: ParsedTransaction) -> tuple:
        return (
            txn.txn_date,
            txn.reference_number,
            txn.amount,
            txn.direction,
            txn.counterparty,
            txn.description,
        )

    for a, b in zip(sorted(left, key=sort_key), sorted(right, key=sort_key)):
        if (
            a.txn_date != b.txn_date
            or Decimal(str(a.amount)) != Decimal(str(b.amount))
            or a.direction != b.direction
            or a.counterparty != b.counterparty
            or a.description != b.description
            or a.reference_number != b.reference_number
        ):
            return False
    return True
