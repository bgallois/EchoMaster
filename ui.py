import pyaudio
from speech_chunker import SpeechChunker, ShadowFormatter
import threading
from gi.repository import Gtk, GLib
import gi
gi.require_version('Gtk', '4.0')


class MainWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Echo Master")

        self.grid = Gtk.Grid()
        self.set_child(self.grid)

        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Youtube URL")
        self.entry.set_hexpand(True)
        self.grid.attach(self.entry, 0, 0, 3, 1)

        self.load = Gtk.Button(label="Load")
        self.load.connect("clicked", self.on_loaded)
        self.grid.attach(self.load, 4, 0, 1, 1)

        self.repeat_label = Gtk.Label(label="Repeat")
        self.grid.attach(self.repeat_label, 0, 1, 1, 1)

        self.repeat = Gtk.SpinButton(
            adjustment=Gtk.Adjustment(
                value=1,
                lower=1,
                upper=10,
                step_increment=1,
                page_increment=3,
                page_size=0))
        self.repeat.connect("changed", self.on_params_changed)
        self.grid.attach(self.repeat, 1, 1, 1, 1)

        self.output_label = Gtk.Label(label="Output")
        self.grid.attach(self.output_label, 0, 2, 1, 1)

        self.output = Gtk.DropDown.new_from_strings(self.list_audio_devices())
        self.output.connect("notify::selected", self.on_output_changed)
        self.grid.attach(self.output, 1, 2, 1, 1)

        self.sub = Gtk.Label(label="Subtitle")
        self.sub.set_vexpand(True)
        self.grid.attach(self.sub, 0, 3, 6, 1)

        self.button = Gtk.ToggleButton(label="Start")
        self.button.connect("toggled", self.on_started)
        self.grid.attach(self.button, 0, 4, 6, 1)

        self._bc = SpeechChunker()
        self._data = None
        self.stop_event = threading.Event()

    def on_delete_event(self, widget, event):
        self.stop_event.set()
        return False

    def on_output_changed(self, dropdown, param):
        if self._data:
            self._data.output_device = dropdown.get_selected()

    def on_loaded(self, button):
        self._bc.url = self.entry.get_text()
        self._data = ShadowFormatter(self._bc, int(self.repeat.get_value()))

    def on_params_changed(self, value):
        if self._data:
            self._data = ShadowFormatter(
                self._bc, int(self.repeat.get_value()))

    def run_audio(self):
        for s, p in self._data:
            if self.stop_event.is_set():
                break
            GLib.idle_add(self.sub.set_label, s)
            self._data.play(p)

        self.button.set_active(False)
        self._data.reset()
        self.button.set_label("Play")

    def on_started(self, button):
        if self._data is None:
            return

        if self.button.get_active():
            self.button.set_label("Stop")
            self.stop_event.clear()
            thread = threading.Thread(target=self.run_audio)
            thread.start()
        else:
            self.stop_event.set()

    def list_audio_devices(self):
        p = pyaudio.PyAudio()
        device_count = p.get_device_count()

        devices = []
        for i in range(device_count):
            device_info = p.get_device_info_by_index(i)
            devices.append(f"Device {i}: {device_info['name']}")
        p.terminate()

        return devices


class MyApp(Gtk.Application):
    def __init__(self):
        super().__init__()

    def do_activate(self):
        window = MainWindow()
        window.set_application(self)
        window.set_visible(True)


if __name__ == "__main__":
    app = MyApp()
    app.run()
