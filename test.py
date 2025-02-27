import torch
import zipfile
import torchaudio
from glob import glob
from speech_chunker import SpeechChunker, ShadowFormatter
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
