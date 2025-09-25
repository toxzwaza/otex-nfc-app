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
import json
import os
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

def load_settings():
    """設定ファイルを読み込む"""
    try:
        settings_path = os.path.join(os.path.dirname(__file__), 'settings.json')
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        logger.info("設定ファイル読み込み完了")
        return settings
    except FileNotFoundError:
        logger.error("settings.jsonファイルが見つかりません")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"設定ファイルのJSON形式が不正です: {e}")
        logger.error("JSONファイルにコメント（//）が含まれていないか確認してください")
        return {}
    except Exception as e:
        logger.error(f"設定ファイル読み込みエラー: {e}")
        logger.error(f"詳細エラー情報: {traceback.format_exc()}")
        return {}

# 設定を読み込み
SETTINGS = load_settings()

class NFCReaderGUI:
    def __init__(self, root):
        self.root = root
        app_title = 'NFCリーダー'
        if SETTINGS and 'app' in SETTINGS:
            app_title = SETTINGS['app'].get('title', 'NFCリーダー')
        self.root.title(app_title)
        
        # アプリケーションモードの取得
        if SETTINGS and 'app' in SETTINGS:
            self.app_mode = SETTINGS['app'].get('mode', 'write')
        else:
            self.app_mode = 'write'
            logger.warning("設定ファイルが読み込めませんでした。デフォルトモード（write）を使用します")
        logger.info(f"NFCリーダーアプリケーション開始 - モード: {self.app_mode}")
        
        # 全画面表示
        fullscreen_enabled = True
        if SETTINGS and 'app' in SETTINGS:
            fullscreen_enabled = SETTINGS['app'].get('fullscreen', True)
        if fullscreen_enabled:
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
        
        bg_color = '#f0f0f0'
        if SETTINGS and 'app' in SETTINGS:
            bg_color = SETTINGS['app'].get('background_color', '#f0f0f0')
        self.root.configure(bg=bg_color)
        
        # 大きなボタンスタイルの設定
        style = ttk.Style()
        button_font_size = 12
        font_family = 'Arial'
        if SETTINGS and 'gui' in SETTINGS:
            button_font_size = SETTINGS['gui'].get('button_font_size', 12)
            font_family = SETTINGS['gui'].get('font_family', 'Arial')
        style.configure('Large.TButton', font=(font_family, button_font_size))
        
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
        padding = SETTINGS.get('gui', {}).get('padding', '20')
        main_frame = ttk.Frame(self.root, padding=padding)
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # タイトル
        title_text = SETTINGS.get('app', {}).get('window_title', 'NFCタグ読み取りシステム')
        title_font_size = SETTINGS.get('gui', {}).get('title_font_size', 24)
        font_family = SETTINGS.get('gui', {}).get('font_family', 'Arial')
        title_label = ttk.Label(main_frame, text=title_text, 
                               font=(font_family, title_font_size, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # ステータス表示
        status_frame = ttk.LabelFrame(main_frame, text="ステータス", padding="10")
        status_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        status_font_size = SETTINGS.get('gui', {}).get('status_font_size', 14)
        font_family = SETTINGS.get('gui', {}).get('font_family', 'Arial')
        self.status_label = ttk.Label(status_frame, text="初期化中...", 
                                     font=(font_family, status_font_size))
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        # 読み取り結果表示
        result_frame = ttk.LabelFrame(main_frame, text="読み取り結果", padding="10")
        result_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # UID表示
        uid_frame = ttk.Frame(result_frame)
        uid_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        font_family = SETTINGS.get('gui', {}).get('font_family', 'Arial')
        uid_font_size = SETTINGS.get('gui', {}).get('uid_font_size', 16)
        ttk.Label(uid_frame, text="UID:", font=(font_family, 12, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.uid_label = ttk.Label(uid_frame, text="---", font=('Courier', uid_font_size))
        self.uid_label.grid(row=0, column=1, sticky=tk.W, padx=(15, 0))
        
        # UIDバイト列表示
        uid_bytes_frame = ttk.Frame(result_frame)
        uid_bytes_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Label(uid_bytes_frame, text="UIDバイト列:", font=(font_family, 12, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.uid_bytes_label = ttk.Label(uid_bytes_frame, text="---", font=('Courier', 14))
        self.uid_bytes_label.grid(row=0, column=1, sticky=tk.W, padx=(15, 0))
        
        # URL表示
        url_frame = ttk.Frame(result_frame)
        url_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Label(url_frame, text="生成URL:", font=(font_family, 12, 'bold')).grid(row=0, column=0, sticky=tk.W)
        url_wrap_length = SETTINGS.get('gui', {}).get('url_wrap_length', 600)
        self.url_label = ttk.Label(url_frame, text="---", font=('Courier', 14), wraplength=url_wrap_length)
        self.url_label.grid(row=0, column=1, sticky=tk.W, padx=(15, 0))
        
        # 送信状況表示
        send_frame = ttk.Frame(result_frame)
        send_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Label(send_frame, text="送信状況:", font=(font_family, 12, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.send_label = ttk.Label(send_frame, text="---", font=(font_family, 12))
        self.send_label.grid(row=0, column=1, sticky=tk.W, padx=(15, 0))
        
        # Bluetooth接続状況表示
        bluetooth_frame = ttk.Frame(result_frame)
        bluetooth_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Label(bluetooth_frame, text="Bluetooth接続:", font=(font_family, 12, 'bold')).grid(row=0, column=0, sticky=tk.W)
        self.bluetooth_label = ttk.Label(bluetooth_frame, text="未接続", font=(font_family, 12), foreground="red")
        self.bluetooth_label.grid(row=0, column=1, sticky=tk.W, padx=(15, 0))
        
        # アプリケーションモード表示
        mode_frame = ttk.Frame(result_frame)
        mode_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(0, 0))
        
        ttk.Label(mode_frame, text="動作モード:", font=(font_family, 12, 'bold')).grid(row=0, column=0, sticky=tk.W)
        mode_text = "書込みモード" if self.app_mode == "write" else "送信モード"
        mode_color = "blue" if self.app_mode == "write" else "green"
        self.mode_label = ttk.Label(mode_frame, text=mode_text, font=(font_family, 12), foreground=mode_color)
        self.mode_label.grid(row=0, column=1, sticky=tk.W, padx=(15, 0))
        

        
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
        mode_text = "書込みモード" if self.app_mode == "write" else "送信モード"
        mode_color = "blue" if self.app_mode == "write" else "green"
        self.mode_label.config(text=mode_text, foreground=mode_color)
        self.update_status("NFCタグをかざしてください...", "info")
    
    def schedule_clear_display(self):
        """5秒後に表示をクリアするタイマーを設定"""
        # 既存のタイマーをキャンセル
        if self.clear_timer:
            self.clear_timer.cancel()
        
        # 新しいタイマーを設定
        clear_delay = SETTINGS.get('nfc', {}).get('clear_display_delay', 5.0)
        self.clear_timer = threading.Timer(clear_delay, self.clear_display)
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
                nfc_timeout = SETTINGS.get('nfc', {}).get('timeout', 1)
                try:
                    uid = self.pn532.read_passive_target(timeout=nfc_timeout)
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
                    tag_delay = SETTINGS.get('nfc', {}).get('tag_detection_delay', 2)
                    time.sleep(tag_delay)  # 次の読み取りまでの待機
                else:
                    reading_interval = SETTINGS.get('nfc', {}).get('reading_interval', 0.1)
                    time.sleep(reading_interval)  # 短い待機
                    
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
            base_url = SETTINGS.get('url', {}).get('base_url', 'https://akioka-sub.cloud/questionnaire/')
            url = f"{base_url}{uid_str}"
            logger.info(f"生成URL: {url}")
            self.url_label.config(text=url)
            self.update_status("URL生成完了", "success")
            
            # モードに応じた処理
            if self.app_mode == "write":
                # 書込みモード: NFCタグへの書き込みのみ
                logger.info("書込みモード: NFCタグへの書き込みを実行")
                self._write_to_nfc_tag(uid_str)
                self.send_label.config(text="書込みモード - Bluetooth送信はスキップ", foreground="blue")
                self.bluetooth_label.config(text="書込みモード", foreground="blue")
            else:
                # 送信モード: 書込み確認後にBluetooth送信
                logger.info("送信モード: 書込み確認とBluetooth送信を実行")
                self._check_and_write_if_needed(uid_str)
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
    
    def _check_and_write_if_needed(self, uid_str):
        """送信モードで書込みが必要かチェックして実行"""
        try:
            logger.info("送信モード: 簡易書込み確認と書込み実行")
            self.update_status("書込み確認中...", "info")
            
            # NFC初期化状態をチェック
            if not self.nfc_initialized or self.pn532 is None:
                logger.warning("NFCが初期化されていないため、書込み確認をスキップします")
                return
            
            # 簡易的な書込み確認（最初の数ページのみ）
            try:
                # タグがまだ読み取れるか確認
                current_uid = self.pn532.read_passive_target(timeout=0.3)
                if current_uid is None:
                    logger.warning("タグが検出されません。書込みを実行します")
                    self.update_status("書込み実行中...", "info")
                    self._write_to_nfc_tag(uid_str)
                    return
                
                # 最初のデータページ（ページ4）のみをチェック
                try:
                    test_data = self._safe_read_block(4)
                    if test_data and len(test_data) >= 4:
                        # データが存在する場合、簡単なURLチェック
                        data_str = bytes(test_data).decode('utf-8', errors='ignore')
                        base_url = 'https://akioka-sub.cloud/questionnaire/'
                        if SETTINGS and 'url' in SETTINGS:
                            base_url = SETTINGS['url'].get('base_url', 'https://akioka-sub.cloud/questionnaire/')
                        
                        if base_url.split('//')[1] in data_str:  # ドメイン部分のみチェック
                            logger.info("タグにURLが書き込まれている可能性があります。書込みをスキップします")
                            self.update_status("書込み済み - 送信準備完了", "success")
                            return
                except Exception as check_error:
                    logger.debug(f"書込み確認エラー: {check_error}")
                
                # 書込みを実行
                logger.info("タグにURLが書き込まれていません。書込みを実行します")
                self.update_status("書込み実行中...", "info")
                self._write_to_nfc_tag(uid_str)
                
            except Exception as read_error:
                logger.warning(f"書込み確認エラー: {read_error}")
                logger.info("書込みを実行します")
                self.update_status("書込み実行中...", "info")
                self._write_to_nfc_tag(uid_str)
                
        except Exception as e:
            logger.warning(f"書込み確認エラー: {e}")
            logger.info("書込みを実行します")
            self.update_status("書込み実行中...", "info")
            self._write_to_nfc_tag(uid_str)
    
    def _safe_write_block(self, page, block):
        """安全なブロック書き込み処理"""
        try:
            # 複数回試行して書き込み
            for attempt in range(3):
                try:
                    # タグが検出されるか確認
                    uid = self.pn532.read_passive_target(timeout=0.2)
                    if uid is None:
                        logger.debug(f"ページ {page} 書き込み試行 {attempt + 1}/3: タグが検出されません")
                        time.sleep(0.1)
                        continue
                    
                    # ブロック書き込み実行
                    result = self.pn532.ntag2xx_write_block(page, block)
                    
                    # 結果の検証
                    if result is None:
                        logger.debug(f"ページ {page} 書き込み試行 {attempt + 1}/3: 結果がNone")
                        time.sleep(0.1)
                        continue
                    elif not isinstance(result, bool):
                        logger.debug(f"ページ {page} 書き込み試行 {attempt + 1}/3: 結果の型が不正: {type(result)}")
                        time.sleep(0.1)
                        continue
                    else:
                        logger.debug(f"ページ {page} 書き込み成功（試行 {attempt + 1}/3）: {result}")
                        return result
                        
                except Exception as write_error:
                    logger.debug(f"ページ {page} 書き込み試行 {attempt + 1}/3 エラー: {write_error}")
                    time.sleep(0.1)
                    continue
            
            logger.debug(f"ページ {page} 書き込み失敗: 3回の試行すべて失敗")
            return None
            
        except Exception as e:
            logger.debug(f"ページ {page} 安全書き込みエラー: {e}")
            return None

    def _safe_read_block(self, page):
        """安全なブロック読み取り処理"""
        try:
            # 複数回試行して読み取り
            for attempt in range(3):
                try:
                    # タグが検出されるか確認
                    uid = self.pn532.read_passive_target(timeout=0.2)
                    if uid is None:
                        logger.debug(f"ページ {page} 読み取り試行 {attempt + 1}/3: タグが検出されません")
                        time.sleep(0.1)
                        continue
                    
                    # ブロック読み取り実行
                    result = self.pn532.ntag2xx_read_block(page)
                    
                    # 結果の検証
                    if result is None:
                        logger.debug(f"ページ {page} 読み取り試行 {attempt + 1}/3: 結果がNone")
                        time.sleep(0.1)
                        continue
                    elif not isinstance(result, (list, tuple)):
                        logger.debug(f"ページ {page} 読み取り試行 {attempt + 1}/3: 結果の型が不正: {type(result)}")
                        time.sleep(0.1)
                        continue
                    elif len(result) < 4:
                        logger.debug(f"ページ {page} 読み取り試行 {attempt + 1}/3: データ長が不足: {len(result)}")
                        time.sleep(0.1)
                        continue
                    else:
                        logger.debug(f"ページ {page} 読み取り成功（試行 {attempt + 1}/3）")
                        return result
                        
                except Exception as read_error:
                    logger.debug(f"ページ {page} 読み取り試行 {attempt + 1}/3 エラー: {read_error}")
                    time.sleep(0.1)
                    continue
            
            logger.debug(f"ページ {page} 読み取り失敗: 3回の試行すべて失敗")
            return None
            
        except Exception as e:
            logger.debug(f"ページ {page} 安全読み取りエラー: {e}")
            return None

    def _extract_url_from_ndef(self, ndef_data, expected_url):
        """NDEFデータからURLを抽出して期待値と比較"""
        try:
            if not ndef_data:
                return False
            
            # NDEFデータを文字列に変換
            ndef_str = ndef_data.decode('utf-8', errors='ignore')
            
            # 期待するURLが含まれているかチェック
            if expected_url in ndef_str:
                logger.info(f"期待するURLが見つかりました: {expected_url}")
                return True
            
            # 部分的なURLマッチングも試行
            url_parts = expected_url.split('/')
            if len(url_parts) >= 3:
                domain_part = '/'.join(url_parts[:3])  # https://domain.com 部分
                if domain_part in ndef_str:
                    logger.info(f"ドメイン部分が一致しました: {domain_part}")
                    return True
            
            logger.info(f"期待するURLが見つかりませんでした。期待値: {expected_url}")
            return False
            
        except Exception as e:
            logger.warning(f"URL抽出エラー: {e}")
            return False

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
            
            base_url = 'https://akioka-sub.cloud/questionnaire/'
            if SETTINGS and 'url' in SETTINGS:
                base_url = SETTINGS['url'].get('base_url', 'https://akioka-sub.cloud/questionnaire/')
            
            url = f"{base_url}{uid_str}"
            uri_body = url.replace("https://", "").encode('utf-8')
            
            ndef_record = b'\xD1\x01' + bytes([len(uri_body) + 1]) + b'\x55\x04' + uri_body
            tlv = b'\x03' + bytes([len(ndef_record)]) + ndef_record + b'\xFE'
            
            data = list(tlv) + [0x00] * (144 - len(tlv))
            
            logger.info(f"NFCタグ書き込み開始 - URL: {url}")
            
            # タグがまだ読み取れるか確認（簡易版）
            try:
                current_uid = self.pn532.read_passive_target(timeout=0.2)
                if current_uid is None:
                    logger.warning("タグが検出されません。書き込みをスキップします")
                    return
                logger.info("タグが検出されました。書き込みを続行します")
            except Exception as tag_check_error:
                logger.warning(f"タグ状態確認エラー: {tag_check_error}")
                logger.info("書き込みを続行します")
            
            # 書き込み処理を安全に実行
            successful_writes = 0
            total_pages = len(data) // 4
            
            for i in range(0, len(data), 4):
                page = 4 + i // 4
                block = data[i:i+4]
                if len(block) < 4:
                    block += [0x00] * (4 - len(block))
                
                # 書き込み前にタグの状態を確認（簡易版）
                if i > 0 and i % 20 == 0:  # 5ページごとにタグ確認
                    try:
                        check_uid = self.pn532.read_passive_target(timeout=0.1)
                        if check_uid is None:
                            logger.warning(f"ページ {page} 書き込み前にタグが検出されません")
                            # タグが離れていても書き込みを継続
                    except Exception as check_error:
                        logger.debug(f"タグ確認エラー: {check_error}")
                
                try:
                    # 安全な書き込み実行
                    result = self._safe_write_block(page, block)
                    if result is None:
                        logger.warning(f"ページ {page} の書き込みでレスポンスがNoneでした")
                        continue
                    elif not result:
                        logger.warning(f"ページ {page} の書き込みが失敗しました")
                        continue
                    else:
                        successful_writes += 1
                        logger.debug(f"ページ {page} の書き込み成功 ({successful_writes}/{total_pages})")
                        
                except Exception as write_error:
                    logger.error(f"ページ {page} の書き込みでエラー: {write_error}")
                    # 個別のページ書き込みエラーは継続
                    continue
                
                # 書き込み間隔を短縮して高速処理
                time.sleep(0.005)
            
            logger.info(f"書き込み完了: {successful_writes}/{total_pages} ページ成功")
            
            # 書き込み後の検証
            if successful_writes > 0:
                logger.info("書き込み検証を実行中...")
                try:
                    # 少し待ってから検証
                    time.sleep(0.5)
                    
                    # タグがまだ検出されるか確認
                    verify_uid = self.pn532.read_passive_target(timeout=0.5)
                    if verify_uid is not None:
                        logger.info("書き込み後もタグが検出されました。書き込み成功の可能性が高いです")
                        
                        # NDEFデータの一部を読み取って検証
                        try:
                            test_page = 4  # 最初のデータページ
                            test_data = self._safe_read_block(test_page)
                            if test_data and len(test_data) >= 4:
                                logger.info(f"書き込み検証: ページ {test_page} のデータ読み取り成功")
                            else:
                                logger.warning("書き込み検証: データ読み取り失敗")
                        except Exception as verify_error:
                            logger.warning(f"書き込み検証エラー: {verify_error}")
                    else:
                        logger.warning("書き込み後、タグが検出されませんでした")
                        
                except Exception as verify_error:
                    logger.warning(f"書き込み検証でエラー: {verify_error}")
            
            logger.info("NFCタグ書き込み処理完了")
            
        except Exception as e:
            logger.error(f"NFCタグ書き込みエラー: {e}")
            logger.error(f"詳細エラー情報: {traceback.format_exc()}")
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
            # UIDの頭に設定されたプレフィックスを追加して送信元を識別可能にする
            sender_id = '[1:]'
            if SETTINGS and 'bluetooth' in SETTINGS:
                sender_id = SETTINGS['bluetooth'].get('sender_id', '[1:]')
            message_with_prefix = f"{sender_id}{uid_str}"
            logger.info(f"Bluetooth送信開始 - UID: {uid_str}, 送信メッセージ: {message_with_prefix}")
            self.send_label.config(text="Bluetooth接続中...", foreground="blue")
            self.bluetooth_label.config(text="接続中...", foreground="orange")
            
            # Bluetooth送信実行
            send_message(message_with_prefix)
            
            # 成功時の表示更新
            logger.info(f"Bluetooth送信完了 - UID: {uid_str}, 送信メッセージ: {message_with_prefix}")
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
