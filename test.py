import torch
from pydub import AudioSegment
import zipfile
import torchaudio
from glob import glob
from speech_chunker import SpeechChunker, ShadowFormatter, SpeechComparator
import numpy as np
import pytest


def test_stt():
    bc = SpeechChunker()
    bc.url = "https://www.youtube.com/watch?v=8LLMbDXdyRI"
    bc.download()
    ft = ShadowFormatter(bc)

    (read_batch, split_into_batches,
     read_audio, prepare_model_input) = ft.utils
    test_files = glob('data.m4a')
    batches = split_into_batches(test_files, batch_size=100)
    input = prepare_model_input(read_batch(batches[0]))

    reference_output = ft._decoder(ft._model(input)[0].cpu())
    test_output = ft.subtitle(bc._data)
    assert reference_output == test_output


def test_vad():
    bc = SpeechChunker()
    bc.url = "https://www.youtube.com/watch?v=8LLMbDXdyRI"
    bc.load()

    (get_speech_timestamps, _, read_audio, _, _) = bc.utils
    wav = read_audio('data.m4a')
    reference_output = [
        (i["start"] *
         1000,
         i["end"] *
            1000) for i in get_speech_timestamps(
            wav,
            bc.model,
            sampling_rate=16000,
            threshold=0.2,
            return_seconds=True,
            speech_pad_ms=80,
            min_speech_duration_ms=1000,
            max_speech_duration_s=bc._chunk_duration,
            min_silence_duration_ms=50)]
    test_output = bc._phrases
    assert reference_output == list(test_output)


def add_noise(audio, mean=0, noise=1):
    data = np.frombuffer(audio.raw_data, np.int16).copy().astype(np.float64)
    data += np.random.normal(mean *
                             data.mean(), noise *
                             data.std(), data.shape)
    return AudioSegment(data=data.astype(np.int16),
                        sample_width=audio.sample_width, frame_rate=audio.frame_rate, channels=audio.channels)


def test_comparator():
    bc = SpeechChunker()
    bc.url = "https://www.youtube.com/watch?v=8LLMbDXdyRI"
    bc.load()
    cp = SpeechComparator()

    assert cp.compare(bc._data, bc._data) > 0.9
    assert np.abs(cp.compare(bc._data, bc._data.reverse())) < 0.1

    audio = add_noise(bc._data, noise=1e-2)
    assert cp.compare(bc._data, audio) > 0.9
