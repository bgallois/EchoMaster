# EchoMaster

## Overview
**EchoMaster** is a tool designed to assist with **audio mimicking** (also known as **shadowing**)—a language learning technique that improves pronunciation, rhythm, and fluency in a second language. Finding suitable material and manually handling playback can be tedious, especially with constant rewinding. EchoMaster simplifies this process by allowing users to:

- Select a **YouTube video** as their audio source.
- Automatically **chunk the audio** into short, complete phrases.
- Generate an **audio track** where each phrase is followed by a pause of the same duration, facilitating effective shadowing.
- Optionally **autogenerate subtitles** to aid comprehension.

## Current Status
EchoMaster is currently in the **prototyping stage**, featuring:
- A **minimal GTK-based interface** for selecting and managing playback.
- A **speech chunker** using **pydub** to segment audio into full phrases.
- **Audio playback** handled via **pyaudio**.
- **Automatic subtitle generation** using **SpeechRecognition**.

## Future Enhancements
Planned improvements include:
- A more **refined UI** with better usability and customization options.
- Support for **additional subtitle sources** and **manual subtitle editing**.
- Improved **chunking accuracy** using machine learning or alternative audio processing techniques.
- **Cross-platform support** and more user-friendly installation options.

## License
This project is licensed under the **MIT License**.

