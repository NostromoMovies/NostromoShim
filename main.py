import mpv
import requests

# player = mpv.MPV(ytdl=True)
# player.play('https://youtu.be/DOmdB7D-pUU')
# player.wait_for_playback()

video_id = 1
stream_url = f"http://localhost:8112/api/media/stream/{video_id}"

response = requests.get(stream_url, stream=True)
if response.status_code != 200:
    print(f"Error: HTTP {response.status_code}")
    exit(1)


player = mpv.MPV(
    input_default_bindings=True,
    input_vo_keyboard=True,
    osc=True
)

try:
    player.play(stream_url)
    player.wait_for_playback()
except Exception as e:
    print(f"Playback error: {e}")