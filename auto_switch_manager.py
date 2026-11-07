from datetime import datetime
import time
import MetaTrader5 as mt5

# ==========================================
# 設定エリア（環境や戦略に合わせて調整）
# ==========================================
# 平日のメイン銘柄（ゴールド）
WEEKDAY_SYMBOL = "XAUUSD"

# 土日の切り替え銘柄（暗号通貨 / ブローカーの仕様に合わせて変更してください。例: BTCUSD または BTC/USD）
WEEKEND_SYMBOL = "BTCUSD"

# 資金管理・リスク制御の閾値（口座通貨ベース）
MAX_LOSS_LIMIT = -5000  # 含み損がこの金額を超えたら強制決済
TAKE_PROFIT_LIMIT = 10000  # 含み益がこの金額に達したら利確決済

# 監視ループの間隔（秒）
CHECK_INTERVAL = 10


def initialize_mt5():
  """MT5の初期化とログイン状態の確認"""
  if not mt5.initialize():
    print(
        f"❌ MT5の初期化に失敗しました。エラーコード: {mt5.last_error()}"
    )
    return False
  print("✅ MT5に正常に接続されました。")
  return True


def is_weekend_mode():
  """金曜深夜〜日曜夜の期間（ゴールド非番・暗号通貨稼働時間）かどうかを判定する"""
  now = datetime.now()
  weekday = now.weekday()  # 0:月曜, 4:金曜, 5:土曜, 6:日曜
  hour = now.hour

  # 土曜日は終日週末モード
  if weekday == 5:
    return True
  # 日曜日は終日週末モード
  if weekday == 6:
    return True
  # 金曜日の23時以降は週末モードへ移行
  if weekday == 4 and hour >= 23:
    return True
  # 月曜日の早朝（例: 2時未満）まではまだ週末モードを維持
  if weekday == 0 and hour < 2:
    return True

  return False


def get_current_target_symbol():
  """曜日に応じて監視・稼働するシンボルを動的に切り替える"""
  if is_weekend_mode():
    print(
        f"【週末モード】ゴールド非番のため、収益重視で暗号通貨（{WEEKEND_SYMBOL}）に切り替えます。"
    )
    return WEEKEND_SYMBOL
  else:
    print(f"【平日モード】メイン収益源であるゴールド（{WEEKDAY_SYMBOL}）で稼働します。")
    return WEEKDAY_SYMBOL


def check_and_manage_positions():
  """現在保有中のポジションを監視し、損益に応じて自動決済する"""
  target_symbol = get_current_target_symbol()

  # サーバーから保有ポジションを取得
  positions = mt5.positions_get()

  if positions is None or len(positions) == 0:
    print(
        f"ℹ️ 現在保有中のポジションはありません。（現在監視対象:"
        f" {target_symbol}）"
    )
    return

  for pos in positions:
    ticket = pos.ticket
    symbol = pos.symbol
    volume = pos.volume
    profit = pos.profit  # 含み損益

    print(
        f"🔍 【監視中】 チケット: {ticket} | 銘柄: {symbol} | ロット: {volume} |"
        f" 含み損益: {profit}"
    )

    # 損失制限の判定（許容損失を超えた場合）
    if profit <= MAX_LOSS_LIMIT:
      print(
          f"⚠️ 損失制限に到達しました (含み損: {profit})。強制決済を実行します。"
      )
      close_position(pos)

    # 利益確定の判定（目標利益に達した場合）
    elif profit >= TAKE_PROFIT_LIMIT:
      print(f"🎯 利確目標に到達しました (含み益: {profit})。決済を実行します。")
      close_position(pos)


def close_position(pos):
  """指定されたポジションの決済注文を送信する"""
  symbol = pos.symbol
  ticket = pos.ticket
  volume = pos.volume
  pos_type = pos.type

  # 買いポジションなら売り決済、売りポジションなら買い決済
  if pos_type == mt5.POSITION_TYPE_BUY:
    trade_type = mt5.ORDER_TYPE_SELL
    price = mt5.symbol_info_tick(symbol).bid
  else:
    trade_type = mt5.ORDER_TYPE_BUY
    price = mt5.symbol_info_tick(symbol).ask

  if price is None:
    print(f"❌ {symbol} の現在価格を取得できませんでした。")
    return

  request = {
      "action": mt5.TRADE_ACTION_DEAL,
      "symbol": symbol,
      "volume": volume,
      "type": trade_type,
      "position": ticket,
      "price": price,
      "deviation": 20,
      "magic": 888000,
      "comment": "Vision FX AI - Profit/Risk Auto Close",
      "type_time": mt5.ORDER_TIME_GTC,
      "type_filling": mt5.ORDER_FILLING_FOK,
  }

  result = mt5.order_send(request)
  if result.retcode != mt5.TRADE_RETCODE_DONE:
    print(f"❌ 決済注文に失敗しました。エラーコード: {result.retcode}")
  else:
    print(f"✨ 成功: ポジション (チケット: {ticket}) を決済しました。")


def main():
  print(
      "🚀 VISION FX AI EA - 土日収益最大化・自動切替リスク管理システムを起動しました"
      " 🚀"
  )

  if not initialize_mt5():
    return

  try:
    while True:
      check_and_manage_positions()
      time.sleep(CHECK_INTERVAL)
  except KeyboardInterrupt:
    print(
        "\n🛑 ユーザーの指示によりプログラムを停止します。MT5との接続を終了します。"
    )
    mt5.shutdown()


if __name__ == "__main__":
  main()
