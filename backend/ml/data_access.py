"""Database access helpers for ML forecast engine."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ml import model_backend, storage
from ml.periods import generate_future_period_codes, next_period_code
from models.bank import BankTransaction
from models.ledger import AccountBalance, LedgerEntry, Period
from models.ml import ForecastSnapshot


async def load_training_rows(
    db: AsyncSession,
    *,
    account_set_id: str,
) -> tuple[list[BankTransaction], list[LedgerEntry]]:
    bank_result = await db.execute(
        select(BankTransaction).where(BankTransaction.account_set_id == account_set_id)
    )
    ledger_result = await db.execute(
        select(LedgerEntry).where(LedgerEntry.account_set_id == account_set_id)
    )
    return list(bank_result.scalars()), list(ledger_result.scalars())


async def count_new_transactions_since(
    db: AsyncSession,
    *,
    account_set_id: str,
    since: datetime | None,
) -> int:
    query = select(func.count()).select_from(BankTransaction).where(
        BankTransaction.account_set_id == account_set_id
    )
    if since is not None:
        query = query.where(BankTransaction.created_at > since)
    result = await db.execute(query)
    return int(result.scalar_one())


async def resolve_forecast_start_period(
    db: AsyncSession,
    *,
    account_set_id: str,
) -> str:
    closed = await db.execute(
        select(Period)
        .where(Period.account_set_id == account_set_id, Period.is_closed.is_(True))
        .order_by(Period.period_code.desc())
        .limit(1)
    )
    last_closed = closed.scalar_one_or_none()
    if last_closed is not None:
        return next_period_code(last_closed.period_code)

    latest_bank = await db.execute(
        select(BankTransaction.date)
        .where(BankTransaction.account_set_id == account_set_id)
        .order_by(BankTransaction.date.desc())
        .limit(1)
    )
    latest_date = latest_bank.scalar_one_or_none()
    if latest_date is not None:
        return f"{latest_date.year}{latest_date.month:02d}"
    return datetime.now(timezone.utc).strftime("%Y%m")


async def save_forecast_snapshot(
    db: AsyncSession,
    *,
    account_set_id: str,
    model_id: str,
    history_frame: pd.DataFrame,
    horizon_months: int = 3,
) -> None:
    if history_frame.empty:
        return

    start_period = next_period_code(str(history_frame["period_code"].iloc[-1]))
    artifact = model_backend._train_stub(history_frame)
    predictions = model_backend.predict_horizon(artifact, history_frame, horizon_months)
    period_codes = generate_future_period_codes(start_period, horizon_months)
    snapshot_period = str(history_frame["period_code"].iloc[-1])

    for period_code, pred in zip(period_codes, predictions, strict=True):
        db.add(
            ForecastSnapshot(
                id=uuid.uuid4(),
                account_set_id=uuid.UUID(account_set_id),
                result_id=None,
                snapshot_at=datetime.now(timezone.utc),
                snapshot_period=snapshot_period,
                target_period=period_code,
                predicted_net_cash_flow=float(pred["predicted_net_cash_flow"]),
                confidence_lower=float(pred["confidence_lower"]),
                confidence_upper=float(pred["confidence_upper"]),
                notes=f"model_id={model_id}",
            )
        )

    storage.save_snapshot_json(
        account_set_id,
        snapshot_period,
        {
            "snapshot_period": snapshot_period,
            "model_id": model_id,
            "periods": [
                {"target_period": code, **pred}
                for code, pred in zip(period_codes, predictions, strict=True)
            ],
        },
    )
    await db.flush()


async def load_account_balances_for_period(
    db: AsyncSession,
    *,
    account_set_id: str,
    period_code: str,
) -> list[AccountBalance]:
    result = await db.execute(
        select(AccountBalance).where(
            AccountBalance.account_set_id == account_set_id,
            AccountBalance.period_code == period_code,
        )
    )
    return list(result.scalars())
