"""Persistent, fail-closed loss lock for PHOENIX GOLD.

This module is deliberately independent of MetaTrader5 and cannot place orders.
A future read-only broker adapter must reconcile each fully closed position,
calculate net P&L in JPY after fees, then call record_closed_trade exactly once.
Single-process use only; do not run multiple writers against one state file.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any


RESET_CONFIRMATION = "RESET_AFTER_REVIEW"


class SafetyStateError(RuntimeError):
    """Raised when the persisted safety state cannot be trusted."""


@dataclass(frozen=True)
class LossGuardConfig:
    max_consecutive_losses: int = 2
    max_daily_loss_jpy: int = 1_500

    def __post_init__(self) -> None:
        if self.max_consecutive_losses < 1:
            raise ValueError("max_consecutive_losses must be >= 1")
        if self.max_daily_loss_jpy < 1:
            raise ValueError("max_daily_loss_jpy must be >= 1")


@dataclass(frozen=True)
class GuardStatus:
    allowed: bool
    locked: bool
    consecutive_losses: int
    daily_net_pnl_jpy: int
    reason: str


class PersistentLossGuard:
    """Persist loss streak, daily P&L and lock state; fail closed on bad state."""

    def __init__(self, state_path: str | Path, config: LossGuardConfig | None = None):
        self.state_path = Path(state_path)
        self.config = config or LossGuardConfig()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load_or_initialize()

    def _blank_state(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "locked": False,
            "lock_reason": "",
            "consecutive_losses": 0,
            "daily_net_pnl_jpy": 0,
            "trading_day": "",
            "processed_trade_ids": [],
            "last_reset_reason": "",
        }

    def _load_or_initialize(self) -> dict[str, Any]:
        if not self.state_path.exists():
            state = self._blank_state()
            self._save(state)
            return state
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            required = set(self._blank_state())
            if not isinstance(state, dict) or not required.issubset(state):
                raise ValueError("missing required state fields")
            if state["schema_version"] != 1:
                raise ValueError("unsupported state schema")
            if not isinstance(state["locked"], bool):
                raise ValueError("invalid locked field")
            for key in ("consecutive_losses", "daily_net_pnl_jpy"):
                if isinstance(state[key], bool) or not isinstance(state[key], int):
                    raise ValueError(f"invalid {key}")
            if state["consecutive_losses"] < 0 or not isinstance(state["processed_trade_ids"], list):
                raise ValueError("invalid loss state")
            if not all(isinstance(item, str) and item for item in state["processed_trade_ids"]):
                raise ValueError("invalid processed trade ids")
            return state
        except Exception as exc:
            # Do not silently overwrite a corrupted lock file with an unlocked state.
            raise SafetyStateError(
                f"Persisted loss-guard state is invalid; entries must remain disabled: {exc}"
            ) from exc

    def _save(self, state: dict[str, Any]) -> None:
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.state_path.name}.", suffix=".tmp", dir=str(self.state_path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.state_path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def status(self) -> GuardStatus:
        if self._state["locked"]:
            return GuardStatus(
                False, True, self._state["consecutive_losses"],
                self._state["daily_net_pnl_jpy"],
                self._state["lock_reason"] or "Manual safety lock is active.",
            )
        if self._state["daily_net_pnl_jpy"] <= -self.config.max_daily_loss_jpy:
            return GuardStatus(
                False, True, self._state["consecutive_losses"],
                self._state["daily_net_pnl_jpy"],
                "Daily realized-loss limit reached; manual review/reset required.",
            )
        return GuardStatus(
            True, False, self._state["consecutive_losses"],
            self._state["daily_net_pnl_jpy"], "Safety gate clear; this is not trade approval."
        )

    def record_closed_trade(self, trade_id: str, net_pnl_jpy: int, trading_day: str) -> GuardStatus:
        """Record one fully closed position's net P&L once; duplicate IDs are ignored."""
        if not isinstance(trade_id, str) or not trade_id.strip():
            raise ValueError("trade_id is required")
        if isinstance(net_pnl_jpy, bool) or not isinstance(net_pnl_jpy, int):
            raise ValueError("net_pnl_jpy must be an integer JPY amount")
        try:
            date.fromisoformat(trading_day)
        except (TypeError, ValueError) as exc:
            raise ValueError("trading_day must be YYYY-MM-DD") from exc

        if trade_id in self._state["processed_trade_ids"]:
            return self.status()
        if self._state["locked"]:
            return self.status()

        next_state = dict(self._state)
        next_state["processed_trade_ids"] = [*self._state["processed_trade_ids"], trade_id]
        if next_state["trading_day"] != trading_day:
            next_state["trading_day"] = trading_day
            next_state["daily_net_pnl_jpy"] = 0

        next_state["daily_net_pnl_jpy"] += net_pnl_jpy
        if net_pnl_jpy < 0:
            next_state["consecutive_losses"] += 1
        elif net_pnl_jpy > 0:
            next_state["consecutive_losses"] = 0

        if next_state["consecutive_losses"] >= self.config.max_consecutive_losses:
            next_state["locked"] = True
            next_state["lock_reason"] = "Consecutive closed-position loss limit reached."
        elif next_state["daily_net_pnl_jpy"] <= -self.config.max_daily_loss_jpy:
            next_state["locked"] = True
            next_state["lock_reason"] = "Daily realized-loss limit reached."

        self._save(next_state)
        self._state = next_state
        return self.status()

    def reset_after_review(self, confirmation: str, review_reason: str) -> GuardStatus:
        """Explicit operator action only; preserve processed IDs to prevent replay."""
        if confirmation != RESET_CONFIRMATION:
            raise PermissionError("Exact reset confirmation phrase is required.")
        if not isinstance(review_reason, str) or len(review_reason.strip()) < 12:
            raise ValueError("A review reason of at least 12 characters is required.")
        next_state = dict(self._state)
        next_state["locked"] = False
        next_state["lock_reason"] = ""
        next_state["consecutive_losses"] = 0
        next_state["daily_net_pnl_jpy"] = 0
        next_state["last_reset_reason"] = review_reason.strip()
        self._save(next_state)
        self._state = next_state
        return self.status()
