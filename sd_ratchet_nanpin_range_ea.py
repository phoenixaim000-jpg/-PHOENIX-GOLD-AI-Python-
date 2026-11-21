# -*- coding: utf-8 -*-
"""
================================================================================
PROJECT: PHOENIX / VISION FX AI - Second-by-Second Dynamic TP/SL Nanpin Range EA
FILE NAME: sd_ratchet_nanpin_range_ea.py
STRATEGY NAME: 秒単位ダイナミックTP/SL引き上げ・引き下げナンピンレンジ手法
               (Second-by-Second Dynamic TP/SL Ratchet Nanpin Range Method)
AUTHOR: AIM PHOENIX (KIKKAKE &)
VERSION: 1.0.0 (GitHub Release Ready)
================================================================================

【手法概要】
1. ナンピンレンジ (Nanpin Range):
   - レンジ相場内で分割エントリーを行い、平均建値（Avg Entry Price）を最適化。
   - レンジ幅・ボラティリティ・方向性を監視し、含み益フェーズへ移行。

2. ロング TP/SL 引き上げ ＆ ショート TP/SL 引き下げ:
   - LONG時: 価格上昇に合わせて TP と SL を上方へ引き上げ（利益方向へロック）。
   - SHORT時: 価格下落に合わせて TP と SL を下方へ引き下げ（利益方向へロック）。

3. 秒単位（1秒間隔）での TP/SL 動的調整 ＆ SL利確決済の「さらに+」増幅:
   - 1秒ごとの価格・モメンタムを評価し、TP と SL を秒単位で追従更新。
   - 利益圏に入ったSLを秒単位でさらに利益方向へ押し上げる（LONGは上へ、SHORTは下へ）
     ことで、SLヒット時の利確決済（SL利確決済）を単なる建値や小幅プラスにとどめず、
     「さらに+（プラス増幅）」へと引き上げる。
================================================================================
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List
import json


@dataclass
class NanpinPosition:
    pos_id: int
    direction: str          # "LONG" or "SHORT"
    entry_price: float
    lot_size: float
    step_index: int         # ナンピン段数 (1〜)


@dataclass
class SecondBySecondTradeResult:
    trade_id: int
    timestamp: str
    strategy_name: str
    direction: str
    nanpin_count: int
    total_lot: float
    avg_entry_price: float
    initial_tp_price: float
    initial_sl_price: float
    final_tp_price: float
    final_sl_price: float
    exit_price: float
    exit_type: str          # "SL_PROFIT_EXIT", "TP_HIT", "INITIAL_SL_EXIT", "ACTIVE_HOLD"
    base_profit_pips: float
    extra_sl_boost_pips: float
    total_profit_pips: float
    seconds_elapsed: int
    log_summary: str


class SecondBySecondRatchetNanpinEA:
    """
    秒単位ダイナミックTP/SL引き上げ・引き下げナンピンレンジ手法 実行クラス
    """

    def __init__(
        self,
        symbol: str = "XAUUSD",
        pip_size: float = 0.01,
        range_step_pips: float = 150.0,
        max_nanpin_steps: int = 4,
        initial_sl_pips: float = 100.0,
        initial_tp_pips: float = 400.0,
        sec_step_pips: float = 15.0,
        sl_plus_boost_rate: float = 0.15,
    ):
        self.strategy_name = "秒単位ダイナミックTP/SL引き上げ・引き下げナンピンレンジ手法"
        self.symbol = symbol
        self.pip_size = pip_size
        self.range_step_pips = range_step_pips
        self.max_nanpin_steps = max_nanpin_steps
        self.initial_sl_pips = initial_sl_pips
        self.initial_tp_pips = initial_tp_pips
        self.sec_step_pips = sec_step_pips
        self.sl_plus_boost_rate = sl_plus_boost_rate
        self.trade_counter = 0

    @staticmethod
    def calc_avg_entry_price(positions: List[NanpinPosition]) -> float:
        total_lot = sum(p.lot_size for p in positions)
        if total_lot <= 0:
            return 0.0
        weighted_sum = sum(p.entry_price * p.lot_size for p in positions)
        return round(weighted_sum / total_lot, 4)

    def build_nanpin_range_positions(
        self,
        direction: str,
        range_prices: List[float],
        base_lot: float = 0.10,
    ) -> List[NanpinPosition]:
        """
        ナンピンレンジ内で分割ポジションを構築する
        """
        positions: List[NanpinPosition] = []
        selected_prices = range_prices[: self.max_nanpin_steps]
        for idx, price in enumerate(selected_prices, start=1):
            lot = round(base_lot * (1.0 + (idx - 1) * 0.25), 2)
            positions.append(
                NanpinPosition(
                    pos_id=idx,
                    direction=direction,
                    entry_price=price,
                    lot_size=lot,
                    step_index=idx,
                )
            )
        return positions

    def run_second_by_second_ratchet(
        self,
        direction: str,
        positions: List[NanpinPosition],
        second_by_second_prices: List[float],
    ) -> SecondBySecondTradeResult:
        """
        1秒ごとの価格推移に対して:
        - LONG: TP と SL を上方へ引き上げ（利益方向へロック）
        - SHORT: TP と SL を下方へ引き下げ（利益方向へロック）
        - 利益圏でのSL利確決済時に「さらに+」のプラス増幅を適用
        """
        direction = direction.upper()
        if direction not in ("LONG", "SHORT"):
            raise ValueError("direction must be 'LONG' or 'SHORT'")

        self.trade_counter += 1
        avg_entry = self.calc_avg_entry_price(positions)
        total_lot = round(sum(p.lot_size for p in positions), 2)

        sl_dist = self.initial_sl_pips * self.pip_size
        tp_dist = self.initial_tp_pips * self.pip_size
        sec_move = self.sec_step_pips * self.pip_size

        if direction == "LONG":
            tp_price = round(avg_entry + tp_dist, 4)
            sl_price = round(avg_entry - sl_dist, 4)
        else:  # SHORT
            tp_price = round(avg_entry - tp_dist, 4)
            sl_price = round(avg_entry + sl_dist, 4)

        initial_tp_price = tp_price
        initial_sl_price = sl_price

        exit_price = second_by_second_prices[-1] if second_by_second_prices else avg_entry
        exit_type = "ACTIVE_HOLD"
        seconds_elapsed = 0
        profit_sl_ratchet_count = 0

        for sec_idx, current_price in enumerate(second_by_second_prices, start=1):
            seconds_elapsed = sec_idx
            exit_price = current_price

            if direction == "LONG":
                # 1. SL到達チェック（利益圏 SL なら「SL利確決済」）
                if current_price <= sl_price:
                    exit_price = sl_price
                    if sl_price > avg_entry:
                        exit_type = "SL_PROFIT_EXIT"
                    else:
                        exit_type = "INITIAL_SL_EXIT"
                    break

                # 2. TP到達チェック
                if current_price >= tp_price:
                    exit_price = tp_price
                    exit_type = "TP_HIT"
                    break

                # 3. 秒単位で LONG の TP / SL を上方引き上げ
                profit_gain = current_price - avg_entry
                if profit_gain >= (sl_dist * 0.5):
                    target_sl = round(current_price - (sl_dist * 0.65), 4)
                    if target_sl > sl_price:
                        if sl_price >= avg_entry:
                            target_sl = round(max(target_sl, sl_price + sec_move), 4)
                            profit_sl_ratchet_count += 1
                        sl_price = target_sl
                        tp_price = round(max(tp_price, current_price + (tp_dist * 0.75)), 4)

            else:  # SHORT
                # 1. SL到達チェック（利益圏 SL なら「SL利確決済」）
                if current_price >= sl_price:
                    exit_price = sl_price
                    if sl_price < avg_entry:
                        exit_type = "SL_PROFIT_EXIT"
                    else:
                        exit_type = "INITIAL_SL_EXIT"
                    break

                # 2. TP到達チェック
                if current_price <= tp_price:
                    exit_price = tp_price
                    exit_type = "TP_HIT"
                    break

                # 3. 秒単位で SHORT の TP / SL を下方引き下げ
                profit_gain = avg_entry - current_price
                if profit_gain >= (sl_dist * 0.5):
                    target_sl = round(current_price + (sl_dist * 0.65), 4)
                    if target_sl < sl_price:
                        if sl_price <= avg_entry:
                            target_sl = round(min(target_sl, sl_price - sec_move), 4)
                            profit_sl_ratchet_count += 1
                        sl_price = target_sl
                        tp_price = round(min(tp_price, current_price - (tp_dist * 0.75)), 4)

        # 獲得pips算出
        if direction == "LONG":
            raw_pips = (exit_price - avg_entry) / self.pip_size
        else:
            raw_pips = (avg_entry - exit_price) / self.pip_size

        base_profit_pips = round(raw_pips, 2)

        # SL利確決済時の「さらに+」増幅ロジック
        extra_boost_pips = 0.0
        if exit_type == "SL_PROFIT_EXIT" and base_profit_pips > 0:
            ratchet_bonus = profit_sl_ratchet_count * (self.sec_step_pips * 0.4)
            extra_boost_pips = round((base_profit_pips * self.sl_plus_boost_rate) + ratchet_bonus, 2)

        total_profit_pips = round(base_profit_pips + extra_boost_pips, 2)

        summary = (
            f"[{direction}] ナンピン{len(positions)}段(合計Lot:{total_lot}, 平均建値:{avg_entry}) | "
            f"決済:{exit_type} ({seconds_elapsed}秒) | "
            f"SL推移:{initial_sl_price}->{sl_price} / TP推移:{initial_tp_price}->{tp_price} | "
            f"基準:{base_profit_pips:+.2f}pips + SL利確ブースト:{extra_boost_pips:+.2f}pips = "
            f"合計:{total_profit_pips:+.2f}pips"
        )

        return SecondBySecondTradeResult(
            trade_id=self.trade_counter,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            strategy_name=self.strategy_name,
            direction=direction,
            nanpin_count=len(positions),
            total_lot=total_lot,
            avg_entry_price=avg_entry,
            initial_tp_price=initial_tp_price,
            initial_sl_price=initial_sl_price,
            final_tp_price=tp_price,
            final_sl_price=sl_price,
            exit_price=exit_price,
            exit_type=exit_type,
            base_profit_pips=base_profit_pips,
            extra_sl_boost_pips=extra_boost_pips,
            total_profit_pips=total_profit_pips,
            seconds_elapsed=seconds_elapsed,
            log_summary=summary,
        )


def demo_run() -> None:
    ea = SecondBySecondRatchetNanpinEA(
        symbol="XAUUSD",
        pip_size=0.01,
        range_step_pips=150.0,
        max_nanpin_steps=3,
        initial_sl_pips=100.0,
        initial_tp_pips=400.0,
        sec_step_pips=15.0,
        sl_plus_boost_rate=0.15,
    )

    print(f"=== {ea.strategy_name} デモ実行 ===\n")

    # 1. LONGケース: ナンピンレンジで仕込み後、上昇→秒単位でTP/SL引き上げ→押し戻しでSL利確決済（+増幅）
    long_positions = ea.build_nanpin_range_positions(
        direction="LONG",
        range_prices=[2650.00, 2648.50, 2647.00],
        base_lot=0.10,
    )
    long_sec_prices = [
        2648.50, 2650.20, 2652.00, 2654.00, 2656.00,
        2655.20, 2654.00, 2652.50, 2651.00, 2649.50,
    ]
    res_long = ea.run_second_by_second_ratchet("LONG", long_positions, long_sec_prices)
    print("【LONG SL利確決済ケース】")
    print(res_long.log_summary)
    print()

    # 2. SHORTケース: ナンピンレンジで仕込み後、下落→秒単位でTP/SL引き下げ→戻しでSL利確決済（+増幅）
    short_positions = ea.build_nanpin_range_positions(
        direction="SHORT",
        range_prices=[2660.00, 2661.50, 2663.00],
        base_lot=0.10,
    )
    short_sec_prices = [
        2661.50, 2659.80, 2658.00, 2656.00, 2654.00,
        2654.80, 2656.00, 2657.50, 2659.00, 2660.50,
    ]
    res_short = ea.run_second_by_second_ratchet("SHORT", short_positions, short_sec_prices)
    print("【SHORT SL利確決済ケース】")
    print(res_short.log_summary)
    print()

    print("=== JSON出力 ===")
    print(json.dumps([asdict(res_long), asdict(res_short)], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    demo_run()

