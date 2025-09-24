import bluetooth

server_mac_address = "D8:3A:DD:85:B6:0F"
port = 1  # 通常RFCOMMのポートは1を使うことが多いです

sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
sock.connect((server_mac_address, port))

message = "テストメッセージ from NFC Pi"
sock.send(message)

print("Message sent.")

sock.close()
