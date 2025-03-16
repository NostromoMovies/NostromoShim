import pystray
from PIL import Image, ImageDraw
import threading
import asyncio
import sys
import os
import time
import winreg
import re
import socket
import aiohttp
from video_player import VideoPlayer
from media_api_client import MediaAPIClient

# Configuration
USERNAME = 'Stolan'
PASSWORD = '123'
DEFAULT_URL = "http://localhost:8112/api/media/stream/1"
IPC_PORT = 45678
PROTOCOL_HANDLER = 'mediaapp'

class TrayApplication:
    def __init__(self):
        self.icon = None
        self.player = None
        self.client = None
        self.loop = asyncio.new_event_loop()
        self.running = True
        self.ipc_server = None
        self.initial_url = self._parse_command_line()
        self.session = None  # aiohttp session

    async def _async_init(self):
        """Initialize async resources"""
        self.session = aiohttp.ClientSession()
        self.client = MediaAPIClient(session=self.session)
        await self.client.initialize()
        
        if not await self._ensure_logged_in():
            sys.exit("Failed to login")

    async def _ensure_logged_in(self):
        if not self.client.token:
            return await self.client.login(USERNAME, PASSWORD)
        return True

    def _parse_command_line(self):
        for arg in sys.argv[1:]:
            if arg.startswith(f'{PROTOCOL_HANDLER}://'):
                match = re.search(rf'{PROTOCOL_HANDLER}://play/(\d+)', arg)
                return f"http://localhost:8112/api/media/stream/{match.group(1)}" if match else None

    def _is_already_running(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(('localhost', IPC_PORT))
                return False
            except OSError:
                return True

    def _send_to_existing_instance(self, url):
        try:
            with socket.create_connection(('localhost', IPC_PORT), timeout=1) as sock:
                sock.sendall(url.encode())
                return True
        except (socket.error, TimeoutError):
            return False

    async def _handle_ipc_client(self, reader, writer):
        try:
            data = await reader.read(1024)
            if data:
                await self.async_play_video(data.decode())
        finally:
            writer.close()

    async def _start_ipc_server(self):
        try:
            self.ipc_server = await asyncio.start_server(
                self._handle_ipc_client, 'localhost', IPC_PORT
            )
            async with self.ipc_server:
                await self.ipc_server.serve_forever()
        except asyncio.CancelledError:
            print("IPC server stopped")

    def _create_tray_icon(self):
        image = Image.new('RGB', (64, 64), 'white')
        ImageDraw.Draw(image).rectangle((16, 16, 48, 48), fill='blue')
        return image

    async def async_play_video(self, url=None):
        stream_url = url or DEFAULT_URL
        
        async with self.session.get(stream_url) as response:
            if response.status != 200:
                print(f"Stream unavailable: HTTP {response.status}")
                return

            if self.player:
                self.player.stop()
                
            self.player = VideoPlayer()
            self.player.play_video(stream_url)

    def _on_play(self, icon, item):
        asyncio.run_coroutine_threadsafe(self.async_play_video(), self.loop)

    async def _cleanup(self):
        print("Cleaning up resources...")
        
        if self.ipc_server:
            self.ipc_server.close()
            await self.ipc_server.wait_closed()

        if self.player:
            self.player.stop()

        if self.session:
            await self.session.close()

        if self.client:
            await self.client.close()

    def _on_exit(self, icon, item):
        self.running = False
        asyncio.run_coroutine_threadsafe(self._shutdown(), self.loop)

    async def _shutdown(self):
        await self._cleanup()
        self.loop.stop()
        if self.icon:
            self.icon.stop()

    def _setup_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem('Play Default', self._on_play),
            pystray.MenuItem('Exit', self._on_exit)
        )
        self.icon = pystray.Icon(
            "media_tray",
            icon=self._create_tray_icon(),
            menu=menu
        )

    def _register_protocol_handler(self):
        try:
            exe_path = os.path.abspath(sys.argv[0])
            cmd = f'"{sys.executable}" "{exe_path}" "%1"' if exe_path.endswith('.py') else f'"{exe_path}" "%1"'
            
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{PROTOCOL_HANDLER}") as key:
                winreg.SetValue(key, "", winreg.REG_SZ, f"URL:{PROTOCOL_HANDLER} Protocol")
                winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
                
                with winreg.CreateKey(key, r"shell\open\command") as cmd_key:
                    winreg.SetValue(cmd_key, "", winreg.REG_SZ, cmd)
        except Exception as e:
            print(f"Protocol registration failed: {e}")

    def run(self):
        if self.initial_url and self._is_already_running():
            if self._send_to_existing_instance(self.initial_url):
                return

        self._register_protocol_handler()

        # Start async loop
        threading.Thread(
            target=self.loop.run_forever,
            daemon=True
        ).start()

        # Initialize async components
        asyncio.run_coroutine_threadsafe(self._async_init(), self.loop)
        asyncio.run_coroutine_threadsafe(self._start_ipc_server(), self.loop)

        # Start tray
        self._setup_tray()
        threading.Thread(target=self.icon.run, daemon=True).start()

        # Play initial URL if provided
        if self.initial_url:
            asyncio.run_coroutine_threadsafe(
                self.async_play_video(self.initial_url), 
                self.loop
            )

        # Keep main thread responsive
        try:
            while self.running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            self._on_exit(None, None)

if __name__ == "__main__":
    TrayApplication().run()