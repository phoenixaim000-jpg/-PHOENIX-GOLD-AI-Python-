import time
import MetaTrader5 as mt5

# 1. MT5の初期化
if not mt5.initialize():
    print(f"MT5の初期化に失敗しました。エラーコード: {mt5.last_error()}")
    quit()

# 2. 許容する損失・利益の閾値設定（例として金額（円・USD等口座通貨ベース）で設定）
MAX_LOSS_LIMIT = -5000  # 含み損がこの金額を超えたら強制決済（例: -5000円）
TAKE_PROFIT_LIMIT = 10000  # 含み益がこの金額に達したら利確決済（例: +10000円）


def check_and_close_positions():
  # 現在保有しているポジションをすべて取得
  positions = mt5.positions_get()

  if positions is None or len(positions) == 0:
    print("現在保有中のポジションはありません。")
    return

  for pos in positions:
    ticket = pos.ticket
    symbol = pos.symbol
    volume = pos.volume
    profit = pos.profit  # 現在の含み損益（スワップ・手数料含む場合あり）
    pos_type = pos.type  # 0: 買い(BUY), 1: 売り(SELL)

    print(
        f"【監視中】 チケット: {ticket} | 通貨: {symbol} | ロット: {volume} |"
        f" 含み損益: {profit}"
    )

    # 損失制御の判定：損失が許容限界（MAX_LOSS_LIMIT）を下回っている場合
    if profit <= MAX_LOSS_LIMIT:
      print(
          f"*** 損失制限に到達しました (含み損: {profit})。強制決済を実行します"
          f" ***"
      )
      close_position(pos)

    # 利益確定の判定（必要に応じて）
    elif profit >= TAKE_PROFIT_LIMIT:
      print(f"*** 利確目標に到達しました (含み益: {profit})。決済を実行します ***")
      close_position(pos)


def close_position(pos):
  # 決済注文のパラメータ構築
  symbol = pos.symbol
  ticket = pos.ticket
  volume = pos.volume
  pos_type = pos.type

  # 買いポジションなら「売り」、売りポジションなら「買い」で決済する
  action_type = (
      mt5.TRADE_ACTION_DEAL
  )  # 取引アクション：成行（ブローカー仕様によってはクローズ専用リクエストを使用）

  if pos_type == mt5.POSITION_TYPE_BUY:
    trade_type = mt5.ORDER_TYPE_SELL
    price = mt5.symbol_info_tick(symbol).bid
  else:
    trade_type = mt5.ORDER_TYPE_BUY
    price = mt5.symbol_info_tick(symbol).ask

  request = {
      "action": mt5.TRADE_ACTION_DEAL,
      "symbol": symbol,
      "volume": volume,
      "type": trade_type,
      "position": ticket,  # 決済対象のポジションチケットを指定
      "price": price,
      "deviation": 20,  # 許容スリッページ（pips換算やポイント）
      "magic": 234000,
      "comment": "Python Risk Management Close",
      "type_time": mt5.ORDER_TIME_GTC,
      "type_filling": mt5.ORDER_FILLING_FOK,
  }

  # 注文送信
  result = mt5.order_send(request)
  if result.retcode != mt5.TRADE_RETCODE_DONE:
    print(f"決済注文に失敗しました。エラーコード: {result.retcode}")
  else:
    print(f"成功: ポジション {ticket} を決済しました。")


# 3. メインループ（一定間隔で監視を継続）
print("--- Pythonによる自動リスク管理・決済監視を開始します ---")
try:
  while True:
    check_and_close_positions()
    time.sleep(1)  # 1秒ごとにチェック（負荷や環境に合わせて調整）
except KeyboardInterrupt:
  print("プログラムを終了します。")
  mt5.shutdown()
