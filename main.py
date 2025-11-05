import sys
import os
import re
import subprocess
import threading
import json
from datetime import timedelta
import shutil

# --- ▼▼▼【macOS 修正】 PyInstaller用 ヘルパー関数 ▼▼▼ ---
def get_base_path():
    """ PyInstaller実行時にリソースへのパスを正しく取得する """
    if getattr(sys, 'frozen', False):
        # PyInstallerによって .app にバンドルされている場合
        # _MEIPASS は一時展開先のルートを指す
        return sys._MEIPASS
    else:
        # 通常のPythonスクリプト (.py) として実行中
        # スクリプトがあるディレクトリを基準にする
        return os.path.dirname(os.path.abspath(__file__))

def get_platform_specific_path(program_name):
    """
    プラットフォームに応じて、実行ファイルのパスを検索する
    """
    base_path = get_base_path()
    
    if sys.platform == "darwin":
        # macOS: .app バンドル内のリソースパス (pyinstallerで --add-data "bin/ffmpeg:." とした場合)
        bundled_path = os.path.join(base_path, program_name)
        if os.path.exists(bundled_path):
            os.chmod(bundled_path, 0o755) # 実行権限を付与
            return bundled_path
        # 開発用のローカルパス
        local_path = os.path.join(base_path, "bin_macos", program_name)
        if os.path.exists(local_path):
             os.chmod(local_path, 0o755) # 実行権限を付与
             return local_path
            
    elif sys.platform == "win32":
        # Windows: .exe
        exe_name = f"{program_name}.exe"
        # .exe バンドル内のパス
        bundled_path = os.path.join(base_path, exe_name)
        if os.path.exists(bundled_path):
            return bundled_path
        # 開発用のローカルパス
        local_path = os.path.join(base_path, exe_name)
        if os.path.exists(local_path):
            return local_path

    # システムPATHからのフォールバック
    system_path = shutil.which(program_name)
    if system_path:
        return system_path
        
    return None # 見つからない

# --- ▲▲▲【macOS 修正】ここまで ▲▲▲ ---

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGridLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QListWidget,
    QVBoxLayout, QFrame, QFileDialog,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsProxyWidget, QFontComboBox, QSpinBox, QColorDialog,
    QHBoxLayout, QSlider, QComboBox,
    QGraphicsTextItem, QToolButton, QSizePolicy,
    QScrollArea
)
from PySide6.QtGui import (
    QPixmap, QCursor, QImage, QPainter, QFont, QColor,
    QTextOption, QPen
)
from PySide6.QtCore import Qt, QObject, Signal, QRunnable, QThreadPool, QPointF, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

# --- スタイルシート ---
STYLE_SHEET = """
    QWidget {
        background-color: #1e1e1e;
        color: #cccccc;
        font-family: 'Segoe UI', Meiryo, sans-serif;
    }
    QMainWindow {
        background-color: #101010;
    }
    QFrame, QScrollArea#settings-scroll-area {
        background-color: #2a2a2a;
        border: 1px solid #101010;
        border-radius: 4px;
    }
    QLabel#panel-header {
        background-color: #3c3c3c;
        font-weight: bold;
        padding: 8px 12px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }
    QPushButton {
        background-color: #4a90e2;
        color: white;
        border: none;
        padding: 8px 15px;
        border-radius: 3px;
    }
    QPushButton:hover {
        background-color: #5aa1f2;
    }
    QPushButton:disabled {
        background-color: #555555;
    }
    QPushButton#encode-button {
        background-color: #50e3c2;
    }
    QPushButton#encode-button:hover {
        background-color: #61f4d3;
    }
    QPushButton#burn-button {
        background-color: #f5a623;
    }
    QPushButton#burn-button:hover {
        background-color: #f7b74e;
    }
    QToolButton {
        background-color: #3c3c3c;
        color: white;
        border: 1px solid #1e1e1e;
        padding: 4px 8px;
        border-radius: 3px;
        font-weight: bold;
    }
    QToolButton:checked {
        background-color: #5aa1f2;
        border: 1px solid #4a90e2;
    }
    QLineEdit, QTextEdit, QListWidget, QFontComboBox, QSpinBox, QComboBox {
        background-color: #1e1e1e;
        border: 1px solid #3c3c3c;
        padding: 2px;
    }
    QVideoWidget {
        background-color: black;
    }
    QSlider::groove:horizontal {
        border: 1px solid #3c3c3c;
        height: 8px;
        background: #1e1e1e;
        margin: 2px 0;
        border-radius: 4px;
    }
    QSlider::handle:horizontal {
        background: #4a90e2;
        border: 1px solid #5aa1f2;
        width: 16px;
        margin: -4px 0;
        border-radius: 8px;
    }
    QSlider::sub-page:horizontal {
        background: #5aa1f2;
        border-radius: 4px;
    }
"""

# --- アスペクト比固定 QGraphicsView ---
class AspectRatioGraphicsView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.aspect_ratio = 16.0 / 9.0
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def heightForWidth(self, width):
        return int(width / self.aspect_ratio)

    def hasHeightForWidth(self):
        return True

    def resizeEvent(self, event):
        if self.scene():
            self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        super().resizeEvent(event)


# --- アスペクト比固定 QVideoWidget ---
class AspectRatioVideoWidget(QVideoWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.aspect_ratio = 16.0 / 9.0
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio) 

    def heightForWidth(self, width):
        return int(width / self.aspect_ratio)

    def hasHeightForWidth(self):
        return True


# --- ドラッグ可能なプロキシウィジェット ---
class DraggableProxyWidget(QGraphicsProxyWidget):
    clicked = Signal(QGraphicsProxyWidget)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlag(QGraphicsProxyWidget.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self._is_resizing = False
        self._resize_margin = 20
        self._start_mouse_pos = QPointF(0, 0)
        self._start_size = None
        self._is_moving = False
        self._mouse_press_pos_scene = QPointF(0, 0)
        self._start_pos = QPointF(0, 0)

    def hoverMoveEvent(self, event):
        pos = event.pos()
        if self.size().width() - self._resize_margin < pos.x() and self.size().height() - self._resize_margin < pos.y():
            self.setCursor(QCursor(Qt.SizeFDiagCursor))
        else:
            self.setCursor(QCursor(Qt.OpenHandCursor))
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        self.clicked.emit(self) 
        pos = event.pos()

        if self.size().width() - self._resize_margin < pos.x() and self.size().height() - self._resize_margin < pos.y():
            self._is_resizing = True
            self._start_mouse_pos = event.pos()
            self._start_size = self.size()
            self._is_moving = False
        else:
            self._is_resizing = False
            self._is_moving = True
            self.setCursor(QCursor(Qt.ClosedHandCursor))
            self._start_pos = self.pos()
            self._mouse_press_pos_scene = event.scenePos()

    def mouseMoveEvent(self, event):
        if self._is_resizing:
            delta = event.pos() - self._start_mouse_pos
            new_width = self._start_size.width() + delta.x()
            new_height = self._start_size.height() + delta.y()
            if new_width > 20 and new_height > 20:
                self.resize(new_width, new_height)
        elif self._is_moving:
            delta = event.scenePos() - self._mouse_press_pos_scene
            self.setPos(self._start_pos + delta)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._is_resizing = False
        self._is_moving = False
        self.setCursor(QCursor(Qt.ArrowCursor))

# --- ドラッグ可能なテキストアイテム ---
class DraggableTextItem(QGraphicsTextItem):
    clicked = Signal(QGraphicsTextItem)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlag(QGraphicsTextItem.ItemIsMovable)
        self.setFlag(QGraphicsTextItem.ItemSendsGeometryChanges)
        self.setFlag(QGraphicsTextItem.ItemIsSelectable)
        self._is_moving = False
        self._mouse_press_pos = QPointF(0, 0)
        self._start_pos = QPointF(0, 0)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

    def mousePressEvent(self, event):
        self.clicked.emit(self)
        self._is_moving = True
        self.setCursor(QCursor(Qt.ClosedHandCursor))
        self._start_pos = self.pos()
        self._mouse_press_pos = event.scenePos()

    def mouseMoveEvent(self, event):
        if self._is_moving:
            delta = event.scenePos() - self._mouse_press_pos
            self.setPos(self._start_pos + delta)

    def mouseReleaseEvent(self, event):
        self._is_moving = False
        self.setCursor(QCursor(Qt.ArrowCursor))

    def mouseDoubleClickEvent(self, event):
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event):
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setCursor(QCursor(Qt.ArrowCursor))
        super().focusOutEvent(event)

# --- グリッド線描画シーン ---
class GridGraphicsScene(QGraphicsScene):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.grid_size = 50
        self._grid_pen = QPen(QColor(85, 85, 85, 127))
        self._grid_pen.setWidth(1)
        self.show_grid = True

    def drawForeground(self, painter, rect):
        if not self.show_grid:
            return
        super().drawForeground(painter, rect)
        scene_rect = self.sceneRect()
        left = int(scene_rect.left())
        right = int(scene_rect.right())
        top = int(scene_rect.top())
        bottom = int(scene_rect.bottom())
        first_x = left - (left % self.grid_size)
        first_y = top - (top % self.grid_size)
        painter.setPen(self._grid_pen)
        for x in range(first_x, right, self.grid_size):
            painter.drawLine(x, top, x, bottom)
        for y in range(first_y, bottom, self.grid_size):
            painter.drawLine(left, y, right, y)

# --- バックグラウンド処理のためのWorker ---
class WorkerSignals(QObject):
    finished = Signal(str)
    error = Signal(str)
    log = Signal(str)

# --- メニュー動画エンコード用Worker (MKV出力) ---
class MenuEncoderWorker(QRunnable):
    def __init__(self, image_path, duration_sec, resolution_fps, ffmpeg_path):
        super().__init__()
        self.signals = WorkerSignals()
        self.image_path = image_path
        self.duration_sec = duration_sec
        self.resolution_fps = resolution_fps
        self.ffmpeg_path = ffmpeg_path

    def run(self):
        if not self.ffmpeg_path:
             self.signals.error.emit("ffmpeg実行ファイルが見つかりませんでした。")
             return
        try:
            image_path_normalized = self.image_path.replace('\\', '/')
            output_dir = os.path.dirname(image_path_normalized)
            output_path = os.path.join(output_dir, "menu.mkv").replace('\\', '/') # ★ .mkv

            res, fps_val = "1920x1080", "23.976" 
            if self.resolution_fps:
                res_part, fps_part_str = self.resolution_fps.split(':')
                if res_part: res = res_part
                
                if fps_part_str:
                    if fps_part_str == "60": fps_val = "59.94"
                    elif fps_part_str == "30": fps_val = "29.97"
                    elif "24000/1001" in fps_part_str: fps_val = "24000/1001"
                    else: fps_val = fps_part_str
            
            command = [
                self.ffmpeg_path,
                '-loop', '1', '-i', image_path_normalized, 
                '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000', 
                '-c:v', 'libx264', '-preset', 'medium', 
                '-profile:v', 'high', 
                '-b:v', '25000k',       
                '-maxrate', '40000k',   
                '-bufsize', '30000k',   
                '-level', '4.1',        
                '-bsf:v', 'h264_metadata=aud=insert',
                '-c:a', 'ac3', '-b:a', '448k', 
                '-t', str(self.duration_sec), 
                '-r', fps_val, 
                '-vsync', '1',
                '-vf', f'scale={res}:out_color_matrix=bt709,format=yuv420p',
                '-color_range', 'tv',
                '-colorspace', 'bt709',
                '-color_primaries', 'bt709',
                '-color_trc', 'bt709',
                '-metadata:s:a:0', 'language=und', 
                '-map_metadata', '-1', 
                '-y', output_path
            ]

            self.signals.log.emit(f"メニュー動画エンコード ({self.duration_sec}秒) を開始します...")
            self.signals.log.emit(f"コマンド: {' '.join(command)}")
            
            creation_flags = 0
            if sys.platform == 'win32':
                creation_flags = subprocess.CREATE_NO_WINDOW
            
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                       universal_newlines=True, encoding='utf-8', 
                                       creationflags=creation_flags)

            for line in process.stdout:
                self.signals.log.emit(line.strip())
            process.wait()

            if process.returncode == 0:
                self.signals.finished.emit(output_path)
            else:
                error_cmd = ' '.join(command)
                raise subprocess.CalledProcessError(process.returncode, error_cmd)
        except Exception as e:
            self.signals.error.emit(f"メニュー動画エンコード失敗: {str(e)}")

# --- 本編エンコード用Worker (MKV出力 / エンコーダ統一解除) ---
class EncoderWorker(QRunnable):
    def __init__(self, video_path, chapters, encoder, resolution_fps, ffmpeg_path):
        super().__init__()
        self.signals = WorkerSignals()
        self.video_path = video_path
        self.chapters = chapters
        self.encoder_option = encoder 
        self.resolution_fps = resolution_fps 
        self.ffmpeg_path = ffmpeg_path

    def run(self):
        if not self.ffmpeg_path:
             self.signals.error.emit("ffmpeg実行ファイルが見つかりませんでした。")
             return
        try:
            video_path_normalized = self.video_path.replace('\\', '/')
            output_dir = os.path.dirname(video_path_normalized)
            output_path = os.path.join(output_dir, f"encoded_video.mkv").replace('\\', '/') # ★ .mkv
            
            scale_filter = ""
            fps_option = []
            fps_val = "" 
            
            if self.resolution_fps and self.resolution_fps != "original":
                res, fps_part_str = self.resolution_fps.split(':')
                pad_res = res.replace('x', ':') 
                scale_filter = f"scale={res}:force_original_aspect_ratio=decrease,pad={pad_res}:(ow-iw)/2:(oh-ih)/2"
                if fps_part_str:
                    if fps_part_str == "60": fps_val = "59.94"
                    elif fps_part_str == "30": fps_val = "29.97"
                    elif "24000/1001" in fps_part_str: fps_val = "24000/1001"
                    else: fps_val = fps_part_str 
                fps_option = ['-r', fps_val] if fps_val else []
            
            elif self.resolution_fps == "original":
                self.signals.log.emit("解像度とフレームレートをオリジナルから維持します。")
                scale_filter = "" 
                fps_option = []
                video_info = self.get_video_info_internal(video_path_normalized)
                if not video_info:
                    self.signals.log.emit("警告: 'original'のFPSが取得できません。")

            final_encoder = self.encoder_option 
            
            command = [
                self.ffmpeg_path,
                '-i', video_path_normalized, 
                '-map_metadata', '-1', 
                '-map', '0:v:0', '-map', '0:a:0', 
            ]
            if scale_filter: command.extend(['-vf', scale_filter])
            command.extend(fps_option) 

            command.extend(['-c:v', final_encoder, '-preset', 'medium'])
            
            if final_encoder == "libx264":
                 command.extend(['-profile:v', 'high'])

            command.extend([
                '-b:v', '25000k',
                '-maxrate', '40000k',
                '-bufsize', '30000k',
                '-level', '4.1',
            ])
            
            command.extend([
                '-pix_fmt', 'yuv420p',
                '-bsf:v', 'h264_metadata=aud=insert',
                '-c:a', 'ac3', '-b:a', '448k',
                '-ar', '48000',
                '-metadata:s:a:0', 'language=und', 
                '-y', output_path
            ])
            
            self.signals.log.emit(f"FFmpeg本編エンコード({final_encoder}, {self.resolution_fps})を開始します...")
            self.signals.log.emit(f"コマンド: {' '.join(command)}")
            
            creation_flags = 0
            if sys.platform == 'win32':
                creation_flags = subprocess.CREATE_NO_WINDOW
            
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                       universal_newlines=True, encoding='utf-8', 
                                       creationflags=creation_flags)

            for line in process.stdout:
                self.signals.log.emit(line.strip())
            process.wait()
            
            if process.returncode == 0:
                self.signals.finished.emit(output_path)
            else:
                error_cmd = ' '.join(command)
                raise subprocess.CalledProcessError(process.returncode, error_cmd)
        except Exception as e:
            self.signals.error.emit(str(e))

    def get_video_info_internal(self, video_path):
        ffprobe_path = get_platform_specific_path("ffprobe")
        if not ffprobe_path:
            self.signals.log.emit("ffprobe が見つからないため、'original' FPS を特定できません。")
            return None
        
        command = [ ffprobe_path, '-v', 'quiet', '-print_format', 'json', '-show_streams', '-select_streams', 'v:0', video_path ]
        try:
            creation_flags = 0
            if sys.platform == 'win32':
                creation_flags = subprocess.CREATE_NO_WINDOW
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                       universal_newlines=True, encoding='utf-8', 
                                       creationflags=creation_flags)
            stdout, stderr = process.communicate(timeout=10)
            if process.returncode != 0: return None
            data = json.loads(stdout)
            if 'streams' not in data or not data['streams']: return None
            stream = data['streams'][0]
            width = stream.get('width')
            height = stream.get('height')
            resolution_str = f"{width}x{height}"
            fps_eval = 0.0
            fps_str = stream.get('r_frame_rate')
            if '/' in fps_str:
                num, den = map(float, fps_str.split('/'))
                if den != 0: fps_eval = num / den
            if fps_eval == 0.0 or fps_eval.is_integer():
                avg_fps_str = stream.get('avg_frame_rate', '0/1')
                if '/' in avg_fps_str:
                    num, den = map(float, avg_fps_str.split('/'))
                    if den != 0 and (num/den) != fps_eval:
                        fps_str = avg_fps_str
                        fps_eval = num / den
            if 23.9 < fps_eval < 24.1: fps_bd_str = "24000/1001"
            elif 29.9 < fps_eval < 30.1: fps_bd_str = "29.97"
            elif 59.9 < fps_eval < 60.1: fps_bd_str = "59.94"
            else: fps_bd_str = fps_str if "/" in fps_str else f"{int(fps_eval * 1000)}/1000"
            return (resolution_str, fps_bd_str, fps_eval)
        except Exception as e:
            self.signals.log.emit(f"ffprobe (internal) 失敗: {e}")
            return None


# --- tsMuxeR オーサリング用Worker ---
class AuthoringWorker(QRunnable):
    def __init__(self, tsmuxer_path, meta_path, output_path):
        super().__init__()
        self.signals = WorkerSignals()
        self.tsmuxer_path = tsmuxer_path
        self.meta_path = meta_path
        self.output_path = output_path 
    def run(self):
        try:
            if os.path.exists(self.output_path):
                self.signals.log.emit(f"既存のISOファイルを削除中: {self.output_path}")
                try:
                    os.remove(self.output_path)
                except Exception as e:
                    self.signals.log.emit(f"警告: 既存ISOの削除に失敗: {e}。続行します。")

            command = [self.tsmuxer_path, self.meta_path, self.output_path]
            self.signals.log.emit("tsMuxeRによるオーサリング (ISO生成) を開始します...")
            self.signals.log.emit(f"コマンド: {' '.join(command)}")
            
            creation_flags = 0
            if sys.platform == 'win32':
                creation_flags = subprocess.CREATE_NO_WINDOW
            
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                       universal_newlines=True, encoding='utf-8', 
                                       creationflags=creation_flags)

            for line in process.stdout:
                self.signals.log.emit(line.strip())
            process.wait()
            
            if os.path.exists(self.meta_path):
                 os.remove(self.meta_path)

            if process.returncode == 0:
                self.signals.finished.emit(self.output_path)
            else:
                raise subprocess.CalledProcessError(process.returncode, command)
        except Exception as e:
            if os.path.exists(self.meta_path):
                 os.remove(self.meta_path)
            self.signals.error.emit(f"tsMuxeRの実行に失敗しました: {e}")

# --- 書き込み用Worker ---
class BurnerWorker(QRunnable):
    def __init__(self, iso_path, drive_id):
        super().__init__()
        self.signals = WorkerSignals()
        self.iso_path = iso_path
        self.drive_id = drive_id

    def run(self):
        try:
            command = []
            if sys.platform == "win32":
                if not self.drive_id:
                    self.signals.error.emit("Windowsでは書き込みドライブ（E:など）の指定が必要です。")
                    return
                
                if not self.iso_path.lower().endswith(".iso"):
                    self.signals.error.emit(f"書き込みエラー: ISOファイルが見つかりません。")
                    return
                command = ['isoburn.exe', '/Q', self.drive_id, self.iso_path]
            elif sys.platform == "darwin":
                 if not self.drive_id:
                    self.signals.error.emit("macOSでは書き込みドライブ（disk2など）の指定が必要です。")
                    return
                 command = ['drutil', 'burn', '-device', self.drive_id, self.iso_path]
            else:
                self.signals.error.emit(f"サポートされていないOSです: {sys.platform}")
                return

            self.signals.log.emit(f"{sys.platform}用の書き込みコマンドを実行します...")
            self.signals.log.emit(f"コマンド: {' '.join(command)}")
            
            creation_flags = 0
            if sys.platform == 'win32':
                creation_flags = subprocess.CREATE_NO_WINDOW
            
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                       universal_newlines=True, encoding='utf-8', 
                                       creationflags=creation_flags)

            for line in process.stdout:
                self.signals.log.emit(line.strip())
            process.wait()

            if process.returncode == 0:
                self.signals.finished.emit(self.iso_path)
            else:
                raise subprocess.CalledProcessError(process.returncode, command)
        except Exception as e:
            self.signals.error.emit(f"書き込みに失敗しました: {e}")


# --- メインウィンドウ ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_video_path = ""
        self.background_image_path = ""
        self.encoded_video_path = None
        self.generated_iso_path = None 
        self.menu_video_path = None
        self.menu_duration_sec = 10.0
        self.original_video_info = None 
        self.chapters = []
        self.threadpool = QThreadPool()
        self.menu_buttons = []
        self.title_item = None
        self.selected_item = None
        self.default_button_font_family = "Arial"
        self.default_button_font_size = 50
        self.default_button_font_color = "#ffffff"
        self.default_title_font_family = "Impact"
        self.default_title_font_size = 72
        self.default_title_font_color = "#ffff00"
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self.update_timecode)
        self.player.durationChanged.connect(self.update_timecode)
        self.setWindowTitle("BDメニュー作成・書き込みソフト (Qt版)")
        self.setGeometry(50, 50, 1920, 1080)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        grid_layout = QGridLayout(main_widget)
        grid_layout.setSpacing(5)
        grid_layout.setContentsMargins(5, 5, 5, 5)

        video_panel = self.create_video_panel()
        grid_layout.addWidget(video_panel, 0, 0)
        preview_panel = self.create_preview_panel()
        grid_layout.addWidget(preview_panel, 0, 1)
        project_panel = self.create_project_panel()
        grid_layout.addWidget(project_panel, 1, 0)
        log_panel = self.create_log_panel()
        grid_layout.addWidget(log_panel, 2, 0)
        settings_panel = self.create_settings_panel()
        grid_layout.addWidget(settings_panel, 1, 1, 2, 1)

        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)
        grid_layout.setRowStretch(0, 15)
        grid_layout.setRowStretch(1, 4)
        grid_layout.setRowStretch(2, 2)

        self.populate_drive_list()

    def log_message(self, message):
        self.log_output.append(message)

    def menu_encoding_finished(self, output_path):
        self.log_output.append("\n🎉 メニュー動画のエンコードが正常に完了しました！")
        self.log_output.append(f"出力ファイル: {output_path}")
        self.menu_video_path = output_path
        self.check_all_encoding_finished() 

    def encoding_finished(self, output_path):
        self.log_output.append("\n🎉 本編動画のエンコードが正常に完了しました！")
        self.log_output.append(f"出力ファイル: {output_path}")
        self.encoded_video_path = output_path
        self.check_all_encoding_finished() 

    def check_all_encoding_finished(self):
        if self.menu_video_path and self.encoded_video_path:
            self.log_message("\n--- メニューと本編のエンコードが両方完了しました ---")
            self.start_muxing_process() 
        else:
            if not self.menu_video_path:
                self.log_message("...本編エンコード完了、メニュー動画エンコード待機中...")
            if not self.encoded_video_path:
                self.log_message("...メニュー動画エンコード完了、本編エンコード待機中...")
    
    def authoring_finished(self, output_path):
        self.log_output.append("\n✅ BD ISOイメージの生成が正常に完了しました！")
        self.log_output.append(f"出力先ISO: {output_path}")
        self.generated_iso_path = output_path 
        self.toggle_ui_elements(True) 
        
        try:
            if os.path.exists(self.menu_video_path): os.remove(self.menu_video_path)
            if os.path.exists(self.encoded_video_path): os.remove(self.encoded_video_path)
            self.log_message("一時エンコードファイル (menu.mkv, encoded_video.mkv) を削除しました。")
        except Exception as e:
            self.log_message(f"警告: 一時ファイルの削除に失敗: {e}")

    def burning_finished(self, iso_path):
        self.log_output.append(f"\n🎉 ディスクへの書き込みが正常に完了しました！ (ISO: {iso_path})")
        self.toggle_ui_elements(True) 

    def encoding_error(self, error_message):
        self.log_output.append(f"\n❌ 処理中にエラーが発生しました:\n{error_message}")
        self.toggle_ui_elements(True)

    def toggle_ui_elements(self, enabled):
        self.select_file_button.setEnabled(enabled)
        self.select_bg_button.setEnabled(enabled)
        self.add_chapter_button.setEnabled(enabled)
        self.delete_chapter_button.setEnabled(enabled)
        self.author_button.setEnabled(enabled)
        self.save_layout_button.setEnabled(enabled)
        self.load_layout_button.setEnabled(enabled)
        self.burn_button.setEnabled(enabled and self.generated_iso_path is not None) 

    def update_timecode(self, position):
        duration = self.player.duration()
        if duration == 0: return
        if self.seek_slider.maximum() != duration:
             self.seek_slider.setMaximum(duration)
        if not self.seek_slider.isSliderDown():
            self.seek_slider.setValue(position)
        pos_str = self.format_time(position)
        dur_str = self.format_time(duration)
        self.timecode_label.setText(f"{pos_str} / {dur_str}")

    def set_video_position(self, position):
        self.player.setPosition(position)
        
    def format_time(self, ms):
        s = ms // 1000
        h = s // 3600
        m = (s % 3600) // 60
        s = s % 60
        return f"{h:02}:{m:02}:{s:02}"

    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "動画ファイルを選択", "", "Video Files (*.mp4 *.mkv *.mov);;All Files (*)")
        if file_path:
            self.selected_video_path = file_path
            short_path = "..." + file_path[-40:] if len(file_path) > 40 else file_path
            self.file_path_label.setText(f"選択中: {short_path}")
            self.log_message(f"動画ファイルが選択されました: {file_path}")
            
            self.original_video_info = self.get_video_info(file_path)
            if self.original_video_info:
                res, fps_str, fps_float = self.original_video_info
                self.resolution_combo_box.setItemText(0, f"オリジナル ({res}, {fps_float:.2f} fps)")
            else:
                self.log_message("警告: オリジナル動画の情報を取得できませんでした。")
                self.resolution_combo_box.setItemText(0, "オリジナル (情報取得失敗)")
            
            self.player.setSource(QUrl.fromLocalFile(file_path))
            self.play_button.setEnabled(True)
            self.skip_button.setEnabled(True)
            self.rewind_button.setEnabled(True)
            self.seek_slider.setEnabled(True)

    def open_background_image_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "背景画像を選択", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.background_image_path = file_path
            self.set_background_image(file_path)

    def set_background_image(self, file_path):
        self.scene.clear() 
        self.menu_buttons.clear()
        self.title_item = None
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            bg_item = QGraphicsPixmapItem()
            scaled_pixmap = pixmap.scaled(int(self.scene.width()), int(self.scene.height()),
                                          Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                          Qt.TransformationMode.SmoothTransformation)
            bg_item.setPixmap(scaled_pixmap)
            bg_item.setPos((self.scene.width() - scaled_pixmap.width()) / 2,
                           (self.scene.height() - scaled_pixmap.height()) / 2)
            self.scene.addItem(bg_item) 
            self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self.log_message(f"背景画像を設定しました: {file_path}")
            self.update_menu_layout()
        else:
            self.log_message(f"エラー: 画像ファイルの読み込みに失敗しました: {file_path}")

    def add_chapter(self):
        time_text = self.chapter_input.text()
        if not re.match(r'^\d{2}:\d{2}:\d{2}$', time_text):
            self.log_message("エラー: チャプターは HH:MM:SS 形式で入力してください。")
            return
        if time_text == '00:00:00':
            self.log_message("エラー: 00:00:00 は自動的に追加されます。")
            return
        if time_text not in self.chapters:
            self.chapters.append(time_text)
            self.chapters.sort()
            self.update_chapter_list_widget()
            self.log_message(f"チャプターを追加しました: {time_text}")
            self.update_menu_layout()
            self.chapter_input.clear() 

    def delete_selected_chapter(self):
        selected_item = self.chapter_list_widget.currentItem()
        if not selected_item:
            self.log_message("削除するチャプターが選択されていません。")
            return
        if '00:00:00' in selected_item.text():
            self.log_message("エラー: 最初のチャプター (00:00:00) は削除できません。")
            return
        try:
            time_str = re.search(r'(\d{2}:\d{2}:\d{2})', selected_item.text()).group(1)
            if time_str in self.chapters:
                self.chapters.remove(time_str)
                self.update_chapter_list_widget()
                self.update_menu_layout()
                self.log_message(f"チャプターを削除しました: {time_str}")
        except (AttributeError, IndexError):
            self.log_message("エラー: 選択された項目から時間を抽出できませんでした。")

    def update_chapter_list_widget(self):
        self.chapter_list_widget.clear()
        all_chapters = sorted(['00:00:00'] + self.chapters)
        for i, time in enumerate(all_chapters):
            self.chapter_list_widget.addItem(f"チャプター {i+1}: {time}")

    # --- ★★★【チャプターバグ修正】★★★
    def update_menu_layout(self, loaded_data=None):
        saved_button_props = {}
        # バグ修正: self.menu_buttons からではなく、シーンから直接アイテムを取得して保存する
        #           (self.menu_buttons が古い可能性に対処)
        scene_items = self.scene.items()
        
        for item in scene_items:
            if isinstance(item, DraggableProxyWidget):
                time_str = item.property("time_str")
                if time_str:
                    saved_button_props[time_str] = self.get_item_properties(item)

        saved_title_props = {}
        if self.title_item:
            # self.title_item は信頼できるものとする
            saved_title_props = self.get_item_properties(self.title_item)
            saved_title_props["text"] = self.title_item.toPlainText()
        else:
             # self.title_item が None の場合も、シーンから探す
            for item in scene_items:
                if isinstance(item, DraggableTextItem):
                    self.title_item = item # 見つけた
                    saved_title_props = self.get_item_properties(item)
                    saved_title_props["text"] = item.toPlainText()
                    break

        # --- 正常な削除ロジック ---
        items_to_remove = [item for item in scene_items if not isinstance(item, QGraphicsPixmapItem)]
        for item in items_to_remove:
            if isinstance(item, QGraphicsProxyWidget):
                widget = item.widget()
                if widget:
                    item.setWidget(None) 
                    widget.deleteLater() 
            self.scene.removeItem(item)
            item.deleteLater() # ★ オブジェクトをメモリから完全に削除
            
        self.menu_buttons.clear() # Pythonリストをクリア
        self.title_item = None
        self.selected_item = None
        self.clear_property_panel()
        
        if loaded_data:
            self.create_title_item(loaded_data.get("title", {}))
            for button_data in loaded_data.get("buttons", []):
                self.create_menu_button(button_data, button_data.get("time_str"))
        else:
            title_props_to_use = saved_title_props if saved_title_props else {
                "text": "My Blu-ray Title", "pos_x": 100, "pos_y": 50,
                "font_family": self.default_title_font_family,
                "font_size": self.default_title_font_size,
                "font_color": self.default_title_font_color,
                "is_bold": False, "is_italic": False
            }
            self.create_title_item(title_props_to_use)

            all_chapters = sorted(['00:00:00'] + self.chapters)
            for i, chapter_time in enumerate(all_chapters):
                props = saved_button_props.get(chapter_time)
                if props:
                    # ★ 以前のテキストを復元
                    props["text"] = props.get("text", f"Chapter {i+1}") 
                    self.create_menu_button(props, chapter_time)
                else:
                    self.create_menu_button({
                        "text": f"Chapter {i+1}", "pos_x": 100, "pos_y": 150 + i * 70,
                        "font_family": self.default_button_font_family,
                        "font_size": self.default_button_font_size,
                        "font_color": self.default_button_font_color,
                        "is_bold": False, "is_italic": False
                    }, chapter_time)

        self.log_message("メニューレイアウトを更新しました。")
        self.scene.update()
    # --- ★★★【修正完了】★★★

    def create_title_item(self, properties):
        if not properties:
            properties = {
                "text": "My Blu-ray Title", "pos_x": 100, "pos_y": 50,
                "font_family": self.default_title_font_family,
                "font_size": self.default_title_font_size,
                "font_color": self.default_title_font_color,
                "is_bold": False, "is_italic": False
            }
        self.title_item = DraggableTextItem(properties.get("text", "Title"))
        self.title_item.clicked.connect(self.on_item_selected)
        self.title_item.setProperty("font_family", properties.get("font_family", self.default_title_font_family))
        self.title_item.setProperty("font_size", properties.get("font_size", self.default_title_font_size))
        self.title_item.setProperty("font_color", properties.get("font_color", self.default_title_font_color))
        self.title_item.setProperty("is_bold", properties.get("is_bold", False))
        self.title_item.setProperty("is_italic", properties.get("is_italic", False))
        self.apply_text_item_style(self.title_item)
        self.scene.addItem(self.title_item)
        self.title_item.setPos(properties.get("pos_x", 100), properties.get("pos_y", 50))

    def create_menu_button(self, properties, chapter_time):
        button = QTextEdit()
        button.setText(properties["text"])
        button.setReadOnly(True)
        proxy_widget = DraggableProxyWidget()
        proxy_widget.setWidget(button)
        proxy_widget.clicked.connect(self.on_item_selected)
        proxy_widget.setProperty("time_str", chapter_time)
        proxy_widget.setProperty("font_family", properties.get("font_family", self.default_button_font_family))
        proxy_widget.setProperty("font_size", properties.get("font_size", self.default_button_font_size))
        proxy_widget.setProperty("font_color", properties.get("font_color", self.default_button_font_color))
        proxy_widget.setProperty("is_bold", properties.get("is_bold", False))
        proxy_widget.setProperty("is_italic", properties.get("is_italic", False))
        self.apply_button_style(proxy_widget)
        self.scene.addItem(proxy_widget)
        proxy_widget.setPos(properties["pos_x"], properties["pos_y"])
        if "width" in properties and "height" in properties:
            proxy_widget.resize(properties["width"], properties["height"])
        self.menu_buttons.append(proxy_widget)

    def on_item_selected(self, item):
        if self.selected_item == item:
            return
        self.selected_item = item
        self.clear_property_panel() 

        if isinstance(item, DraggableProxyWidget):
            self.button_text_input.setEnabled(True)
            self.font_combo_box.setEnabled(True)
            self.font_size_spinbox.setEnabled(True)
            self.color_button.setEnabled(True)
            self.button_bold_button.setEnabled(True)
            self.button_italic_button.setEnabled(True)
            self.button_text_input.setText(item.widget().toPlainText())
            font = QFont(); font.setFamily(item.property("font_family"))
            self.font_combo_box.setCurrentFont(font)
            self.font_size_spinbox.setValue(item.property("font_size"))
            color = item.property("font_color")
            self.color_button.setStyleSheet(f"background-color: {color};")
            self.button_bold_button.setChecked(item.property("is_bold"))
            self.button_italic_button.setChecked(item.property("is_italic"))

        elif isinstance(item, DraggableTextItem):
            self.title_text_input.setEnabled(True)
            self.title_font_combo_box.setEnabled(True)
            self.title_font_size_spinbox.setEnabled(True)
            self.title_color_button.setEnabled(True)
            self.title_bold_button.setEnabled(True)
            self.title_italic_button.setEnabled(True)
            self.title_text_input.setText(item.toPlainText())
            font = QFont(); font.setFamily(item.property("font_family"))
            self.title_font_combo_box.setCurrentFont(font)
            self.title_font_size_spinbox.setValue(item.property("font_size"))
            color = item.property("font_color")
            self.title_color_button.setStyleSheet(f"background-color: {color};")
            self.title_bold_button.setChecked(item.property("is_bold"))
            self.title_italic_button.setChecked(item.property("is_italic"))

    def update_item_text(self):
        if not self.selected_item: return
        sender_widget = self.sender()
        new_text = ""
        if isinstance(sender_widget, QLineEdit):
            new_text = sender_widget.text()
        elif isinstance(sender_widget, QTextEdit):
            new_text = sender_widget.toPlainText()
        else:
            return
        if isinstance(self.selected_item, DraggableProxyWidget) and sender_widget == self.button_text_input:
            self.selected_item.widget().setText(new_text)
            self.selected_item.setProperty("text", new_text) # ★ プロパティにも保存
        elif isinstance(self.selected_item, DraggableTextItem) and sender_widget == self.title_text_input:
            self.selected_item.setPlainText(new_text)

    def update_item_font(self, font):
        if not self.selected_item: return
        sender_widget = self.sender()
        self.selected_item.setProperty("font_family", font.family())
        if isinstance(self.selected_item, DraggableProxyWidget) and sender_widget == self.font_combo_box:
            self.apply_button_style(self.selected_item)
        elif isinstance(self.selected_item, DraggableTextItem) and sender_widget == self.title_font_combo_box:
            self.apply_text_item_style(self.selected_item)

    def update_item_font_size(self, size):
        if not self.selected_item: return
        sender_widget = self.sender()
        self.selected_item.setProperty("font_size", size)
        if isinstance(self.selected_item, DraggableProxyWidget) and sender_widget == self.font_size_spinbox:
            self.apply_button_style(self.selected_item)
        elif isinstance(self.selected_item, DraggableTextItem) and sender_widget == self.title_font_size_spinbox:
            self.apply_text_item_style(self.selected_item)

    def update_item_font_style(self):
        if not self.selected_item: return
        sender = self.sender()
        if sender == self.title_bold_button:
            self.selected_item.setProperty("is_bold", sender.isChecked())
        elif sender == self.title_italic_button:
            self.selected_item.setProperty("is_italic", sender.isChecked())
        elif sender == self.button_bold_button:
            self.selected_item.setProperty("is_bold", sender.isChecked())
        elif sender == self.button_italic_button:
            self.selected_item.setProperty("is_italic", sender.isChecked())
        else:
            return 
        if isinstance(self.selected_item, DraggableTextItem):
            self.apply_text_item_style(self.selected_item)
        elif isinstance(self.selected_item, DraggableProxyWidget):
            self.apply_button_style(self.selected_item)

    def open_item_color_picker(self):
        if not self.selected_item: return
        sender_widget = self.sender()
        current_color = QColor(self.selected_item.property("font_color"))
        color = QColorDialog.getColor(current_color)
        if color.isValid():
            color_hex = color.name()
            self.selected_item.setProperty("font_color", color_hex)
            if isinstance(self.selected_item, DraggableProxyWidget) and sender_widget == self.color_button:
                self.apply_button_style(self.selected_item)
                self.color_button.setStyleSheet(f"background-color: {color_hex};")
            elif isinstance(self.selected_item, DraggableTextItem) and sender_widget == self.title_color_button:
                self.apply_text_item_style(self.selected_item)
                self.title_color_button.setStyleSheet(f"background-color: {color_hex};")

    def apply_button_style(self, button_proxy):
        font_family = button_proxy.property("font_family")
        font_size = button_proxy.property("font_size")
        font_color = button_proxy.property("font_color")
        is_bold = button_proxy.property("is_bold")
        is_italic = button_proxy.property("is_italic")
        font_weight = "bold" if is_bold else "normal"
        font_style = "italic" if is_italic else "normal"
        style = f"""QTextEdit {{
                    background-color: rgba(0, 0, 0, 0.6);
                    color: {font_color};
                    border: 1px solid white;
                    border-radius: 5px;
                    padding: 10px;
                    font-family: '{font_family}';
                    font-size: {font_size}px;
                    font-weight: {font_weight};
                    font-style: {font_style};
                }}"""
        button_proxy.widget().setStyleSheet(style)
        if isinstance(button_proxy.widget(), QTextEdit):
            button_proxy.widget().setAlignment(Qt.AlignCenter)

    def apply_text_item_style(self, text_item):
        font = QFont()
        font.setFamily(text_item.property("font_family"))
        font.setPointSize(text_item.property("font_size"))
        font.setBold(text_item.property("is_bold"))
        font.setItalic(text_item.property("is_italic"))
        text_item.setFont(font)
        text_item.setDefaultTextColor(QColor(text_item.property("font_color")))

    # --- ★★★【チャプターバグ修正】★★★
    def get_item_properties(self, item):
        props = {
            "pos_x": item.pos().x(), "pos_y": item.pos().y(),
            "font_family": item.property("font_family"),
            "font_size": item.property("font_size"),
            "font_color": item.property("font_color"),
            "is_bold": item.property("is_bold"),
            "is_italic": item.property("is_italic")
        }
        if isinstance(item, DraggableProxyWidget):
            props["width"] = item.size().width()
            props["height"] = item.size().height()
            props["time_str"] = item.property("time_str")
            props["text"] = item.widget().toPlainText() # ★ テキストも保存
        return props
    # --- ★★★【修正完了】★★★

    def clear_property_panel(self):
        if hasattr(self, 'button_text_input'): self.button_text_input.clear(); self.button_text_input.setEnabled(False); self.button_text_input.setPlaceholderText("ボタンを選択...")
        if hasattr(self, 'font_combo_box'): self.font_combo_box.setEnabled(False)
        if hasattr(self, 'font_size_spinbox'): self.font_size_spinbox.setEnabled(False)
        if hasattr(self, 'color_button'): self.color_button.setEnabled(False); self.color_button.setStyleSheet("")
        if hasattr(self, 'button_bold_button'): self.button_bold_button.setEnabled(False); self.button_bold_button.setChecked(False)
        if hasattr(self, 'button_italic_button'): self.button_italic_button.setEnabled(False); self.button_italic_button.setChecked(False)
        if hasattr(self, 'title_text_input'): self.title_text_input.clear(); self.title_text_input.setEnabled(False); self.title_text_input.setPlaceholderText("タイトルをダブルクリックして編集...")
        if hasattr(self, 'title_font_combo_box'): self.title_font_combo_box.setEnabled(False)
        if hasattr(self, 'title_font_size_spinbox'): self.title_font_size_spinbox.setEnabled(False)
        if hasattr(self, 'title_color_button'): self.title_color_button.setEnabled(False); self.title_color_button.setStyleSheet("")
        if hasattr(self, 'title_bold_button'): self.title_bold_button.setEnabled(False); self.title_bold_button.setChecked(False)
        if hasattr(self, 'title_italic_button'): self.title_italic_button.setEnabled(False); self.title_italic_button.setChecked(False)

    def save_layout(self):
        if not self.background_image_path:
            self.log_message("エラー: 保存する背景画像がありません。")
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "レイアウトを保存", "", "JSON Files (*.json)")
        if not save_path:
            return
        layout_data = {"background": self.background_image_path, "chapters": self.chapters, "buttons": []}
        if self.title_item:
            title_data = self.get_item_properties(self.title_item)
            title_data["text"] = self.title_item.toPlainText()
            layout_data["title"] = title_data
        for proxy_widget in self.menu_buttons:
            props = self.get_item_properties(proxy_widget)
            # props["text"] = proxy_widget.widget().toPlainText() # get_item_properties で保存済
            layout_data["buttons"].append(props)
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(layout_data, f, indent=4, ensure_ascii=False)
            self.log_message(f"レイアウトを保存しました: {save_path}")
        except Exception as e:
            self.log_message(f"レイアウトの保存に失敗しました: {e}")

    def load_layout(self):
        load_path, _ = QFileDialog.getOpenFileName(self, "レイアウトを読み込み", "", "JSON Files (*.json)")
        if not load_path:
            return
        try:
            with open(load_path, 'r', encoding='utf-8') as f:
                layout_data = json.load(f)
            self.chapters = layout_data.get("chapters", [])
            self.update_chapter_list_widget()
            self.background_image_path = layout_data["background"]
            self.set_background_image(self.background_image_path)
            # ★ 修正: update_menu_layout は bg 設定後に呼ばれるので、
            #    set_background_image の中で呼ばれる update_menu_layout が loaded_data を使えるようにする必要がある
            #    -> いや、set_background_image が update_menu_layout を呼ぶ。
            #    -> そこで loaded_data=layout_data を渡す必要がある。
            #    -> set_background_image が update_menu_layout() を呼ぶので、
            #       self.update_menu_layout(loaded_data=layout_data) をここで呼ぶのは二重になる。
            
            # set_background_image が呼ぶ update_menu_layout は引数なしで実行されるため、
            # 既存のボタン位置が復元されてしまう。
            # 苦肉の策だが、load_layout 専用のフラグを持たせるか...
            # いや、set_background_image が update_menu_layout を呼ぶので、
            # load_layout は set_background_image の *後* に update_menu_layout を
            # loaded_data 付きで呼び出せば上書きされる。
            self.update_menu_layout(loaded_data=layout_data) # ★ これで上書き
            self.log_message(f"レイアウトを読み込みました: {load_path}")
        except Exception as e:
            self.log_message(f"レイアウトの読み込みに失敗しました: {e}")

    def start_authoring(self):
        if not self.selected_video_path or not self.background_image_path:
            self.log_message("エラー: 動画ファイルと背景画像の両方を選択してください。")
            return

        self.toggle_ui_elements(False)
        self.encoded_video_path = None
        self.menu_video_path = None
        self.generated_iso_path = None
        self.burn_button.setEnabled(False) 
        self.log_output.clear()
        self.log_message("オーサリング準備中...")
        
        selected_option_data = self.resolution_combo_box.currentData()
        encoder_res_fps_str = ""
        menu_res_fps_str = ""    
        
        if selected_option_data == "original":
            if not self.original_video_info:
                self.encoding_error("エラー: 'オリジナル' が選択されましたが、動画情報の取得に失敗しています。")
                return
            res, fps_str, fps_float = self.original_video_info
            encoder_res_fps_str = "original" 
            menu_res_fps_str = f"{res}:{fps_str}"
            self.log_message(f"設定: 'オリジナル' ({menu_res_fps_str}) を使用します。")
        else:
            encoder_res_fps_str = selected_option_data
            menu_res_fps_str = selected_option_data
            self.log_message(f"設定: '指定' ({menu_res_fps_str}) を使用します。")
        
        base_dir = os.path.dirname(os.path.abspath(self.selected_video_path))
        base_dir_fwd_slash = base_dir.replace('\\', '/')
        self.menu_image_path = os.path.join(base_dir_fwd_slash, "menu_image.png")

        try:
            for item in self.scene.selectedItems():
                item.setSelected(False)
            self.render_scene_to_image(self.menu_image_path)
            self.log_message(f"メニュー画像を保存しました: {self.menu_image_path}")
            self.start_menu_encoding_process(self.menu_image_path, menu_res_fps_str)
            self.start_encoding_process(encoder_res_fps_str) 
        except Exception as e:
            self.encoding_error(f"メニュー画像の生成に失敗: {e}")

    def render_scene_to_image(self, save_path):
        scene_rect = self.scene.sceneRect()
        image = QImage(scene_rect.size().toSize(), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        self.scene.show_grid = False
        try:
            self.scene.render(painter, target=scene_rect, source=scene_rect)
        finally:
            self.scene.show_grid = True
        painter.end()
        image.save(save_path)

    def start_menu_encoding_process(self, image_path, menu_res_fps_str):
        self.log_message("メニュー動画エンコード準備中...")
        ffmpeg_path = self.find_ffmpeg(for_menu=True)
        if not ffmpeg_path:
            self.encoding_error("ffmpegが見つかりません。")
            return
        self.menu_duration_sec = 10.0
        worker = MenuEncoderWorker(image_path, self.menu_duration_sec, menu_res_fps_str, ffmpeg_path)
        worker.signals.log.connect(self.log_message)
        worker.signals.finished.connect(self.menu_encoding_finished)
        worker.signals.error.connect(self.encoding_error)
        self.threadpool.start(worker)

    def start_encoding_process(self, encoder_res_fps_str):
        self.log_message("本編エンコード準備中...")
        ffmpeg_path = self.find_ffmpeg()
        if not ffmpeg_path:
            self.encoding_error("ffmpegが見つかりません。")
            return
        
        gui_encoder_choice = self.encoder_combo_box.currentData()
        
        worker = EncoderWorker(self.selected_video_path, self.chapters, gui_encoder_choice, encoder_res_fps_str, ffmpeg_path)
        worker.signals.log.connect(self.log_message)
        worker.signals.finished.connect(self.encoding_finished)
        worker.signals.error.connect(self.encoding_error)
        self.threadpool.start(worker)

    def start_muxing_process(self):
        if not self.menu_video_path or not self.encoded_video_path:
            self.encoding_error("致命的エラー: Mux処理が呼ばれましたが、動画ファイルが不足しています。")
            return

        base_dir = os.path.dirname(os.path.abspath(self.selected_video_path))
        iso_output_path = os.path.join(base_dir, "BDMV_MENU.iso") 
        meta_path = os.path.join(base_dir, "tsmuxer.meta")

        selected_option_data = self.resolution_combo_box.currentData()
        fps_str = "23.976" 
        if selected_option_data == "original":
            if self.original_video_info:
                res, fps_str_from_info, fps_float = self.original_video_info
                fps_str = fps_str_from_info 
            else:
                self.encoding_error("致命的エラー: Mux処理中、オリジナル動画のFPSが不明です。")
                return
        else:
            if ":" in selected_option_data:
                 fps_part = selected_option_data.split(':')[1]
                 if fps_part == "60": fps_str = "59.94"
                 elif fps_part == "30": fps_str = "29.97"
                 elif "24000/1001" in fps_part: fps_str = "24000/1001"

        def time_to_sec(t):
            h, m, s = map(int, t.split(':'))
            return float(h * 3600 + m * 60 + s)
        def sec_to_time(s_float):
            s = int(round(s_float))
            h = s // 3600
            m = (s % 3600) // 60
            s = s % 60
            return f"{h:02}:{m:02}:{s:02}" 

        offset_sec = self.menu_duration_sec 
        all_chapters_time = sorted(['00:00:00'] + self.chapters)
        offset_chapters_list = []
        for time_str in all_chapters_time:
            original_sec = time_to_sec(time_str)
            offset_chapters_list.append(sec_to_time(original_sec + offset_sec))
        final_chapters_list = ["00:00:00"] + offset_chapters_list 
        chapters_str = ";".join(final_chapters_list)

        menu_path_for_meta = os.path.abspath(self.menu_video_path).replace('\\', '/')
        encoded_path_for_meta = os.path.abspath(self.encoded_video_path).replace('\\', '/')

        meta_content = f'MUXOPT --no-pcr-on-video-pid --new-audio-pes --vbr --vbv-len=500 --blu-ray-iso --chapters="{chapters_str}"\n'
        meta_content += f'V_MPEG4/ISO/AVC, "{menu_path_for_meta}"+"{encoded_path_for_meta}", track=1, fps={fps_str}\n'
        meta_content += f'A_AC3, "{menu_path_for_meta}"+"{encoded_path_for_meta}", track=2\n'

        try:
            with open(meta_path, 'w', encoding='utf-8') as f:
                f.write(meta_content)
            self.log_message("tsMuxeR用の設定ファイルを作成しました (連結指定)。")
            self.log_message(f"--- .meta ファイル内容 (デバッグ用) ---\n{meta_content}---")
        except Exception as e:
            self.encoding_error(f"tsMuxeR設定ファイルの作成に失敗: {e}")
            return

        tsmuxer_exe_path = self.find_tsmuxer()
        if not tsmuxer_exe_path:
             self.encoding_error("tsMuxeR が見つかりませんでした。")
             return
        
        worker = AuthoringWorker(tsmuxer_exe_path, meta_path, iso_output_path) 
        worker.signals.log.connect(self.log_message)
        worker.signals.finished.connect(self.authoring_finished)
        worker.signals.error.connect(self.encoding_error)
        self.threadpool.start(worker)

    def find_ffmpeg(self, for_menu=False):
        ffmpeg_path = get_platform_specific_path("ffmpeg") 
        if ffmpeg_path:
            if not for_menu: # 本編用の時だけログを出す（メニュー用は冗長なので）
                self.log_message(f"ffmpegを発見: {ffmpeg_path}")
            return ffmpeg_path
        self.log_message("ffmpegが見つかりません")
        return None

    def find_tsmuxer(self):
        tsmuxer_path = get_platform_specific_path("tsMuxeR")
        if tsmuxer_path:
            self.log_message(f"tsMuxeRを発見: {tsmuxer_path}")
            return tsmuxer_path
        self.log_message("tsMuxeRが見つかりません")
        return None

    def find_ffprobe(self):
        ffprobe_path = get_platform_specific_path("ffprobe")
        if ffprobe_path:
            self.log_message(f"ffprobeを発見: {ffprobe_path}")
            return ffprobe_path
        self.log_message("ffprobeが見つかりません")
        return None

    def get_video_info(self, video_path):
        ffprobe_path = self.find_ffprobe()
        if not ffprobe_path:
            self.log_message("ffprobe が見つからないため、動画情報を取得できません。")
            return None
        command = [
            ffprobe_path, '-v', 'quiet', '-print_format', 'json',
            '-show_streams', '-select_streams', 'v:0', video_path
        ]
        try:
            creation_flags = 0
            if sys.platform == 'win32':
                creation_flags = subprocess.CREATE_NO_WINDOW
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                       universal_newlines=True, encoding='utf-8', 
                                       creationflags=creation_flags)
            stdout, stderr = process.communicate(timeout=10)
            if process.returncode != 0:
                self.log_message(f"ffprobeの実行に失敗: {stderr}")
                return None
            data = json.loads(stdout)
            if 'streams' not in data or not data['streams']:
                self.log_message("ffprobe: ビデオストリームが見つかりません。")
                return None

            stream = data['streams'][0]
            width = stream.get('width')
            height = stream.get('height')
            if not width or not height:
                 self.log_message("ffprobe: 解像度が取得できません。")
                 return None
            resolution_str = f"{width}x{height}"
            
            fps_eval = 0.0
            fps_str = stream.get('r_frame_rate')
            if '/' in fps_str:
                num, den = map(float, fps_str.split('/'))
                if den != 0: fps_eval = num / den
            
            if fps_eval == 0.0 or fps_eval.is_integer():
                avg_fps_str = stream.get('avg_frame_rate', '0/1')
                if '/' in avg_fps_str:
                    num, den = map(float, avg_fps_str.split('/'))
                    if den != 0 and (num/den) != fps_eval:
                        fps_str = avg_fps_str
                        fps_eval = num / den

            if 23.9 < fps_eval < 24.1:
                fps_bd_str = "24000/1001"
            elif 29.9 < fps_eval < 30.1:
                fps_bd_str = "29.97"
            elif 59.9 < fps_eval < 60.1:
                fps_bd_str = "59.94"
            else:
                fps_bd_str = fps_str if "/" in fps_str else f"{int(fps_eval * 1000)}/1000"

            self.log_message(f"動画情報: {resolution_str}, FPS: {fps_eval:.3f} (内部使用: {fps_bd_str})")
            return (resolution_str, fps_bd_str, fps_eval)
            
        except Exception as e:
            self.log_message(f"ffprobeでの動画情報取得に失敗: {e}")
            return None

    def start_burning_process(self):
        if not self.generated_iso_path or not os.path.exists(self.generated_iso_path):
            self.log_message("エラー: 書き込むISOファイルが見つかりません。")
            return
        drive_id = self.drive_combo.currentData()
        if not drive_id:
             self.log_message("エラー: 書き込み先のドライブを選択してください。")
             return
        self.log_message(f"書き込み処理を開始します (ドライブ: {drive_id}, ISO: {self.generated_iso_path})")
        self.toggle_ui_elements(False) 
        worker = BurnerWorker(self.generated_iso_path, drive_id)
        worker.signals.log.connect(self.log_message)
        worker.signals.error.connect(self.encoding_error)
        worker.signals.finished.connect(self.burning_finished)
        self.threadpool.start(worker)

    def populate_drive_list(self):
        self.drive_combo.clear()
        self.log_message("書き込みドライブを検索中...")
        try:
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NO_WINDOW
                output = subprocess.check_output(['wmic', 'cdrom', 'get', 'Drive, MediaType'],
                                                 universal_newlines=True,
                                                 creationflags=creation_flags)
                for line in output.splitlines():
                    match = re.match(r'^\s*([A-Z]:)\s*(.*)', line)
                    if match:
                        drive = match.group(1)
                        media_type = match.group(2).strip()
                        if not media_type: media_type = "メディアなし"
                        self.drive_combo.addItem(f"{drive} ({media_type})", drive)
                if self.drive_combo.count() > 0:
                     self.log_message(f"{self.drive_combo.count()}個のドライブを見つけました。")
                else:
                     self.log_message("書き込み可能なドライブが見つかりませんでした。")
            elif sys.platform == "darwin":
                output = subprocess.check_output(['drutil', 'list'], universal_newlines=True)
                current_device = None
                for line in output.splitlines():
                    if "Vendor" in line and "Product" in line:
                         match = re.search(r'/dev/(disk\d+)', line)
                         if match: current_device = match.group(1)
                    if current_device and "Type" in line and ("CD" in line or "DVD" in line or "BD" in line):
                         self.drive_combo.addItem(f"{current_device} (光学ドライブ)", current_device)
                         current_device = None
                if self.drive_combo.count() > 0:
                     self.log_message(f"{self.drive_combo.count()}個のドライブを見つけました。")
                else:
                     self.log_message("書き込み可能なドライブが見つかりませんでした。")
            else:
                self.log_message(f"非対応OSのためドライブを取得できません: {sys.platform}")
        except Exception as e:
            self.log_message(f"ドライブ一覧の取得に失敗: {e}")

    def play_video(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_button.setText("再生")
        else:
            self.player.play()
            self.play_button.setText("一時停止")
    def add_chapter_from_video(self):
        if self.player.source().isEmpty():
            return
        milliseconds = self.player.position()
        time_str = self.format_time(milliseconds)
        self.chapter_input.setText(time_str)
        self.add_chapter()
    def zoom_in_preview(self):
        self.view.scale(1.2, 1.2)
    def zoom_out_preview(self):
        self.view.scale(1 / 1.2, 1.2)
    def rewind_video(self):
        current_pos = self.player.position()
        self.player.setPosition(max(0, current_pos - 10000))
    def skip_video(self):
        current_pos = self.player.position()
        self.player.setPosition(current_pos + 10000)
    def set_default_font(self, font): pass
    def set_default_font_size(self, size): pass
    def set_default_color(self): pass

    def create_panel_widget(self, title):
        panel_frame = QFrame()
        panel_layout = QVBoxLayout(panel_frame)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)
        header = QLabel(title)
        header.setObjectName("panel-header")
        header.setFixedHeight(40)
        content_widget = QWidget()
        panel_layout.addWidget(header)
        panel_layout.addWidget(content_widget, 1)
        return panel_frame, content_widget

    def create_project_panel(self,):
        panel, content = self.create_panel_widget("プロジェクト")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(content)
        self.file_path_label = QLabel("動画ファイルが選択されていません")
        self.select_file_button = QPushButton("動画ファイルを選択...")
        self.select_file_button.clicked.connect(self.open_file_dialog)
        self.select_bg_button = QPushButton("背景画像を選択...")
        self.select_bg_button.clicked.connect(self.open_background_image_dialog)
        self.save_layout_button = QPushButton("レイアウトを保存...")
        self.save_layout_button.clicked.connect(self.save_layout)
        self.load_layout_button = QPushButton("レイアウトを読み込み...")
        self.load_layout_button.clicked.connect(self.load_layout)
        layout.addWidget(self.select_file_button)
        layout.addWidget(self.file_path_label)
        layout.addWidget(self.select_bg_button)
        layout.addWidget(self.save_layout_button)
        layout.addWidget(self.load_layout_button)
        layout.addStretch(1)
        return panel

    def create_video_panel(self):
        panel, content = self.create_panel_widget("ビデオプレビュー")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(content)
        self.video_widget = AspectRatioVideoWidget() 
        self.player.setVideoOutput(self.video_widget)
        controls_layout = QGridLayout()
        self.play_button = QPushButton("再生")
        self.play_button.setEnabled(False)
        self.rewind_button = QPushButton("« 10s")
        self.rewind_button.setEnabled(False)
        self.skip_button = QPushButton("10s »")
        self.skip_button.setEnabled(False)
        self.timecode_label = QLabel("00:00:00 / 00:00:00")
        self.timecode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.add_chapter_from_video_button = QPushButton("現在の位置をチャプターに追加")
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setEnabled(False)
        self.seek_slider.sliderMoved.connect(self.set_video_position)
        controls_layout.addWidget(self.rewind_button, 0, 0)
        controls_layout.addWidget(self.play_button, 0, 1)
        controls_layout.addWidget(self.skip_button, 0, 2)
        controls_layout.addWidget(self.timecode_label, 0, 3, 1, 2)
        controls_layout.setColumnStretch(3, 1)
        controls_layout.addWidget(self.seek_slider, 1, 0, 1, 5)
        controls_layout.addWidget(self.add_chapter_from_video_button, 2, 0, 1, 5)
        self.play_button.clicked.connect(self.play_video)
        self.rewind_button.clicked.connect(self.rewind_video)
        self.skip_button.clicked.connect(self.skip_video)
        self.add_chapter_from_video_button.clicked.connect(self.add_chapter_from_video)
        layout.addWidget(self.video_widget, 1)
        layout.addLayout(controls_layout)
        return panel

    def create_preview_panel(self):
        panel, content = self.create_panel_widget("メニュープレビュー")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(content)
        self.scene = GridGraphicsScene()
        self.scene.setSceneRect(0, 0, 1920, 1080) 
        self.view = AspectRatioGraphicsView(self.scene)
        self.view.setStyleSheet("background-color: #101010; border: none;")
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        zoom_layout = QHBoxLayout()
        zoom_in_button = QPushButton("拡大 (+)")
        zoom_out_button = QPushButton("縮小 (-)")
        zoom_layout.addStretch()
        zoom_layout.addWidget(zoom_in_button)
        zoom_layout.addWidget(zoom_out_button)
        zoom_in_button.clicked.connect(self.zoom_in_preview)
        zoom_out_button.clicked.connect(self.zoom_out_preview)
        layout.addLayout(zoom_layout)
        layout.addWidget(self.view, 1)
        return panel

    def create_settings_panel(self):
        settings_widget = self._create_settings_widget()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(settings_widget)
        scroll_area.setObjectName("settings-scroll-area")
        scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return scroll_area

    def _create_settings_widget(self):
        panel, content = self.create_panel_widget("設定")
        panel.setStyleSheet("QFrame { border: none; }")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(content)

        # --- Title Properties ---
        layout.addWidget(QLabel("タイトル プロパティ"))
        self.title_text_input = QLineEdit()
        self.title_text_input.setPlaceholderText("タイトルをダブルクリックして編集...")
        self.title_text_input.textChanged.connect(self.update_item_text)
        layout.addWidget(self.title_text_input)
        self.title_font_combo_box = QFontComboBox()
        self.title_font_combo_box.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.title_font_combo_box.currentFontChanged.connect(self.update_item_font)
        layout.addWidget(self.title_font_combo_box)
        title_style_layout = QHBoxLayout()
        title_style_layout.addWidget(QLabel("サイズ:"))
        self.title_font_size_spinbox = QSpinBox()
        self.title_font_size_spinbox.setRange(8, 200)
        self.title_font_size_spinbox.valueChanged.connect(self.update_item_font_size)
        title_style_layout.addWidget(self.title_font_size_spinbox)
        self.title_bold_button = QToolButton()
        self.title_bold_button.setText("B")
        self.title_bold_button.setCheckable(True)
        self.title_bold_button.clicked.connect(self.update_item_font_style)
        title_style_layout.addWidget(self.title_bold_button)
        self.title_italic_button = QToolButton()
        self.title_italic_button.setText("I")
        self.title_italic_button.setCheckable(True)
        self.title_italic_button.clicked.connect(self.update_item_font_style)
        title_style_layout.addWidget(self.title_italic_button)
        self.title_color_button = QPushButton("色を変更")
        self.title_color_button.clicked.connect(self.open_item_color_picker)
        title_style_layout.addWidget(self.title_color_button)
        layout.addLayout(title_style_layout)
        separator_title = QFrame(); separator_title.setFrameShape(QFrame.Shape.HLine); separator_title.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator_title)

        # --- Button Properties ---
        layout.addWidget(QLabel("ボタン プロパティ"))
        self.button_text_input = QTextEdit()
        self.button_text_input.setFixedHeight(80)
        self.button_text_input.setPlaceholderText("ボタンを選択...")
        self.button_text_input.textChanged.connect(self.update_item_text)
        layout.addWidget(self.button_text_input)
        self.font_combo_box = QFontComboBox()
        self.font_combo_box.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.font_combo_box.currentFontChanged.connect(self.update_item_font)
        layout.addWidget(self.font_combo_box)
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(QLabel("サイズ:"))
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setRange(8, 200)
        self.font_size_spinbox.valueChanged.connect(self.update_item_font_size)
        font_size_layout.addWidget(self.font_size_spinbox)
        self.button_bold_button = QToolButton()
        self.button_bold_button.setText("B")
        self.button_bold_button.setCheckable(True)
        self.button_bold_button.clicked.connect(self.update_item_font_style)
        font_size_layout.addWidget(self.button_bold_button)
        self.button_italic_button = QToolButton()
        self.button_italic_button.setText("I")
        self.button_italic_button.setCheckable(True)
        self.button_italic_button.clicked.connect(self.update_item_font_style)
        font_size_layout.addWidget(self.button_italic_button)
        self.color_button = QPushButton("色を変更")
        self.color_button.clicked.connect(self.open_item_color_picker)
        font_size_layout.addWidget(self.color_button)
        layout.addLayout(font_size_layout)
        separator_default = QFrame(); separator_default.setFrameShape(QFrame.Shape.HLine); separator_default.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator_default)

        # --- Encoding Settings ---
        layout.addWidget(QLabel("エンコード設定"))
        self.encoder_combo_box = QComboBox()
        self.encoder_combo_box.addItem("CPU (高品質)", "libx264")
        self.encoder_combo_box.addItem("NVIDIA (高速)", "h264_nvenc")
        self.encoder_combo_box.addItem("AMD (高速)", "h264_amf")
        self.encoder_combo_box.addItem("Intel (高速)", "h264_qsv")
        layout.addWidget(self.encoder_combo_box)
        self.resolution_combo_box = QComboBox()
        self.resolution_combo_box.addItem("オリジナル (動画ファイルを指定してください)", "original") 
        self.resolution_combo_box.addItem("1080p 60fps", "1920x1080:60")
        self.resolution_combo_box.addItem("1080p 30fps", "1920x1080:30")
        self.resolution_combo_box.addItem("1080p 24fps (BD標準)", "1920x1080:24000/1001")
        self.resolution_combo_box.addItem("720p 60fps", "1280x720:60")
        self.resolution_combo_box.addItem("720p 30fps", "1280x720:30")
        self.resolution_combo_box.setCurrentIndex(0)
        layout.addWidget(self.resolution_combo_box)
        separator3 = QFrame(); separator3.setFrameShape(QFrame.Shape.HLine); separator3.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator3)

        # --- Chapter Settings ---
        layout.addWidget(QLabel("チャプター設定 (HH:MM:SS)"))
        self.chapter_input = QLineEdit()
        self.add_chapter_button = QPushButton("追加")
        self.delete_chapter_button = QPushButton("選択項目を削除")
        self.chapter_list_widget = QListWidget()
        self.add_chapter_button.clicked.connect(self.add_chapter)
        self.chapter_input.returnPressed.connect(self.add_chapter)
        self.delete_chapter_button.clicked.connect(self.delete_selected_chapter)
        chapter_button_layout = QHBoxLayout()
        chapter_button_layout.addWidget(self.add_chapter_button)
        chapter_button_layout.addWidget(self.delete_chapter_button)
        layout.addWidget(self.chapter_input)
        layout.addLayout(chapter_button_layout)
        layout.addWidget(self.chapter_list_widget)
        separator4 = QFrame(); separator4.setFrameShape(QFrame.Shape.HLine); separator4.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator4)

        # --- 生成と書き込みセクション ---
        layout.addWidget(QLabel("生成と書き込み"))
        self.author_button = QPushButton("1. ISOイメージを生成") 
        self.author_button.setObjectName("encode-button")
        self.author_button.clicked.connect(self.start_authoring)
        self.drive_combo = QComboBox()
        self.drive_combo.setPlaceholderText("書き込みドライブを選択...")
        self.burn_button = QPushButton("2. ISOをディスクに書き込む")
        self.burn_button.setObjectName("burn-button")
        self.burn_button.setEnabled(False) 
        self.burn_button.clicked.connect(self.start_burning_process)
        layout.addWidget(self.author_button)
        layout.addWidget(QLabel("書き込みドライブ:"))
        layout.addWidget(self.drive_combo)
        layout.addWidget(self.burn_button)

        self.clear_property_panel()
        return panel

    def create_log_panel(self):
        panel, content = self.create_panel_widget("処理ログ")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(content)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output, 1)
        return panel

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())