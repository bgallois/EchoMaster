from gi.repository import Gtk, GLib, Pango, Gdk
import threading
from speech_chunker import SpeechChunker, ShadowFormatter, SpeechComparator
import pyaudio
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')


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
        self.grid.attach_next_to(
            self.load,
            self.entry,
            Gtk.PositionType.RIGHT,
            1,
            1)

        self.repeat_label = Gtk.Label(label="Number of Repetitions")
        self.grid.attach_next_to(
            self.repeat_label,
            self.entry,
            Gtk.PositionType.BOTTOM,
            1,
            1)

        self.repeat = Gtk.SpinButton(
            adjustment=Gtk.Adjustment(
                value=1,
                lower=1,
                upper=10,
                step_increment=1,
                page_increment=3,
                page_size=0))
        self.repeat.connect("changed", self.on_formatter_changed)
        self.grid.attach_next_to(
            self.repeat,
            self.repeat_label,
            Gtk.PositionType.RIGHT,
            1,
            1)

        self.replay_checkbox = Gtk.CheckButton(label="Replay Performance")
        self.grid.attach_next_to(
            self.replay_checkbox,
            self.repeat,
            Gtk.PositionType.RIGHT,
            1,
            1)

        self.output_label = Gtk.Label(label="Output")
        self.grid.attach_next_to(
            self.output_label,
            self.repeat_label,
            Gtk.PositionType.BOTTOM,
            1,
            1)

        self.output = Gtk.DropDown.new_from_strings(self.list_audio_devices())
        self.output.connect("notify::selected", self.on_output_changed)
        self.grid.attach_next_to(
            self.output,
            self.output_label,
            Gtk.PositionType.RIGHT,
            1,
            1)

        self.input_label = Gtk.Label(label="Input")
        self.grid.attach_next_to(
            self.input_label,
            self.output_label,
            Gtk.PositionType.BOTTOM,
            1,
            1)

        self.input = Gtk.DropDown.new_from_strings(self.list_audio_devices())
        self.input.connect("notify::selected", self.on_input_changed)
        self.grid.attach_next_to(
            self.input,
            self.input_label,
            Gtk.PositionType.RIGHT,
            1,
            1)

        self.max_chunk_label = Gtk.Label(label="Max chunk duration")
        self.grid.attach_next_to(
            self.max_chunk_label,
            self.input_label,
            Gtk.PositionType.BOTTOM,
            1,
            1)

        self.max_chunk = Gtk.SpinButton(
            adjustment=Gtk.Adjustment(
                value=10,
                lower=5,
                upper=40,
                step_increment=5,
                page_increment=3,
                page_size=0))
        self.max_chunk.connect("changed", self.on_chunker_changed)
        self.grid.attach_next_to(
            self.max_chunk,
            self.max_chunk_label,
            Gtk.PositionType.RIGHT,
            1,
            1)

        self.sub = Gtk.Label()
        self.sub.set_markup("<span font_desc='Arial 20'>Subtitle!</span>")
        self.sub.set_vexpand(True)
        self.grid.attach_next_to(
            self.sub,
            self.max_chunk_label,
            Gtk.PositionType.BOTTOM,
            4,
            1)

        self.button = Gtk.ToggleButton(label="Start")
        self.button.connect("toggled", self.on_started)
        self.grid.attach_next_to(
            self.button, self.sub, Gtk.PositionType.BOTTOM, 4, 1)

        self._bc = SpeechChunker()
        self._data = None
        self._comparator = SpeechComparator()
        self.stop_event = threading.Event()

    def on_delete_event(self, widget, event):
        self.stop_event.set()
        return False

    def on_output_changed(self, dropdown, param):
        if self._data:
            self._data.output_device = dropdown.get_selected()

    def on_input_changed(self, dropdown, param):
        if self._data:
            self._data.input_device = dropdown.get_selected()

    def waiting(func):
        def inner(*args, **kwargs):
            args[0].set_cursor(Gdk.Cursor.new_from_name("progress"))
            GLib.MainContext.default().iteration(False)
            try:
                return func(*args, **kwargs)
            finally:
                args[0].set_cursor(None)
        return inner

    @waiting
    def on_loaded(self, button):
        self._bc.url = self.entry.get_text()
        self._bc.load()
        self._data = ShadowFormatter(self._bc)

    @waiting
    def on_chunker_changed(self, value):
        if self._data:
            self._bc.chunk_duration = int(self.max_chunk.get_value())

    @waiting
    def on_formatter_changed(self, value):
        if self._data:
            ...

    def run_audio(self):
        for s, p in self._data:
            for _ in range(int(self.repeat.get_value())):
                if self.stop_event.is_set():
                    break
                GLib.idle_add(
                    self.sub.set_markup, "<span font_desc='Arial 16'>{}</span>".format(s))
                record = self._data.play(p)
                if self.replay_checkbox.get_active():
                    self._data.play(record)
                # self._comparator.compare(p, record) # TODO more robust metric
        else:
            self._data.reset()

        self.button.set_active(False)
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
