file_name = "phoenix_vision_gold_ai_dynamic_ea.py"
"""
PHOENIX VISION & GOLD AI DYNAMIC EA (多次元世界線・動的価値換算＆リスク管理統合版)
- 特徴: 
  1. 為替・ボラティリティに応じた動的pips/価値換算（円安・バブル・急落時のレバレッジ・ロット自動ブースト）
  2. 損切り(SL)・利確(TP)の自動付与による安全決済
  3. ナンピン回数・損失限界の厳格制御
  4. 初期設定はデモ安全設計（ENABLE_LIVE_TRADING = False）
"""

from datetime import datetime, timedelta
import time

import MetaTrader5 as mt5


# ---------- 設定：世界線・動的パラメータ ----------

SYMBOL_CONFIGS = {
    "XAUUSD": {
        "pip_size": 0.1,
        "base_min_pips": 250,
        "base_lot": 0.01,
        "magic": 20261111,
        "mode": "GOLD_AI_DYNAMIC",
    },
    "BTCUSD": {
        "pip_size": 1.0,
        "base_min_pips": 250,
        "base_lot": 0.01,
        "magic": 20261112,
        "mode": "VISION_FX_DYNAMIC",
    },
}

TIMEFRAME_ENTRY = mt5.TIMEFRAME_M1
TIMEFRAME_CONFIRM = mt5.TIMEFRAME_M5

MAX_CONSECUTIVE_LOSSES = 2
MAX_NANPIN_COUNT = 1  # ナンピンは最大1回（安全防衛ライン）

# 損切り(SL)・利確(TP)のデフォルト幅（pips換算）
DEFAULT_SL_PIPS = 300
DEFAULT_TP_PIPS = 500

# Falseの間は条件判定とログ出力のみ（デモ・ドライラン）
ENABLE_LIVE_TRADING = False

RESISTANCE_LOOKBACK = 30
POLL_SECONDS = 5


class PhoenixDynamicEA:
    def __init__(self, configs):
        self.configs = configs

        if not mt5.initialize():
            raise RuntimeError(f"MT5初期化失敗: {mt5.last_error()}")

        for symbol in self.configs.keys():
            if not mt5.symbol_select(symbol, True):
                raise RuntimeError(f"銘柄を選択できません: {symbol}")

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

    def get_usdjpy_rate(self):
        """為替レート（USDJPY）を取得し、円換算・動的スケーリングに利用する"""
        tick = mt5.symbol_info_tick("USDJPY")
        if tick and tick.bid > 0:
            return float(tick.bid)
        return 150.0  # 取得できない場合のフォールバック基準値

    def calculate_dynamic_thresholds(self, symbol, rates_1m):
        """
        円安・トレンド・急落（バブル局面）のボラティリティを演算し、
        要求pipsおよびロット倍率（レバレッジブースト）を動的に変動させる。
        """
        usdjpy = self.get_usdjpy_rate()
        
        # 直近の高値・安値の変動幅からボラティリティ（ATR代替）を簡易算出し、世界線係数を決定
        highs = [float(r["high"]) for r in rates_1m[-10:]]
        lows = [float(r["low"]) for r in rates_1m[-10:]]
        volatility = max(highs) - min(lows)

        # 円安影響・ボラティリティが高い局面（急落・バブル・トレンド初動）では基準を最適化
        # 1ドル170円換算等のマクロ視点を反映
        exchange_factor = usdjpy / 150.0 
        
        # 動的目標pipsの演算
        dynamic_min_pips = 250 * exchange_factor
        
        # ボラティリティが大きい（トレンド・急落・バブル局面）時はロット倍率を上げて勝ちに行く
        lot_multiplier = 1.0
        if volatility > (200 if symbol == "BTCUSD" else 10):
            lot_multiplier = 1.5  # チャンス世界線でのレバレッジブースト

        return dynamic_min_pips, lot_multiplier

    def bottom_candidate(self, rates_1m, rates_5m):
        """反転候補チェック（買い優勢の世界線選択）"""
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

    def evaluate_symbol(self, symbol, conf):
        magic = conf["magic"]
        pip_size = conf["pip_size"]
        base_lot = conf["base_lot"]
        mode = conf["mode"]

        try:
            rates_1m = self.get_rates(symbol, TIMEFRAME_ENTRY, 40)
            rates_5m = self.get_rates(symbol, TIMEFRAME_CONFIRM, 5)
        except Exception as e:
            return False, str(e), 0, 0, 0

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return False, "価格情報を取得できません", 0, 0, 0

        current_price = float(tick.ask)
        positions = self.get_open_positions(symbol, magic)

        # 動的閾値＆ロット倍率の演算
        dynamic_min_pips, lot_multiplier = self.calculate_dynamic_thresholds(symbol, rates_1m)

        if not self.bottom_candidate(rates_1m, rates_5m):
            return False, "反転候補条件を満たさないため見送り", 0, 0, 0

        bar_time = int(rates_1m[-2]["time"])
        if self.last_checked_bar_times[symbol] == bar_time:
            return False, "同じ確定足では再判定しません", 0, 0, 0
        self.last_checked_bar_times[symbol] = bar_time

        if positions:
            if len(positions) > MAX_NANPIN_COUNT:
                return False, "ナンピン上限（防衛ライン）到達のため見送り", 0, 0, 0

            average_price, current_volume = self.weighted_average(positions)
            if average_price is None or current_price >= average_price:
                return False, "保有ポジションが含み損でないためナンピンしません", 0, 0, 0

            info = mt5.symbol_info(symbol)
            if info is None:
                return False, "銘柄仕様取得失敗", 0, 0, 0

            raw_lot = min(base_lot * lot_multiplier, current_volume * 0.25)
            step = float(info.volume_step)
            min_volume = float(info.volume_min)
            add_lot = max(min_volume, round((raw_lot // step) * step, 8))

            projected_average = (
                average_price * current_volume + current_price * add_lot
            ) / (current_volume + add_lot)
            reason = "小ナンピン（防衛・押し上げ決済準備）"
        else:
            add_lot = round(base_lot * lot_multiplier, 8)
            projected_average = current_price
            reason = "新規エントリー（トレンド初動・バブル/急落狙い）"

        # 直近高値までの距離（pips）確認
        resistance_bars = rates_1m[-(RESISTANCE_LOOKBACK + 1):-1]
        resistance = max(float(r["high"]) for r in resistance_bars)

        expected_pips = (resistance - projected_average) / pip_size
        if expected_pips < dynamic_min_pips:
            return False, f"直近高値まで約{expected_pips:.1f} pips。動的目標({dynamic_min_pips:.1f} pips)未満のため見送り", 0, 0, 0

        # 損切り(SL)・利確(TP)価格の算出
        sl_price = current_price - (DEFAULT_SL_PIPS * pip_size)
        tp_price = current_price + (DEFAULT_TP_PIPS * pip_size)

        return True, f"[{mode}] {reason}条件通過。ロット={add_lot}, 余地={expected_pips:.1f}pips (動的閾値クリア)", add_lot, sl_price, tp_price

    def place_order(self, symbol, conf, volume, sl_price, tp_price, comment):
        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)

        if info is None or tick is None:
            print(f"[{symbol}] 注文失敗: 銘柄情報取得できず")
            return

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY,
            "price": float(tick.ask),
            "sl": float(sl_price),
            "tp": float(tp_price),
            "deviation": 50,
            "magic": conf["magic"],
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": info.filling_mode,
        }

        result = mt5.order_send(request)
        if result is None:
            print(f"[{symbol}] [注文エラー] {mt5.last_error()}")
        elif result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"[{symbol}] [注文拒否] retcode={result.retcode}, comment={result.comment}")
        else:
            print(f"[{symbol}] [注文成功] order={result.order}, volume={volume}, SL={sl_price}, TP={tp_price}")

    def run(self):
        targets = ", ".join(self.configs.keys())
        print(f"=== PHOENIX DYNAMIC EA 起動 ===")
        print(f"監視銘柄: [{targets}] | 実注文={'有効' if ENABLE_LIVE_TRADING else '無効（デモ・ドライラン中）'}")

        while True:
            try:
                for symbol, conf in self.configs.items():
                    allowed, message, volume, sl, tp = self.evaluate_symbol(symbol, conf)
                    timestamp = datetime.now().isoformat(timespec='seconds')
                    print(f"[{timestamp}] [{symbol}] {message}")

                    if allowed and ENABLE_LIVE_TRADING:
                        positions = self.get_open_positions(symbol, conf["magic"])
                        comment = "SMALL_NANPIN" if positions else "PHOENIX_DYNAMIC_ENTRY"
                        self.place_order(symbol, conf, volume, sl, tp, comment)

            except Exception as exc:
                print(f"[エラー発生] {exc}")

            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    bot = None
    try:
        bot = PhoenixDynamicEA(SYMBOL_CONFIGS)
        bot.run()
    except KeyboardInterrupt:
        print("プログラムを停止しました。")
    finally:
        mt5.shutdown()
