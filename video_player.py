import threading
import os
import sys
script_dir = os.path.dirname(__file__)
os.environ["PATH"] = script_dir + os.pathsep + os.environ["PATH"]
import mpv

class VideoPlayer:
    def __init__(self):
        self.player = mpv.MPV(
            input_default_bindings=True,
            input_vo_keyboard=True,
            osc=True
        )
        self.playback_thread = None
        self._stop_event = threading.Event()

    def play_video(self, path: str):
        # Stop any existing playback
        self.stop()
        
        # Start new playback in a thread
        self.playback_thread = threading.Thread(
            target=self._play,
            args=(path,),
            daemon=True
        )
        self.playback_thread.start()

    def _play(self, path: str):
        try:
            self.player.play(path)
            while not self._stop_event.is_set() and self.player.core_idle:
                self.player.wait_for_playback()
        except mpv.ShutdownError as e:
            print(f"MPV shutdown handled: {e}")
        finally:
            self._cleanup()

    def stop(self):
        if self.playback_thread and self.playback_thread.is_alive():
            self._stop_event.set()
            self.player.terminate()
            self.playback_thread.join(timeout=1)
            self._cleanup()

    def _cleanup(self):
        self._stop_event.clear()
        if self.player:
            self.player.terminate()