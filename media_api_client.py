import keyring
import requests
from getpass import getpass
from typing import Optional
import aiohttp
import asyncio

class MediaAPIClient:
    def __init__(self, base_url: str = "http://localhost:8112"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.token: Optional[str] = None
        self.current_profile: Optional[str] = None
        self.device = "NostromoShim"

    async def initialize(self) -> None:
        """Initialize the client and load existing token"""
        self.session = aiohttp.ClientSession()
        await self._load_existing_token()

    async def close(self) -> None:
        """Close the session"""
        if self.session:
            await self.session.close()

    def _get_service_name(self) -> str:
        return f"MediaServer-{self.base_url}"

    async def _load_existing_token(self) -> None:
        """Load stored token from system keyring"""
        try:
            self.current_profile = keyring.get_password(
                self._get_service_name(), "current_profile"
            )
            if self.current_profile:
                self.token = keyring.get_password(
                    self._get_service_name(), f"{self.current_profile}_token"
                )
        except Exception as e:
            print(f"Error loading credentials: {e}")
            self.token = None
            self.current_profile = None

    async def login(self, username: str, password: Optional[str] = None) -> bool:
        """Authenticate with the server and store token securely"""
        if not password:
            password = getpass(f"Password for {username}: ")

        try:
            async with self.session.post(
                f"{self.base_url}/api/auth/login",
                json={"username": username, "password": password, "device": self.device}
            ) as response:
                response.raise_for_status()
                data = await response.json()
                token = data.get("data", {}).get("token")

                if not token:
                    print("Login failed: No token in response")
                    return False

                self.token = token
                self.current_profile = username

                # Store credentials securely
                keyring.set_password(
                    self._get_service_name(),
                    f"{username}_token",
                    self.token
                )
                keyring.set_password(
                    self._get_service_name(),
                    "current_profile",
                    username
                )
                return True
        except aiohttp.ClientError as e:
            print(f"Login failed: {e}")
            return False

    def logout(self) -> None:
        """Clear local credentials and session"""
        if self.current_profile:
            try:
                # Remove stored credentials
                keyring.delete_password(
                    self._get_service_name(),
                    f"{self.current_profile}_token"
                )
                keyring.delete_password(
                    self._get_service_name(),
                    "current_profile"
                )
            except Exception as e:
                print(f"Error clearing credentials: {e}")
        
        self.session.close()
        self.token = None
        self.current_profile = None

    async def get_authenticated(self, endpoint: str) -> Optional[dict]:
        """Make authenticated GET request"""
        if not self.token:
            raise ValueError("Not authenticated")

        try:
            async with self.session.get(
                f"{self.base_url}{endpoint}",
                headers={"Authorization": f"Bearer {self.token}"}
            ) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            print(f"Request failed: {e}")
            return None

    def clear_credentials(self) -> None:
        """Clear stored credentials from keyring for this client"""
        service_name = self._get_service_name()
        
        try:
            # Get current profile before deletion
            current_profile = keyring.get_password(service_name, "current_profile")
            
            # Delete stored entries
            if current_profile:
                keyring.delete_password(service_name, f"{current_profile}_token")
                print(f"Cleared token for profile: {current_profile}")
                
            keyring.delete_password(service_name, "current_profile")
            print("Cleared current profile entry")

            # Reset in-memory credentials
            self.token = None
            self.current_profile = None
            
        except keyring.errors.PasswordDeleteError as e:
            print(f"No credentials to delete: {e}")
        except Exception as e:
            print(f"Error clearing credentials: {e}")