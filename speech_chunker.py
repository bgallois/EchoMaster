import yt_dlp
from fastdtw import fastdtw
import time
import threading
import torch
import torchaudio
import requests
import pyaudio
import os
import numpy as np
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
from pydub import AudioSegment
import speech_recognition as sr
import scipy


class SpeechChunker:

    def __init__(self, chunk_duration=10):
        self._data = None
        self._chunk_duration = chunk_duration
        self._url = None
        self._phrases = None
        self.model, self.utils = torch.hub.load(
            'snakers4/silero-vad', model='silero_vad')

    def __iter__(self):
        return self

    def __next__(self):
        start, end = next(self._phrases)
        return self._data[start:end]

    def reset(self):
        self.process()

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, url):
        self._url = url

    @property
    def chunk_duration(self):
        return self._chunk_duration

    @chunk_duration.setter
    def chunk_duration(self, chunk_duration):
        self._chunk_duration = chunk_duration
        self.process()

    def load(self):
        self.download()
        self.process()

    def download(self):
        if self._url is None:
            return None

        ydl_opts = {
            'format': 'm4a/bestaudio/best',
            'outtmpl': 'data.m4a',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }]
        }

        # TODO: direct access
        try:
            os.remove("data.m4a")
        except BaseException:
            pass
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download(self._url)

        self._data = AudioSegment.from_file(
            "data.m4a", "m4a")

    def process(self):
        audio = np.frombuffer(self._data.raw_data, np.int16).copy()
        audio = audio.reshape(
            len(audio) //
            self._data.channels,
            self._data.channels).mean(
            axis=1)
        audio = audio.astype(np.float32) / 32767.5
        resampler = torchaudio.transforms.Resample(
            orig_freq=self._data.frame_rate, new_freq=16000)
        audio = torch.tensor(audio).unsqueeze(0)
        audio = resampler(audio)
        nonsilent_chunks = [
            (i["start"] *
             1000,
             i["end"] *
                1000) for i in self.utils[0](
                audio,
                self.model,
                sampling_rate=16000,
                threshold=0.2,
                return_seconds=True,
                speech_pad_ms=80,
                min_speech_duration_ms=1000,
                max_speech_duration_s=self._chunk_duration,
                min_silence_duration_ms=50)]
        self._phrases = iter(nonsilent_chunks)


class ShadowFormatter:

    def __init__(self, speech_chunker, repeat=1):
        self._phrases = speech_chunker
        self._repeat = repeat
        self._output_device = 2
        self._input_device = 7
        self._start_event = threading.Event()
        self._model, self._decoder, self.utils = torch.hub.load(
            'snakers4/silero-models', model='silero_stt', jit_model='jit_xlarge', language='en')

    def __iter__(self):
        return self

    def __next__(self):
        return self.format()

    def reset(self):
        self._phrases.reset()

    @property
    def input_device(self):
        return self._input

    @input_device.setter
    def input_device(self, input_device):
        self._input_device = input_device

    @property
    def repeat(self):
        return self._repeat

    @repeat.setter
    def repeat(self, repeat):
        self._repeat = repeat

    @property
    def output_device(self):
        return self._output

    @output_device.setter
    def output_device(self, output_device):
        self._output_device = output_device

    def format(self):
        shadow = AudioSegment.silent(duration=100)
        i = next(self._phrases)
        sub = self.subtitle(i)
        shadow += i
        shadow += AudioSegment.silent(duration=len(i))
        return sub, shadow

    def subtitle(self, segment):
        audio = np.frombuffer(segment.raw_data, np.int16)
        audio = audio.reshape(
            len(audio) //
            segment.channels,
            segment.channels).mean(
            axis=1)
        audio = audio.astype(np.float32) / 32767.5
        resampler = torchaudio.transforms.Resample(
            orig_freq=segment.frame_rate, new_freq=16000)
        audio = torch.tensor(audio).unsqueeze(0)
        audio = resampler(audio)
        input_audio = self.utils[3](audio)
        transcriptions = self._model(input_audio)
        return self._decoder(transcriptions[0].cpu())

    def play_audio(self, stream, audio):
        self._start_event.wait()
        stream.write(audio)

    def record_audio(self, stream, frames, duration):
        self._start_event.wait()
        start_time = time.time()
        while time.time() - start_time < duration / 1000:
            input_audio = stream.read(512)
            frames.append(input_audio)

    def play(self, segment):
        # try:
        p = pyaudio.PyAudio()
        audio_data = segment.raw_data

        stream_out = p.open(format=p.get_format_from_width(segment.sample_width),
                            channels=segment.channels,
                            rate=segment.frame_rate,
                            output_device_index=self._output_device,
                            output=True)

        stream_in = p.open(format=pyaudio.paInt16,
                           channels=1,
                           frames_per_buffer=512,
                           rate=44100,
                           input_device_index=self._input_device,
                           input=True)
        frames = []
        record_thread = threading.Thread(
            target=self.record_audio, args=(
                stream_in, frames, len(segment)))
        play_thread = threading.Thread(
            target=self.play_audio, args=(
                stream_out, audio_data))

        record_thread.start()
        play_thread.start()
        self._start_event.set()

        play_thread.join()
        record_thread.join()

        stream_out.stop_stream()
        stream_in.stop_stream()
        stream_out.close()
        stream_in.close()

        p.terminate()
        self._start_event.clear()

        return AudioSegment(data=b''.join(frames),
                            sample_width=2, frame_rate=44100, channels=1)
        # except BaseException:
        #   pass


class SpeechComparator:

    def __init__(self):
        self._model = torchaudio.models.wav2vec2_large()
        self._model.eval()

    def extract_features(self, segment):
        audio = np.frombuffer(segment.raw_data, np.int16)
        audio = audio.reshape(
            len(audio) //
            segment.channels,
            segment.channels).mean(
            axis=1)
        audio = audio.astype(np.float32) / 32767.5
        resampler = torchaudio.transforms.Resample(
            orig_freq=segment.frame_rate, new_freq=16000)
        audio = torch.tensor(audio).unsqueeze(0)
        audio = resampler(audio)
        features, _ = self._model.extract_features(waveforms=audio)
        return features[4].squeeze(0)

    def preprocess(self, reference, audio):
        cut = len(reference) // 2
        reference = reference[:cut]
        audio = audio[cut:]
        return (reference, audio)

    def normalize(self, feature):
        return (feature - feature.mean()) / (feature.std() + 1e-8)

    def compare(self, reference, audio):
        reference, audio = self.preprocess(reference, audio)
        reference = self.normalize(self.extract_features(reference))
        audio = self.normalize(self.extract_features(audio))
        if (diff := reference.shape[0] - audio.shape[0]) < 0:
            audio = audio[:len(reference)]
        elif diff > 0:
            audio = torch.nn.functional.pad(audio, (diff, 0))
        distance, path = fastdtw(reference.detach().numpy(
        ).T, audio.detach().numpy().T, dist=scipy.spatial.distance.cosine)
        return 1 / (1 + distance)
