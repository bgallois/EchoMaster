from PySide6.QtWidgets import (QApplication, QWidget, QGridLayout, QPushButton, QLineEdit, QLabel,
                               QSpinBox, QCheckBox, QComboBox, QPlainTextEdit)
from PySide6.QtCore import Qt, QThread, Signal
import pyaudio
import threading
from speech_chunker import SpeechChunker, ShadowFormatter, SpeechComparator


def waiting(func):
    def inner(*args, **kwargs):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            return func(*args, **kwargs)
        finally:
            QApplication.restoreOverrideCursor()
    return inner


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Echo Master")

        self.layout = QGridLayout()
        self.setLayout(self.layout)

        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Youtube URL")
        self.layout.addWidget(self.entry, 0, 0, 1, 3)

        self.load_button = QPushButton("Load")
        self.load_button.clicked.connect(self.on_loaded)
        self.layout.addWidget(self.load_button, 0, 3, 1, 1)

        self.repeat_label = QLabel("Number of Repetitions")
        self.layout.addWidget(self.repeat_label, 1, 0)

        self.repeat_spinbox = QSpinBox()
        self.repeat_spinbox.setRange(1, 10)
        self.layout.addWidget(self.repeat_spinbox, 1, 1)

        self.replay_checkbox = QCheckBox("Replay Performance")
        self.layout.addWidget(self.replay_checkbox, 1, 2)

        self.output_label = QLabel("Output")
        self.layout.addWidget(self.output_label, 2, 0)

        self.output_dropdown = QComboBox()
        self.output_dropdown.addItems(self.list_audio_devices())
        self.output_dropdown.currentIndexChanged.connect(
            self.on_output_changed)
        self.layout.addWidget(self.output_dropdown, 2, 1, 1, 2)

        self.input_label = QLabel("Input")
        self.layout.addWidget(self.input_label, 3, 0)

        self.input_dropdown = QComboBox()
        self.input_dropdown.addItems(self.list_audio_devices())
        self.input_dropdown.currentIndexChanged.connect(self.on_input_changed)
        self.layout.addWidget(self.input_dropdown, 3, 1, 1, 2)

        self.max_chunk_label = QLabel("Max chunk duration")
        self.layout.addWidget(self.max_chunk_label, 4, 0)

        self.max_chunk_spinbox = QSpinBox()
        self.max_chunk_spinbox.setRange(5, 40)
        self.max_chunk_spinbox.setSingleStep(5)
        self.max_chunk_spinbox.valueChanged.connect(self.on_chunker_changed)
        self.layout.addWidget(self.max_chunk_spinbox, 4, 1)

        self.subtitle_label = QLabel("Subtitle!")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.subtitle_label, 5, 0, 1, 4)

        self.start_button = QPushButton("Start")
        self.start_button.setCheckable(True)
        self.start_button.clicked.connect(self.on_started)
        self.layout.addWidget(self.start_button, 6, 0, 1, 4)

        self._bc = SpeechChunker()
        self._data = None
        self._comparator = SpeechComparator()
        self.stop_event = threading.Event()

    @waiting
    def on_loaded(self):
        self._bc.url = self.entry.text()
        self._bc.load()
        self._data = ShadowFormatter(self._bc)

    def on_output_changed(self, value):
        if self._data:
            self._data.output_device = value

    def on_input_changed(self, value):
        if self._data:
            self._data.input_device = value

    @waiting
    def on_chunker_changed(self, value):
        if self._data:
            self._bc.chunk_duration = value

    def run_audio(self):
        for s, p in self._data:
            for _ in range(self.repeat_spinbox.value()):
                if self.stop_event.is_set():
                    break
                self.subtitle_label.setText(s)
                record = self._data.play(p)
                if self.replay_checkbox.isChecked():
                    self._data.play(record)
        else:
            self._data.reset()

        self.start_button.setChecked(False)
        self.start_button.setText("Start")

    def on_started(self):
        if self._data is None:
            return

        if self.start_button.isChecked():
            self.start_button.setText("Stop")
            self.stop_event.clear()
            thread = threading.Thread(target=self.run_audio)
            thread.start()
        else:
            self.stop_event.set()
            self.start_button.setText("Start")

    def list_audio_devices(self):
        p = pyaudio.PyAudio()
        device_count = p.get_device_count()
        devices = [p.get_device_info_by_index(
            i)['name'] for i in range(device_count)]
        p.terminate()
        return devices


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
