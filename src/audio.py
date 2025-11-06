from dataclasses import dataclass
import queue
import time
from playaudio import playaudio

from src.base import Queues


sound_files_map = {
    "hit": "./src/sound/hit.mp3",
    "turn": "./src/sound/turn.mp3",
    "move": "./src/sound/move.mp3",
    "kill": "./src/sound/kill.mp3",
}


@dataclass
class SoundEvent:
    name: str


def run_sound_thread():
    print("[SOUND THREAD] Running")
    while True:
        while not Queues.SOUND_QUEUE.empty():
            try:
                sound_event: SoundEvent = Queues.SOUND_QUEUE.get_nowait()
                print(f"[SOUND THREAD] GOT {sound_event}")
                playaudio(sound_files_map[sound_event.name])
            except queue.Empty:
                break
        time.sleep(0.2)
