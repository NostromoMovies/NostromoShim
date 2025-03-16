import pystray
from PIL import Image, ImageDraw
import threading
import asyncio
import sys
import os
import winreg
import re
import socket
import time
from video_player import VideoPlayer
from media_api_client import MediaAPIClient
import requests

# Configuration
username = 'Stolan'
password = '123'
DEFAULT_URL = "http://localhost:8112/api/media/stream/1"  # Default stream URL
IPC_PORT = 45678  # Port for inter-process communication

class TrayApplication:
    def __init__(self):
        self.icon = None
        self.player = None
        self.client = None
        self.loop = asyncio.new_event_loop()
        self.running = True
        self.ipc_server = None
        
        # Parse command line arguments for URL protocol handling
        self.initial_url = None
        self.parse_command_line()

    def parse_command_line(self):
        # Check if app was launched with a custom URL
        for arg in sys.argv[1:]:
            if arg.startswith('mediaapp://'):
                # Extract video_id from mediaapp://play/123 format
                match = re.search(r'mediaapp://play/(\d+)', arg)
                if match:
                    video_id = match.group(1)
                    self.initial_url = f"http://localhost:8112/api/media/stream/{video_id}"
                    print(f"Found initial URL: {self.initial_url}")

    def is_already_running(self):
        """Check if another instance is already running by trying to bind to the IPC port"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('localhost', IPC_PORT))
            # If we get here, no other instance is running
            return False
        except socket.error:
            # Port is in use, another instance is running
            return True
        finally:
            sock.close()

    def send_url_to_running_instance(self, url):
        """Send the URL to an already running instance"""
        try:
            # Connect to the running instance
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(('localhost', IPC_PORT))
            
            # Send the URL
            sock.sendall(url.encode('utf-8'))
            sock.close()
            print(f"Sent URL to running instance: {url}")
            return True
        except Exception as e:
            print(f"Failed to send URL to running instance: {e}")
            return False

    async def start_ipc_server(self):
        """Start a server to listen for commands from other instances"""
        self.ipc_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ipc_server.bind(('localhost', IPC_PORT))
        self.ipc_server.listen(5)
        self.ipc_server.setblocking(False)
        
        print(f"IPC server listening on port {IPC_PORT}")
        
        while self.running:
            try:
                # Use asyncio to handle non-blocking socket operations
                client, addr = await self.loop.sock_accept(self.ipc_server)
                print(f"IPC connection from {addr}")
                
                # Receive the URL
                data = await self.loop.sock_recv(client, 1024)
                if data:
                    url = data.decode('utf-8')
                    print(f"Received URL via IPC: {url}")
                    
                    # Schedule video playback
                    asyncio.create_task(self.async_play_video(url))
                
                client.close()
            except Exception as e:
                if self.running:  # Only print errors if we're still supposed to be running
                    print(f"IPC server error: {e}")
                await asyncio.sleep(0.1)  # Small delay to prevent CPU hogging

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

    async def async_play_video(self, url=None):
        try:
            # Use provided URL or default
            stream_url = url or DEFAULT_URL
            
            # Check stream availability
            response = requests.get(stream_url, stream=True)
            if response.status_code != 200:
                print(f"Error: HTTP {response.status_code}")
                return

            # Stop any existing player
            if self.player:
                self.player.stop()
            
            # Initialize new player
            self.player = VideoPlayer()
            self.player.play_video(stream_url)
            
        except Exception as e:
            print(f"Playback error: {e}")

    def on_play(self, icon, item):
        # Play default video
        asyncio.run_coroutine_threadsafe(self.async_play_video(), self.loop)

    def on_exit(self, icon, item):
        print("Exiting...")
        self.running = False
        if self.player:
            self.player.stop()
        if self.ipc_server:
            self.ipc_server.close()
        self.icon.stop()
        self.loop.call_soon_threadsafe(self.loop.stop)

    def setup_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem('Play Default Video', self.on_play),
            pystray.MenuItem('Exit', self.on_exit)
        )

        self.icon = pystray.Icon(
            "media_tray_app",
            icon=self.create_icon(),
            menu=menu
        )

    def register_protocol_handler(self):
        """Register the custom URL protocol handler in Windows Registry"""
        try:
            # Get the path to the current executable
            app_path = os.path.abspath(sys.argv[0])
            if app_path.endswith('.py'):
                # If running from Python script, use pythonw to avoid console window
                cmd = f'"{sys.executable}" "{app_path}" "%1"'
            else:
                # If running from executable
                cmd = f'"{app_path}" "%1"'
                
            # Create registry entries
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\mediaapp") as key:
                winreg.SetValue(key, "", winreg.REG_SZ, "URL:Media App Protocol")
                winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
                
                with winreg.CreateKey(key, r"shell\open\command") as cmd_key:
                    winreg.SetValue(cmd_key, "", winreg.REG_SZ, cmd)
                    
            print("Protocol handler registered successfully")
            return True
        except Exception as e:
            print(f"Failed to register protocol handler: {e}")
            return False

    def run(self):
        # Check if another instance is already running
        if self.initial_url and self.is_already_running():
            print("Another instance is already running. Sending URL and exiting.")
            self.send_url_to_running_instance(self.initial_url)
            return

        # Register protocol handler (only needs to be done once)
        self.register_protocol_handler()
        
        # Start the asyncio event loop in a separate thread
        def start_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        threading.Thread(target=start_loop, args=(self.loop,), daemon=True).start()

        # Initialize client in the async loop
        asyncio.run_coroutine_threadsafe(self.async_login(), self.loop)
        
        # Start the IPC server in the async loop
        asyncio.run_coroutine_threadsafe(self.start_ipc_server(), self.loop)

        # Start the tray icon in its own thread
        threading.Thread(target=self.icon.run, daemon=True).start()

        # If launched with a URL, play it
        if self.initial_url:
            asyncio.run_coroutine_threadsafe(self.async_play_video(self.initial_url), self.loop)

        # Keep main thread alive
        while self.running:
            time.sleep(0.1)  # Reduce CPU usage

if __name__ == "__main__":
    app = TrayApplication()
    app.setup_tray()
    app.run()