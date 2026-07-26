import os
import json
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

class AuthManager:
    def __init__(self, session_name, api_id, api_hash, phone=None, password=None):
        self.session_name = session_name
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.password = password
        self.client = None
        self.session_file = f"{session_name}.session"
        self.auth_cache_file = f"{session_name}_auth.json"
    
    async def get_client(self):
        """Get or create authenticated client with persistent session"""
        if self.client and await self.client.is_user_authorized():
            return self.client
        
        # Create new client instance
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        
        try:
            await self.client.connect()
            
            # Check if already authorized (session file exists)
            if await self.client.is_user_authorized():
                print("✓ Using existing authenticated session")
                return self.client
            
            # Need to authenticate
            print("Starting authentication...")
            
            if os.getenv('BOT_TOKEN'):
                print("Authenticating with BOT_TOKEN...")
                await self.client.start(bot_token=os.getenv('BOT_TOKEN'))
            elif self.phone:
                print(f"Authenticating with phone: {self.phone}")
                try:
                    await self.client.start(
                        phone=self.phone,
                        password=self.password,
                        code_callback=self._get_code_from_input
                    )
                except SessionPasswordNeededError:
                    print("⚠️ Two-factor authentication required - please run locally once to authorize")
                    raise
            else:
                raise ValueError("No bot token or phone number provided")
            
            # Save session info
            self._save_auth_cache()
            print("✓ Authentication successful - session will be reused")
            
            return self.client
            
        except Exception as e:
            print(f"✗ Authentication failed: {e}")
            if self.client:
                await self.client.disconnect()
            raise
    
    async def _get_code_from_input(self, attempt):
        """Called when code is needed - can be overridden for automation"""
        code = input(f"Enter the code you received (attempt {attempt}): ")
        return code
    
    def _save_auth_cache(self):
        """Cache auth info for debugging"""
        cache = {
            "authenticated_at": datetime.now().isoformat(),
            "session_file": self.session_file,
            "expires_at": (datetime.now() + timedelta(days=365)).isoformat()
        }
        try:
            with open(self.auth_cache_file, 'w') as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save auth cache: {e}")
    
    async def disconnect(self):
        """Safely disconnect client"""
        if self.client:
            await self.client.disconnect()
    
    def has_valid_session(self):
        """Check if session file exists and is valid"""
        return os.path.exists(self.session_file)
    
    def clear_session(self):
        """Delete session file (forces re-authentication)"""
        if os.path.exists(self.session_file):
            os.remove(self.session_file)
            print(f"Cleared session: {self.session_file}")
        if os.path.exists(self.auth_cache_file):
            os.remove(self.auth_cache_file)
