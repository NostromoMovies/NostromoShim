import mpv

# player = mpv.MPV(ytdl=True)
# player.play('https://youtu.be/DOmdB7D-pUU')
# player.wait_for_playback()

class VideoPlayer():
    def __init__(self):
        self.player = mpv.MPV(
            input_default_bindings=True,
            input_vo_keyboard=True,
            osc=True
            )
    
    def play_video(self, path: str):
        self.player.play(path)
        self.player.wait_for_playback()