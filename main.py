import board
import busio
from adafruit_pn532.i2c import PN532_I2C
import socket
import time
import tkinter as tk
from tkinter import ttk
import threading
from datetime import datetime
import time
import bluetooth
import logging
import traceback
from bluetooth_send2 import send_message

# ログ設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # コンソール出力
        logging.FileHandler('nfc_reader.log')  # ファイル出力
    ]
)
logger = logging.getLogger(__name__)

class NFCReaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("NFCリーダー")
        
        logger.info("NFCリーダーアプリケーション開始")
        
        # 全画面表示
        try:
            # Linux用の全画面表示
            self.root.attributes('-zoomed', True)
            logger.info("Linux全画面表示設定完了")
        except:
            try:
                # Windows用の全画面表示
                self.root.state('zoomed')
                logger.info("Windows全画面表示設定完了")
            except:
                # フォールバック: 画面サイズを取得して全画面に設定
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                self.root.geometry(f"{screen_width}x{screen_height}+0+0")
                logger.info(f"フォールバック全画面表示設定完了: {screen_width}x{screen_height}")
        
        self.root.configure(bg='#f0f0f0')
        
        # 大きなボタンスタイルの設定
        style = ttk.Style()
        style.configure('Large.TButton', font=('Arial', 12))
        
        # GUI要素の作成（先に作成）
        self.create_widgets()
        
        # 読み取り状態
        self.is_reading = False
        self.reading_thread = None
        self.clear_timer = None
        
        # NFC関連の初期化
        self.pn532 = None
        self.i2c = None
        self.nfc_initialized = False
        
        # NFC初期化（GUI作成後に実行）
        self.setup_nfc()
        
        # 初期化が成功した場合のみ読み取り開始
        if self.nfc_initialized:
            self.start_reading()
        else:
            logger.warning("NFC初期化が失敗したため、読み取りを開始しません")
            self.update_status("NFC初期化失敗 - アプリケーションを再起動してください", "error")
    
    def setup_nfc(self):
        """NFCリーダーの初期化"""
        try:
            logger.info("NFC初期化開始")
            self.update_status("I2C初期化中...", "info")
            self.i2c = busio.I2C(board.SCL, board.SDA)
            logger.info("I2C初期化完了")
            self.update_status("I2C初期化完了", "success")
            
            self.update_status("PN532初期化中...", "info")
            self.pn532 = PN532_I2C(self.i2c, debug=False)
            logger.info("PN532オブジェクト作成完了")
            self.update_status("PN532オブジェクト作成完了", "success")
            
            self.update_status("ファームウェアバージョン取得中...", "info")
            ic, ver, rev, support = self.pn532.firmware_version
            logger.info(f"ファームウェアバージョン: {ver}.{rev}")
            self.update_status(f"ファームウェアバージョン: {ver}.{rev}", "success")
            
            self.update_status("SAM設定中...", "info")
            self.pn532.SAM_configuration()
            logger.info("SAM設定完了")
            self.update_status("SAM設定完了", "success")
            
            self.update_status(f"PN532初期化完了 (v{ver}.{rev})", "success")
            logger.info("NFC初期化完了")
            self.nfc_initialized = True
            
        except Exception as e:
            error_msg = f"NFC初期化エラー: {e}"
            logger.error(error_msg)
            logger.error(f"詳細エラー情報: {traceback.format_exc()}")
            self.update_status(error_msg, "error")
            self.nfc_initialized = False
    
    def create_widgets(self):
        """GUI要素の作成"""
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # タイトル
        title_label = ttk.Label(main_frame, text="NFCタグ読み取りシステム", 
                               font=('Arial', 24, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # ステータス表示
        status_frame = ttk.LabelFrame(main_frame, text="ステータス", padding="10")
        status_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        self.status_label = ttk.Label(status_frame, text="初期化中...", 
                                     font=('Arial', 14))
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        # 読み取り結果表示
        result_frame = ttk.LabelFrame(main_frame, text="読み取り結果", padding="10")
        result_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # UID表示
        uid_frame = ttk.Frame(result_frame)
        uid_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Label(uid_frame, text="UID:", font=('Arial', 12, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.uid_label = ttk.Label(uid_frame, text="---", font=('Courier', 16))
        self.uid_label.grid(row=0, column=1, sticky=tk.W, padx=(15, 0))
        
        # UIDバイト列表示
        uid_bytes_frame = ttk.Frame(result_frame)
        uid_bytes_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Label(uid_bytes_frame, text="UIDバイト列:", font=('Arial', 12, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.uid_bytes_label = ttk.Label(uid_bytes_frame, text="---", font=('Courier', 14))
        self.uid_bytes_label.grid(row=0, column=1, sticky=tk.W, padx=(15, 0))
        
        # URL表示
        url_frame = ttk.Frame(result_frame)
        url_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Label(url_frame, text="生成URL:", font=('Arial', 12, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.url_label = ttk.Label(url_frame, text="---", font=('Courier', 14), wraplength=600)
        self.url_label.grid(row=0, column=1, sticky=tk.W, padx=(15, 0))
        
        # 送信状況表示
        send_frame = ttk.Frame(result_frame)
        send_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Label(send_frame, text="送信状況:", font=('Arial', 12, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.send_label = ttk.Label(send_frame, text="---", font=('Arial', 12))
        self.send_label.grid(row=0, column=1, sticky=tk.W, padx=(15, 0))
        
        # Bluetooth接続状況表示
        bluetooth_frame = ttk.Frame(result_frame)
        bluetooth_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 0))
        
        ttk.Label(bluetooth_frame, text="Bluetooth接続:", font=('Arial', 12, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.bluetooth_label = ttk.Label(bluetooth_frame, text="未接続", font=('Arial', 12), foreground="red")
        self.bluetooth_label.grid(row=0, column=1, sticky=tk.W, padx=(15, 0))
        

        
        # ボタンフレーム
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(20, 0))
        
        self.start_button = ttk.Button(button_frame, text="読み取り開始", 
                                      command=self.start_reading, style='Large.TButton')
        self.start_button.grid(row=0, column=0, padx=(0, 15))
        
        self.stop_button = ttk.Button(button_frame, text="読み取り停止", 
                                     command=self.stop_reading, state='disabled', style='Large.TButton')
        self.stop_button.grid(row=0, column=1, padx=(0, 15))
        

        
        # グリッドの重み設定
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
    
    def update_status(self, message, status_type="info"):
        """ステータス表示の更新"""
        colors = {
            "success": "green",
            "error": "red", 
            "warning": "orange",
            "info": "black"
        }
        self.status_label.config(text=message, foreground=colors.get(status_type, "black"))
    
    def clear_display(self):
        """表示情報をクリア"""
        self.uid_label.config(text="---")
        self.uid_bytes_label.config(text="---")
        self.url_label.config(text="---")
        self.send_label.config(text="---", foreground="black")
        self.bluetooth_label.config(text="未接続", foreground="red")
        self.update_status("NFCタグをかざしてください...", "info")
    
    def schedule_clear_display(self):
        """5秒後に表示をクリアするタイマーを設定"""
        # 既存のタイマーをキャンセル
        if self.clear_timer:
            self.clear_timer.cancel()
        
        # 新しいタイマーを設定
        self.clear_timer = threading.Timer(5.0, self.clear_display)
        self.clear_timer.start()
    
    def start_reading(self):
        """読み取り開始"""
        if not self.is_reading and self.nfc_initialized:
            self.is_reading = True
            self.start_button.config(state='disabled')
            self.stop_button.config(state='normal')
            self.reading_thread = threading.Thread(target=self.reading_loop, daemon=True)
            self.reading_thread.start()
            self.update_status("読み取り開始", "success")
        elif not self.nfc_initialized:
            logger.error("NFCが初期化されていないため、読み取りを開始できません")
            self.update_status("NFC初期化失敗 - 読み取りを開始できません", "error")
    
    def stop_reading(self):
        """読み取り停止"""
        self.is_reading = False
        self.start_button.config(state='normal')
        self.stop_button.config(state='disabled')
        self.update_status("読み取り停止", "warning")
        
        # タイマーをキャンセル
        if self.clear_timer:
            self.clear_timer.cancel()
            self.clear_timer = None
    
    def reading_loop(self):
        """読み取りループ"""
        logger.info("読み取りループ開始")
        while self.is_reading:
            try:
                # NFC初期化状態をチェック
                if not self.nfc_initialized or self.pn532 is None:
                    logger.error("NFCが初期化されていません")
                    self.update_status("NFC初期化エラー - 読み取りを停止します", "error")
                    self.stop_reading()
                    break
                
                self.update_status("NFCタグをかざしてください...", "info")
                
                # NFCタグ読み取り
                try:
                    uid = self.pn532.read_passive_target(timeout=1)
                except Exception as e:
                    error_msg = f"NFC読み取りエラー: {e}"
                    logger.error(error_msg)
                    logger.error(f"詳細エラー情報: {traceback.format_exc()}")
                    self.update_status(error_msg, "error")
                    time.sleep(1)
                    continue
                
                if uid is not None:
                    logger.info(f"タグ検出: {uid.hex()}")
                    self.update_status("タグ検出！処理開始...", "success")
                    self.process_tag(uid)
                    time.sleep(2)  # 次の読み取りまでの待機
                else:
                    time.sleep(0.1)  # 短い待機
                    
            except Exception as e:
                error_msg = f"読み取りループエラー: {e}"
                logger.error(error_msg)
                logger.error(f"詳細エラー情報: {traceback.format_exc()}")
                self.update_status(error_msg, "error")
                time.sleep(1)
        
        logger.info("読み取りループ終了")
    
    def process_tag(self, uid):
        """タグ処理"""
        try:
            logger.info("タグ処理開始")
            self.update_status("タグ処理開始...", "info")
            
            # UID情報の表示
            uid_str = uid.hex()
            uid_bytes = list(uid)
            
            logger.info(f"UID: {uid_str}, バイト列: {uid_bytes}")
            self.uid_label.config(text=uid_str)
            self.uid_bytes_label.config(text=str(uid_bytes))
            self.update_status("UID情報表示完了", "success")
            
            # URL生成
            url = f"https://akioka-sub.cloud/questionnaire/{uid_str}"
            logger.info(f"生成URL: {url}")
            self.url_label.config(text=url)
            self.update_status("URL生成完了", "success")
            
            # NFCタグへの書き込み
            self._write_to_nfc_tag(uid_str)
            
            # Bluetooth送信
            self._send_via_bluetooth(uid_str)
            
            # 5秒後に表示をクリアするタイマーを設定
            self.schedule_clear_display()
            logger.info("タグ処理完了")
            
        except Exception as e:
            error_msg = f"タグ処理エラー: {e}"
            logger.error(error_msg)
            logger.error(f"詳細エラー情報: {traceback.format_exc()}")
            self.update_status(error_msg, "error")
    
    def _write_to_nfc_tag(self, uid_str):
        """NFCタグへの書き込み処理"""
        try:
            logger.info("NFCタグ書き込み開始")
            self.update_status("NFCタグ書き込み中...", "info")
            self.write_to_tag(uid_str)
            logger.info("NFCタグ書き込み完了")
            self.update_status("NFCタグ書き込み完了", "success")
        except Exception as e:
            error_msg = f"NFCタグ書き込みエラー: {e}"
            logger.warning(error_msg)
            logger.warning(f"詳細エラー情報: {traceback.format_exc()}")
            self.update_status(error_msg, "warning")
    
    def _send_via_bluetooth(self, uid_str):
        """Bluetooth送信処理"""
        try:
            logger.info("Bluetooth送信開始")
            self.update_status("Bluetooth送信開始...", "info")
            self.send_to_camera(uid_str)
            logger.info("Bluetooth送信完了")
            self.update_status("Bluetooth送信完了", "success")
        except Exception as e:
            error_msg = f"Bluetooth送信エラー: {e}"
            logger.warning(error_msg)
            logger.warning(f"詳細エラー情報: {traceback.format_exc()}")
            self.update_status(error_msg, "warning")
    
    def write_to_tag(self, uid_str):
        """NFCタグへの書き込み"""
        try:
            # NFC初期化状態をチェック
            if not self.nfc_initialized or self.pn532 is None:
                logger.error("NFCが初期化されていないため、タグ書き込みをスキップします")
                return
            
            url = f"https://akioka-sub.cloud/questionnaire/{uid_str}"
            uri_body = url.replace("https://", "").encode('utf-8')
            
            ndef_record = b'\xD1\x01' + bytes([len(uri_body) + 1]) + b'\x55\x04' + uri_body
            tlv = b'\x03' + bytes([len(ndef_record)]) + ndef_record + b'\xFE'
            
            data = list(tlv) + [0x00] * (144 - len(tlv))
            
            for i in range(0, len(data), 4):
                page = 4 + i // 4
                block = data[i:i+4]
                if len(block) < 4:
                    block += [0x00] * (4 - len(block))
                self.pn532.ntag2xx_write_block(page, block)
            
        except Exception as e:
            logger.error(f"NFCタグ書き込みエラー: {e}")
            raise
    
    def check_bluetooth_device(self, mac_address):
        """Bluetoothデバイスの状態を確認"""
        try:
            logger.info(f"Bluetoothデバイス確認中: {mac_address}")
            
            # デバイス検索
            nearby_devices = bluetooth.discover_devices(lookup_names=True)
            logger.info(f"発見されたデバイス数: {len(nearby_devices)}")
            
            for addr, name in nearby_devices:
                logger.info(f"デバイス: {addr} - {name}")
                if addr.upper() == mac_address.upper():
                    logger.info(f"ターゲットデバイス発見: {name}")
                    return True
            
            logger.warning(f"ターゲットデバイスが見つかりません: {mac_address}")
            return False
            
        except Exception as e:
            logger.error(f"デバイス確認エラー: {e}")
            return False

    def send_to_camera(self, uid_str):
        """BluetoothでUIDを送信"""
        try:
            logger.info(f"Bluetooth送信開始 - UID: {uid_str}")
            self.send_label.config(text="Bluetooth接続中...", foreground="blue")
            self.bluetooth_label.config(text="接続中...", foreground="orange")
            
            # Bluetooth送信実行
            send_message(uid_str)
            
            # 成功時の表示更新
            logger.info(f"Bluetooth送信完了 - UID: {uid_str}")
            self.send_label.config(text="Bluetooth送信成功", foreground="green")
            self.bluetooth_label.config(text="接続済み", foreground="green")
            
        except bluetooth.btcommon.BluetoothError as e:
            error_msg = f"Bluetooth接続エラー: {e}"
            logger.error(error_msg)
            self.send_label.config(text=error_msg, foreground="red")
            self.bluetooth_label.config(text="接続エラー", foreground="red")
        except Exception as e:
            error_msg = f"Bluetooth送信エラー: {e}"
            logger.error(error_msg)
            self.send_label.config(text=error_msg, foreground="red")
            self.bluetooth_label.config(text="送信エラー", foreground="red")

def main():
    logger.info("アプリケーション開始")
    root = tk.Tk()
    app = NFCReaderGUI(root)
    root.mainloop()
    logger.info("アプリケーション終了")

if __name__ == "__main__":
    main()
