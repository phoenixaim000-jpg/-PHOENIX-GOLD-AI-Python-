file_name = "phoenix_multi_symbol_nanpin.py"
"""
PHOENIX マルチシンボル対応・小ナンピン用エントリー条件フィルター
（BTCUSD, XAUUSD, その他通貨ペア対応版）

注意:
- これは利益を保証するプログラムではありません。
- 各銘柄の PIP_SIZE や仕様は口座業者の仕様に合わせて必ず設定してください。
- 初期設定では実注文を出しません（ENABLE_LIVE_TRADING = False）。
- 実注文を有効にする前に、MT5デモ口座で十分にテストしてください。
"""

from datetime import datetime, timedelta
import time

import MetaTrader5 as mt5


# ---------- 設定：必ず口座業者の仕様を確認してください ----------

# 監視する銘柄ごとの設定辞書
# ※ PIP_SIZE はブローカーの仕様（小数点以下の桁数や1pipの定義）に合わせて必ず調整してください。
SYMBOL_CONFIGS = {
    "BTCUSD": {
        "pip_size": 1.0,           # 例: 業者の仕様に合わせて変更 (例: 1.0 または 0.1)
        "min_expected_pips": 250,  # ご要望の250 pips以上
        "base_lot": 0.01,
        "magic": 20261101,
    },
    "XAUUSD": {
        "pip_size": 0.1,           # ゴールドの1 pip（通常 0.1 または 0.01）
        "min_expected_pips": 250,  # ゴールドでの250 pips（必要に応じて調整）
        "base_lot": 0.01,
        "magic": 20261102,
    },
    # 必要に応じて通貨ペアを追加可能
    # "EURUSD": {
    #     "pip_size": 0.0001,
    #     "min_expected_pips": 50,
    #     "base_lot": 0.01,
    #     "magic": 20261103,
    # },
}

TIMEFRAME_ENTRY = mt5.TIMEFRAME_M1
TIMEFRAME_CONFIRM = mt5.TIMEFRAME_M5

MAX_CONSECUTIVE_LOSSES = 2
MAX_NANPIN_COUNT = 1

# Falseの間は条件判定とログ表示のみ。実際の注文は出しません。
ENABLE_LIVE_TRADING = False

# 直近高値を利確候補として参照する本数
RESISTANCE_LOOKBACK = 30

# 各銘柄を巡回してチェックするインターバル（秒）
POLL_SECONDS = 5


class PhoenixMultiSymbolNanpin:
    def __init__(self, configs):
        self.configs = configs

        if not mt5.initialize():
            raise RuntimeError(f"MT5初期化失敗: {mt5.last_error()}")

        for symbol in self.configs.keys():
            if not mt5.symbol_select(symbol, True):
                raise RuntimeError(f"銘柄を選択できません: {symbol}")

        # 銘柄ごとの前回チェックした確定足の時間を保持
        self.last_checked_bar_times = {symbol: None for symbol in configs.keys()}

    def get_rates(self, symbol, timeframe, count):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None or len(rates) < count:
            raise RuntimeError(f"[{symbol}] 価格データ取得失敗: {mt5.last_error()}")
        return rates

    def get_open_positions(self, symbol, magic):
        positions = mt5.positions_get(symbol=symbol)
        if positions is None:
            return []
        return [p for p in positions if p.magic == magic]

    def consecutive_losses(self, symbol, magic):
        """直近の決済済みポジションの連敗数を履歴から数える。"""
        end = datetime.now()
        start = end - timedelta(days=90)
        deals = mt5.history_deals_get(start, end)

        if deals is None:
            print(f"[{symbol}] [警告] 取引履歴を取得できません: {mt5.last_error()}")
            return 0

        grouped = {}
        for deal in deals:
            if deal.symbol != symbol or deal.magic != magic:
                continue

            position_id = getattr(deal, "position_id", None)
            if position_id is None:
                continue

            item = grouped.setdefault(
                position_id,
                {"net": 0.0, "last_time": 0, "closed": False},
            )
            item["net"] += (
                float(getattr(deal, "profit", 0.0))
                + float(getattr(deal, "commission", 0.0))
                + float(getattr(deal, "swap", 0.0))
                + float(getattr(deal, "fee", 0.0))
            )
            item["last_time"] = max(item["last_time"], int(deal.time))

            if deal.entry in (
                mt5.DEAL_ENTRY_OUT,
                mt5.DEAL_ENTRY_OUT_BY,
                mt5.DEAL_ENTRY_INOUT,
            ):
                item["closed"] = True

        closed = [v for v in grouped.values() if v["closed"]]
        closed.sort(key=lambda v: v["last_time"], reverse=True)

        losses = 0
        for position in closed:
            if position["net"] < 0:
                losses += 1
            else:
                break
        return losses

    def bottom_candidate(self, rates_1m, rates_5m):
        """
        簡易的な反転候補チェック:
        - 直近の確定1分足が、直近5本の安値圏
        - その1分足が陽線
        - 直近確定5分足も陽線
        """
        lows = [float(r["low"]) for r in rates_1m[-6:-1]]
        candle_1m = rates_1m[-2]
        candle_5m = rates_5m[-2]

        local_low = float(candle_1m["low"]) <= min(lows)
        bullish_1m = float(candle_1m["close"]) > float(candle_1m["open"])
        bullish_5m = float(candle_5m["close"]) > float(candle_5m["open"])

        return local_low and bullish_1m and bullish_5m

    def weighted_average(self, positions):
        total_volume = sum(float(p.volume) for p in positions)
        if total_volume <= 0:
            return None, 0.0

        average = sum(
            float(p.price_open) * float(p.volume) for p in positions
        ) / total_volume

        return average, total_volume

    def has_already_nanpinned(self, positions):
        return any("SMALL_NANPIN" in str(p.comment) for p in positions)

    def evaluate_symbol(self, symbol, conf):
        magic = conf["magic"]
        pip_size = conf["pip_size"]
        min_expected_pips = conf["min_expected_pips"]
        base_lot = conf["base_lot"]

        if pip_size <= 0:
            return False, f"PIP_SIZEが未設定または不正です"

        losses = self.consecutive_losses(symbol, magic)
        if losses >= MAX_CONSECUTIVE_LOSSES:
            return False, f"{losses}連敗のため停止"

        try:
            rates_1m = self.get_rates(symbol, TIMEFRAME_ENTRY, 40)
            rates_5m = self.get_rates(symbol, TIMEFRAME_CONFIRM, 5)
        except Exception as e:
            return False, str(e)

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return False, "価格情報を取得できません"

        current_price = float(tick.ask)
        positions = self.get_open_positions(symbol, magic)

        if not self.bottom_candidate(rates_1m, rates_5m):
            return False, "反転候補条件を満たさないため見送り"

        # 同じ確定足での重複判定を防ぐ
        bar_time = int(rates_1m[-2]["time"])
        if self.last_checked_bar_times[symbol] == bar_time:
            return False, "同じ確定足では再判定しません"
        self.last_checked_bar_times[symbol] = bar_time

        if positions:
            if len(positions) >= 2 or self.has_already_nanpinned(positions):
                return False, "ナンピン上限に達しているため見送り"

            average_price, current_volume = self.weighted_average(positions)
            if average_price is None or current_price >= average_price:
                return False, "保有ポジションが含み損でないためナンピンしません"

            info = mt5.symbol_info(symbol)
            if info is None:
                return False, "銘柄仕様を取得できません"

            raw_lot = min(base_lot, current_volume * 0.25)
            step = float(info.volume_step)
            min_volume = float(info.volume_min)

            add_lot = (raw_lot // step) * step
            add_lot = round(add_lot, 8)

            if add_lot < min_volume:
                return False, "小ナンピン量が最小取引数量未満のため見送り"

            projected_average = (
                average_price * current_volume + current_price * add_lot
            ) / (current_volume + add_lot)

            reason = "小ナンピン"
        else:
            add_lot = base_lot
            projected_average = current_price
            reason = "新規エントリー"

        # 直近確定足の指定本数から高値を算出し、トレンド・レンジ余地（pips）を確認
        resistance_bars = rates_1m[-(RESISTANCE_LOOKBACK + 1):-1]
        resistance = max(float(r["high"]) for r in resistance_bars)

        expected_pips = (resistance - projected_average) / pip_size
        if expected_pips < min_expected_pips:
            return False, (
                f"直近高値まで約{expected_pips:.1f} pips。"
                f"目標の {min_expected_pips} pips 未満のためトレンド余地なしと判断"
            )

        return True, (
            f"{reason}条件通過。ロット={add_lot}, "
            f"直近高値まで約{expected_pips:.1f} pips（トレンド/レンジ余地確認）"
        )

    def place_buy(self, symbol, conf, volume, comment):
        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)

        if info is None or tick is None:
            print(f"[{symbol}] [注文見送り] 銘柄情報または価格情報を取得できません")
            return

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY,
            "price": float(tick.ask),
            "deviation": 50,
            "magic": conf["magic"],
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": info.filling_mode,
        }

        result = mt5.order_send(request)
        if result is None:
            print(f"[{symbol}] [注文失敗] {mt5.last_error()}")
        elif result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"[{symbol}] [注文失敗] retcode={result.retcode}, comment={result.comment}")
        else:
            print(f"[{symbol}] [注文成功] order={result.order}, volume={volume}")

    def run(self):
        targets = ", ".join(self.configs.keys())
        print(
            f"マルチシンボル監視開始 銘柄: [{targets}]。"
            f"実注文={'有効' if ENABLE_LIVE_TRADING else '無効（ドライラン）'}"
        )

        while True:
            try:
                for symbol, conf in self.configs.items():
                    allowed, message = self.evaluate_symbol(symbol, conf)
                    timestamp = datetime.now().isoformat(timespec='seconds')
                    print(f"[{timestamp}] [{symbol}] {message}")

                    if allowed and ENABLE_LIVE_TRADING:
                        positions = self.get_open_positions(symbol, conf["magic"])
                        comment = "SMALL_NANPIN" if positions else "PHOENIX_ENTRY"
                        self.place_buy(symbol, conf, conf["base_lot"], comment)

            except Exception as exc:
                print(f"[エラー] {exc}")

            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    bot = None
    try:
        bot = PhoenixMultiSymbolNanpin(SYMBOL_CONFIGS)
        bot.run()
    except KeyboardInterrupt:
        print("停止しました")
    finally:
        mt5.shutdown()
