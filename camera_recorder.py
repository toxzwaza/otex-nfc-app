import cv2
import time
from datetime import datetime
import os
import threading
import json
import bluetooth
import logging

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('camera_recorder.log')
    ]
)
logger = logging.getLogger(__name__)

os.environ["QT_QPA_PLATFORM"] = "xcb"

width, height = 640, 360
fps = 20
font = cv2.FONT_HERSHEY_SIMPLEX

is_recording = False
out = None
server_sock = None
bluetooth_running = True

received_uid = ""
uid_received_time = 0

def get_output_filename():
    now = datetime.now()
    return now.strftime("%Y-%m-%d_%H-%M-%S") + ".mp4"

def save_uid_to_json(uid):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "uid": uid,
        "timestamp": timestamp,
        "datetime": datetime.now().isoformat()
    }
    filename = "uid.json"
    try:
        existing_data = []
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        existing_data.append(data)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
        logger.info(f"UIDをJSONファイルに追加: {uid}")
    except Exception as e:
        logger.error(f"JSONファイル保存エラー: {e}")

def draw_timestamp(frame):
    timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    text_size, _ = cv2.getTextSize(timestamp, font, 0.6, 1)
    text_w, text_h = text_size
    x = frame.shape[1] - text_w - 10
    y = frame.shape[0] - 10
    cv2.putText(frame, timestamp, (x, y), font, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

def draw_buttons(frame):
    color = (0, 255, 0) if is_recording else (0, 0, 255)
    label = "STOP" if is_recording else "START"
    cv2.rectangle(frame, (10, 10), (110, 50), color, -1)
    cv2.putText(frame, label, (20, 40), font, 0.8, (255, 255, 255), 2)

def mouse_callback(event, x, y, flags, param):
    global is_recording, out
    if event == cv2.EVENT_LBUTTONDOWN:
        if 10 <= x <= 110 and 10 <= y <= 50:
            if is_recording:
                logger.info("録画停止")
                is_recording = False
                if out:
                    out.release()
                    out = None
            else:
                logger.info("録画開始")
                is_recording = True
                filename = get_output_filename()
                fourcc = cv2.VideoWriter_fourcc(*'avc1')
                out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
                logger.info(f"保存ファイル: {filename}")

def bluetooth_server():
    global received_uid, uid_received_time, server_sock, bluetooth_running
    
    try:
        server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        server_sock.bind(("", 1))  # チャネル1で待受
        server_sock.listen(1)
        server_sock.settimeout(1.0)  # タイムアウト設定
        logger.info("Bluetooth UID受信サーバ 起動中...")

        while bluetooth_running:
            try:
                client_sock, client_info = server_sock.accept()
                logger.info(f"接続許可: {client_info}")
                
                try:
                    client_sock.settimeout(10.0)  # クライアントソケットのタイムアウト
                    while bluetooth_running:
                        data = client_sock.recv(1024)
                        if not data:
                            break
                        received_uid = data.decode('utf-8').strip()
                        uid_received_time = time.time()
                        logger.info(f"UID受信: {received_uid}")
                        save_uid_to_json(received_uid)
                        
                except bluetooth.btcommon.BluetoothError as e:
                    logger.warning(f"Bluetooth通信エラー: {e}")
                except Exception as e:
                    logger.error(f"予期しないエラー: {e}")
                finally:
                    try:
                        client_sock.close()
                    except:
                        pass
                        
            except bluetooth.btcommon.BluetoothError as e:
                if "timed out" not in str(e).lower():
                    logger.warning(f"Bluetooth接続エラー: {e}")
            except Exception as e:
                logger.error(f"予期しないBluetoothエラー: {e}")
                
    except Exception as e:
        logger.error(f"Bluetoothサーバー初期化エラー: {e}")
    finally:
        if server_sock:
            try:
                server_sock.close()
            except:
                pass
        logger.info("Bluetoothサーバー終了")

def cleanup():
    """リソースのクリーンアップ"""
    global bluetooth_running, server_sock, out, cap
    logger.info("クリーンアップ開始")
    
    bluetooth_running = False
    
    if server_sock:
        try:
            server_sock.close()
        except:
            pass
    
    if out:
        try:
            out.release()
        except:
            pass
    
    if cap:
        try:
            cap.release()
        except:
            pass
    
    cv2.destroyAllWindows()
    logger.info("クリーンアップ完了")

# Bluetoothサーバースレッド開始
bluetooth_thread = threading.Thread(target=bluetooth_server, daemon=True)
bluetooth_thread.start()

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    logger.error("カメラを開けませんでした")
    cleanup()
    exit(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
cap.set(cv2.CAP_PROP_FPS, fps)

cv2.namedWindow('Camera Feed')
cv2.setMouseCallback('Camera Feed', mouse_callback)

logger.info("カメラ録画アプリケーション開始")

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            logger.warning("フレーム読み取りに失敗しました")
            break

        record_frame = frame.copy()
        draw_timestamp(record_frame)
        preview_frame = record_frame.copy()
        draw_buttons(preview_frame)

        # UID表示（10秒間表示）
        if received_uid and (time.time() - uid_received_time) < 10:
            cv2.putText(preview_frame, f"UID: {received_uid}", (10, 90),
                        font, 1, (0, 0, 255), 2, cv2.LINE_AA)
            if is_recording and out:
                cv2.putText(record_frame, f"UID: {received_uid}", (10, 90),
                            font, 1, (0, 0, 255), 2, cv2.LINE_AA)
                out.write(record_frame)
        else:
            if is_recording and out:
                out.write(record_frame)

        cv2.imshow('Camera Feed', preview_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            logger.info("ユーザーによる終了")
            break

except KeyboardInterrupt:
    logger.info("キーボード割り込みによる終了")
except Exception as e:
    logger.error(f"予期しないエラー: {e}")
finally:
    cleanup() 