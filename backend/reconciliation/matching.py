"""
Transaction matching — exact and fuzzy (Levenshtein) algorithms.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

DEFAULT_FUZZY_THRESHOLD = 3


@dataclass
class InternalCandidate:
    entry_id: str
    date: date
    amount: float
    description: str

    @property
    def signed_amount(self) -> float:
        return self.amount


@dataclass
class BankCandidate:
    transaction_id: str
    date: date
    amount: float
    direction: str
    description: str

    @property
    def signed_amount(self) -> float:
        return self.amount if self.direction == "Inflow" else -self.amount


@dataclass
class MatchProposal:
    bank_transaction_id: str
    voucher_entry_id: str
    match_type: str  # Exact, Fuzzy, Manual


def levenshtein_distance(a: str, b: str) -> int:
    """Classic Levenshtein edit distance."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def _normalize_description(text: str) -> str:
    return " ".join(text.lower().split())


def find_exact_matches(
    bank_rows: list[BankCandidate],
    internal_rows: list[InternalCandidate],
    *,
    already_matched_bank: set[str] | None = None,
    already_matched_internal: set[str] | None = None,
) -> list[MatchProposal]:
    """Match on same date, absolute amount, and identical description (Req 5.2)."""
    matched_bank = already_matched_bank or set()
    matched_internal = already_matched_internal or set()
    proposals: list[MatchProposal] = []

    for bank in bank_rows:
        if bank.transaction_id in matched_bank:
            continue
        bank_desc = _normalize_description(bank.description)
        for internal in internal_rows:
            if internal.entry_id in matched_internal:
                continue
            if internal.date != bank.date:
                continue
            if round(abs(internal.signed_amount), 4) != round(abs(bank.signed_amount), 4):
                continue
            if _normalize_description(internal.description) != bank_desc:
                continue
            proposals.append(
                MatchProposal(
                    bank_transaction_id=bank.transaction_id,
                    voucher_entry_id=internal.entry_id,
                    match_type="Exact",
                )
            )
            matched_bank.add(bank.transaction_id)
            matched_internal.add(internal.entry_id)
            break

    return proposals


def find_fuzzy_matches(
    bank_rows: list[BankCandidate],
    internal_rows: list[InternalCandidate],
    *,
    threshold: int = DEFAULT_FUZZY_THRESHOLD,
    already_matched_bank: set[str] | None = None,
    already_matched_internal: set[str] | None = None,
) -> list[MatchProposal]:
    """Fuzzy match on description when date+amount align (Req 5.2)."""
    matched_bank = already_matched_bank or set()
    matched_internal = already_matched_internal or set()
    proposals: list[MatchProposal] = []

    available_internal = [
        row for row in internal_rows if row.entry_id not in matched_internal
    ]

    for bank in bank_rows:
        if bank.transaction_id in matched_bank:
            continue
        best: InternalCandidate | None = None
        best_distance = threshold + 1

        for internal in available_internal:
            if internal.entry_id in matched_internal:
                continue
            if internal.date != bank.date:
                continue
            if round(abs(internal.signed_amount), 4) != round(abs(bank.signed_amount), 4):
                continue
            internal_desc = _normalize_description(internal.description)
            bank_desc = _normalize_description(bank.description)
            if internal_desc == bank_desc:
                continue
            distance = levenshtein_distance(bank_desc, internal_desc)
            if distance <= threshold and distance < best_distance:
                best = internal
                best_distance = distance

        if best is None:
            continue

        proposals.append(
            MatchProposal(
                bank_transaction_id=bank.transaction_id,
                voucher_entry_id=best.entry_id,
                match_type="Fuzzy",
            )
        )
        matched_bank.add(bank.transaction_id)
        matched_internal.add(best.entry_id)
        available_internal = [r for r in available_internal if r.entry_id != best.entry_id]

    return proposals


def auto_match_candidates(
    bank_rows: list[BankCandidate],
    internal_rows: list[InternalCandidate],
    *,
    fuzzy_threshold: int = DEFAULT_FUZZY_THRESHOLD,
) -> list[MatchProposal]:
    exact = find_exact_matches(bank_rows, internal_rows)
    matched_bank = {m.bank_transaction_id for m in exact}
    matched_internal = {m.voucher_entry_id for m in exact}
    fuzzy = find_fuzzy_matches(
        bank_rows,
        internal_rows,
        threshold=fuzzy_threshold,
        already_matched_bank=matched_bank,
        already_matched_internal=matched_internal,
    )
    return exact + fuzzy


def signed_voucher_amount(debit: float, credit: float) -> float:
    """Bank account lines: debit inflow (+), credit outflow (-)."""
    if debit > 0:
        return float(debit)
    if credit > 0:
        return -float(credit)
    return 0.0


def compute_difference(
    unmatched_bank: list[dict[str, Any]],
    unmatched_internal: list[dict[str, Any]],
) -> float:
    """Sum of unreconciled amounts (Req 5.5)."""
    bank_total = sum(float(row.get("signed_amount", 0)) for row in unmatched_bank)
    internal_total = sum(float(row.get("signed_amount", 0)) for row in unmatched_internal)
    return round(bank_total - internal_total, 4)
