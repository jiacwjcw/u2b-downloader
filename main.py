import os
import re
import subprocess
import sys

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
)
from pytubefix import YouTube


class DownloadThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url, resolution, folder):
        super().__init__()
        self.url = url
        self.resolution = resolution
        self.folder = folder

    def sanitize_filename(self, filename):
        return re.sub(r'[\/:*?"<>|]', "_", filename)

    def progress_function(self, stream, chunk, bytes_remaining):
        total_size = stream.filesize
        downloaded_size = total_size - bytes_remaining
        progress_percentage = int(downloaded_size / total_size * 100)
        self.progress.emit(progress_percentage)

    def run(self):
        try:
            yt = YouTube(self.url, on_progress_callback=self.progress_function)
            selected_resolution = self.resolution.split(" ")[0]
            video_stream = yt.streams.filter(
                adaptive=True, file_extension="mp4", resolution=selected_resolution
            ).first()
            audio_stream = yt.streams.filter(
                only_audio=True, file_extension="mp4"
            ).first()

            if video_stream and audio_stream:
                sanitized_title = self.sanitize_filename(yt.title)
                video_path = os.path.join(self.folder, f"{sanitized_title}_video.mp4")
                audio_path = os.path.join(self.folder, f"{sanitized_title}_audio.mp4")
                output_path = os.path.join(self.folder, f"{sanitized_title}.mp4")

                video_stream.download(
                    output_path=self.folder, filename=f"{sanitized_title}_video.mp4"
                )
                audio_stream.download(
                    output_path=self.folder, filename=f"{sanitized_title}_audio.mp4"
                )

                self.merge_video_audio(video_path, audio_path, output_path)

                os.remove(video_path)
                os.remove(audio_path)

                self.finished.emit(output_path)
            else:
                self.error.emit("無法找到對應的解析度或音訊！")
        except Exception as e:
            self.error.emit(f"下載失敗：{str(e)}")

    def merge_video_audio(self, video_path, audio_path, output_path):
        """使用 ffmpeg 合併音訊與影片並顯示進度"""
        try:
            command = [
                os.path.join(os.getcwd(), "ffmpeg-windows", "bin", "ffmpeg.exe"),
                "-i",
                video_path,
                "-i",
                audio_path,
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-strict",
                "experimental",
                output_path,
            ]

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
            )

            duration = None
            for line in process.stdout:
                if "Duration" in line:
                    duration_match = re.search(
                        r"Duration: (\d+):(\d+):(\d+).(\d+)", line
                    )
                    if duration_match:
                        hours = int(duration_match.group(1))
                        minutes = int(duration_match.group(2))
                        seconds = int(duration_match.group(3))
                        duration = hours * 3600 + minutes * 60 + seconds

                if "time=" in line and duration:
                    time_match = re.search(r"time=(\d+):(\d+):(\d+).(\d+)", line)
                    if time_match:
                        hours = int(time_match.group(1))
                        minutes = int(time_match.group(2))
                        seconds = int(time_match.group(3))
                        current_time = hours * 3600 + minutes * 60 + seconds

                        progress = int((current_time / duration) * 100)
                        self.progress.emit(progress)

            process.wait()
            if process.returncode != 0:
                raise Exception("ffmpeg 合併失敗")
        except Exception as e:
            self.error.emit(f"合併失敗：{str(e)}")


class YouTubeDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Downloader")
        self.setGeometry(100, 100, 600, 450)

        # YouTube URL 輸入框
        self.url_label = QLabel("YouTube 影片網址：", self)
        self.url_label.setGeometry(50, 50, 200, 30)
        self.url_input = QLineEdit(self)
        self.url_input.setGeometry(200, 50, 350, 30)

        # 載入解析度按鈕
        self.load_button = QPushButton("載入解析度", self)
        self.load_button.setGeometry(50, 100, 150, 30)
        self.load_button.clicked.connect(self.load_resolutions)

        # 解析度下拉選單
        self.resolution_label = QLabel("選擇解析度：", self)
        self.resolution_label.setGeometry(50, 150, 200, 30)
        self.resolution_dropdown = QComboBox(self)
        self.resolution_dropdown.setGeometry(200, 150, 200, 30)

        # 選擇下載位置
        self.folder_button = QPushButton("選擇下載位置", self)
        self.folder_button.setGeometry(50, 200, 150, 30)
        self.folder_button.clicked.connect(self.select_folder)
        self.folder_label = QLabel("未選擇下載路徑", self)
        self.folder_label.setGeometry(200, 200, 350, 30)

        # 進度條
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setGeometry(50, 300, 500, 30)
        self.progress_bar.setValue(0)

        # 下載按鈕
        self.download_button = QPushButton("下載影片", self)
        self.download_button.setGeometry(50, 250, 150, 30)
        self.download_button.clicked.connect(self.download_video)

        self.download_path = ""
        self.download_thread = None

    def load_resolutions(self):
        url = self.url_input.text()
        if not url:
            QMessageBox.warning(self, "警告", "請輸入 YouTube 影片網址！")
            return

        try:
            yt = YouTube(url)
            streams = yt.streams.filter(adaptive=True, file_extension="mp4")
            resolutions = [
                f"{stream.resolution} ({stream.mime_type})"
                for stream in streams
                if stream.video_codec
            ]
            self.resolution_dropdown.clear()
            self.resolution_dropdown.addItems(resolutions)
            QMessageBox.information(self, "成功", "解析度已載入！")
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"無法載入解析度：{e}")

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "選擇下載位置")
        if folder:
            self.download_path = folder
            self.folder_label.setText(folder)

    def download_video(self):
        url = self.url_input.text()
        resolution = self.resolution_dropdown.currentText()
        folder = self.download_path

        if not url or not resolution or not folder:
            QMessageBox.warning(self, "警告", "請填寫所有欄位！")
            return

        self.download_thread = DownloadThread(url, resolution, folder)
        self.download_thread.progress.connect(self.update_progress)
        self.download_thread.finished.connect(self.download_finished)
        self.download_thread.error.connect(self.download_error)
        self.download_thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def download_finished(self, output_path):
        QMessageBox.information(self, "成功", f"影片已下載並合併至：{output_path}")
        self.progress_bar.setValue(0)

    def download_error(self, error_message):
        QMessageBox.critical(self, "錯誤", error_message)
        self.progress_bar.setValue(0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YouTubeDownloader()
    window.show()
    sys.exit(app.exec_())
