# client.py
import socket

HOST = '192.168.10.2'  # サーバのIPアドレスに書き換えてください
PORT = 5000

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    message = "テストメッセージ"
    s.sendall(message.encode())
    print("送信完了")
