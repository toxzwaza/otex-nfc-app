import board
import busio
from adafruit_pn532.i2c import PN532_I2C
import time
import json
import sys
import signal

# JSON保存ファイル名
OUTPUT_FILE = "nfc_data.json"

def read_nfc_tag(timeout=1):
    """
    NFCタグを読み取り、UIDを返す関数
    :param timeout: 読み取りタイムアウト秒数
    :return: UID（str型: hex表記） or None
    """
    uid = pn532.read_passive_target(timeout=timeout)
    if uid is not None:
        return uid.hex()
    return None

def save_to_json(data, filename=OUTPUT_FILE):
    """
    読み取ったIDとUIDをJSON形式で追記保存
    """
    try:
        # 既存データをロード
        try:
            with open(filename, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            existing = []

        # 新しいデータを追加
        existing.append(data)

        # 保存
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        print(f"保存しました: {data}")

    except Exception as e:
        print(f"保存エラー: {e}")

def signal_handler(sig, frame):
    print("\nプログラムを終了します。")
    sys.exit(0)

if __name__ == "__main__":
    # Ctrl+C ハンドラ登録
    signal.signal(signal.SIGINT, signal_handler)

    # I2C初期化
    i2c = busio.I2C(board.SCL, board.SDA)
    pn532 = PN532_I2C(i2c, debug=False)
    pn532.SAM_configuration()

    print("NFCリーダー初期化完了")

    while True:
        try:
            # ユーザーからIDを入力してもらう
            id_input = input("\n登録したいIDを入力してください (終了する場合は 'q' を入力): ")
            
            if id_input.lower() == 'q':
                print("プログラムを終了します。")
                break
            
            # IDを整数に変換
            current_id = int(id_input)
            
            print(f"\nID: {current_id} の登録を開始します")
            print("NFC読み取り中... タグをかざしてください")

            uid = None
            while uid is None:
                uid = read_nfc_tag(timeout=1)

            data = {"id": current_id, "uid": uid}
            save_to_json(data)

            print(f"ID: {current_id} と UID: {uid} の紐づけが完了しました")

        except ValueError:
            print("エラー: 有効な数値を入力してください")
        except KeyboardInterrupt:
            print("\nプログラムを終了します。")
            break
