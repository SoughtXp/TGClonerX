import os
import sys
from telethon import TelegramClient
from src.config import load_config, APP_DIR

_client = None
SESSION_FILE = os.path.join(APP_DIR, "app_session")

def get_client(session_name=None, loop=None):
    """
    Retrieves or initializes singleton TelegramClient instance.
    """
    global _client
    if session_name is None:
        session_name = SESSION_FILE

    if _client is None:
        api_id, api_hash = load_config()
        _client = TelegramClient(session_name, api_id, api_hash, loop=loop)
    return _client
