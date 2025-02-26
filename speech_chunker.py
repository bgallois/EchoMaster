import yt_dlp
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


class SpeechChunker:

    def __init__(self, chunk_duration=10):
        self._data = None
        self._chunk_duration = chunk_duration
        self._url = None
        self._phrases = None

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

        self._data = AudioSegment.silent(duration=1000) + AudioSegment.from_file(
            "data.m4a", "m4a") + AudioSegment.silent(duration=1000)

    def process(self):
        audio = np.frombuffer(self._data.raw_data, np.uint16)
        audio = audio.reshape(
            len(audio) //
            self._data.channels,
            self._data.channels).sum(
            axis=1)
        audio = audio.astype(np.float32) / np.max(np.abs(audio))
        resampler = torchaudio.transforms.Resample(
            orig_freq=self._data.frame_rate, new_freq=16000)
        audio = torch.tensor(audio).unsqueeze(0).float()
        audio = resampler(audio)
        vad_model, utils = torch.hub.load(
            'snakers4/silero-vad', model='silero_vad')
        nonsilent_chunks = [
            (i["start"] *
             1000,
             i["end"] *
                1000) for i in utils[0](
                audio,
                vad_model,
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
        self._output_device = 1
        self._model, self._decoder, self.utils = torch.hub.load(
            'snakers4/silero-models', model='silero_stt', onnx_model='jit_xlarge', language='en')

    def __iter__(self):
        return self

    def __next__(self):
        return self.format()

    def reset(self):
        self._phrases.reset()

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
        for _ in range(self._repeat):
            shadow += i
            shadow += AudioSegment.silent(duration=len(i))
        return sub, shadow

    def subtitle(self, segment):
        audio = np.frombuffer(segment.raw_data, np.uint16)
        audio = audio.reshape(
            len(audio) //
            segment.channels,
            segment.channels).sum(
            axis=1)
        audio = audio.astype(np.float32) / np.max(np.abs(audio))
        resampler = torchaudio.transforms.Resample(
            orig_freq=segment.frame_rate, new_freq=16000)
        audio = torch.tensor(audio).unsqueeze(0).float()
        audio = resampler(audio)
        input_audio = self.utils[3](audio)
        transcriptions = self._model(input_audio)
        return self._decoder(transcriptions[0].cpu())

    def play(self, segment):
        try:
            p = pyaudio.PyAudio()
            audio_data = segment.raw_data

            stream = p.open(format=p.get_format_from_width(segment.sample_width),
                            channels=segment.channels,
                            rate=segment.frame_rate,
                            output_device_index=self._output_device,
                            output=True)

            stream.write(audio_data)
            stream.stop_stream()
            stream.close()
            p.terminate()
        except BaseException:
            pass
