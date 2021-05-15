import os
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    pass

VOICE_URL = os.getenv('VOICE_URL', '')
VOICE_URL = VOICE_URL.rstrip('/')


def transcribe_audio(audio: str):
    try:
        text = requests.post(url='{}/{}'.format(VOICE_URL, 'stt'), json={'audio': audio})
        text = text.json().get('text')
    except requests.exceptions.RequestException:
        text = ''
    return text


def synthesize_text(text: str):
    try:
        audio = requests.post(url='{}/{}'.format(VOICE_URL, 'tts'), json={'text': text})
        audio = audio.json().get('audio')
    except requests.exceptions.RequestException:
        audio = None
    return audio
