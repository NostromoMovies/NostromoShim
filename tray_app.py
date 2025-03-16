import pystray
from PIL import Image, ImageDraw
import threading
import asyncio
from video_player import VideoPlayer
from media_api_client import MediaAPIClient
import requests

# Configuration
video_id = 1
stream_url = f"http://localhost:8112/api/media/stream/{video_id}"
username = 'Stolan'
password = '123'

class TrayApplication:
    def __init__(self):
        self.icon = None
        self.player = None
        self.client = None
        self.loop = asyncio.new_event_loop()
        self.running = True

    def create_icon(self):
        # Create a simple programmatic icon
        image = Image.new('RGB', (64, 64), 'white')
        dc = ImageDraw.Draw(image)
        dc.rectangle((16, 16, 48, 48), fill='blue')
        return image

    async def async_login(self):
        self.client = MediaAPIClient()
        await self.client.initialize()
        
        if not self.client.token:
            if await self.client.login(username, password):
                print("Login successful!")
            else:
                print("Login failed")
                return False
        return True

    async def async_play_video(self):
        try:
            # Check stream availability
            response = requests.get(stream_url, stream=True)
            if response.status_code != 200:
                print(f"Error: HTTP {response.status_code}")
                return

            # Initialize player
            self.player = VideoPlayer()
            self.player.play_video(stream_url)
            
        except Exception as e:
            print(f"Playback error: {e}")

    def on_play(self, icon, item):
        # Run async task in the event loop
        asyncio.run_coroutine_threadsafe(self.async_play_video(), self.loop)

    def on_exit(self, icon, item):
        print("Exiting...")
        self.running = False
        if self.player:
            self.player.stop()
        self.icon.stop()
        self.loop.call_soon_threadsafe(self.loop.stop)

    def setup_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem('Play Video', self.on_play),
            pystray.MenuItem('Exit', self.on_exit)
        )

        self.icon = pystray.Icon(
            "media_tray_app",
            icon=self.create_icon(),
            menu=menu
        )

    def run(self):
        # Start the asyncio event loop in a separate thread
        def start_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        threading.Thread(target=start_loop, args=(self.loop,), daemon=True).start()

        # Initialize client in the async loop
        asyncio.run_coroutine_threadsafe(self.async_login(), self.loop)

        # Start the tray icon in its own thread
        threading.Thread(target=self.icon.run, daemon=True).start()

        # Keep main thread alive
        while self.running:
            pass

if __name__ == "__main__":
    app = TrayApplication()
    app.setup_tray()
    app.run()