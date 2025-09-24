import bluetooth

def send_message(message):
    """Bluetoothでメッセージを送信する関数"""
    server_mac_address = "D8:3A:DD:85:B6:0F"
    port = 1  # 通常RFCOMMのポートは1を使うことが多いです

    sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    sock.connect((server_mac_address, port))

    sock.send(message)
    print("Message sent.")

    sock.close()

# テスト用（直接実行時）
if __name__ == "__main__":
    message = "UIDtest!"
    send_message(message)
