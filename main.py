from video_player import VideoPlayer
from media_api_client import  MediaAPIClient
import requests
import asyncio

video_id = 1
stream_url = f"http://localhost:8112/api/media/stream/{video_id}"


async def main():
    client = MediaAPIClient()
    await client.initialize()

    print(f"Initial token: {client.token}")

    if client.token is None:

        username = 'Stolan'
        password = '123'
        if await client.login(username, password):
            print("Login successful!")
            print(f"Token: {client.token}")
        else:
            print("Login failed")


    response = requests.get(stream_url, stream=True)
    if response.status_code != 200:
        print(f"Error: HTTP {response.status_code}")
        exit(1)


    player = VideoPlayer()

    try:
        player.play_video(stream_url)
    except Exception as e:
        print(f"Playback error: {e}")


asyncio.run( main() )