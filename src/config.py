import os
import sys

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

CONFIG_FILE = os.path.join(APP_DIR, "config.txt")
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")

_API_ID = None
_API_HASH = None

def get_credentials():
    """
    Retrieves or prompts for Telegram API ID and API HASH credentials.

    Returns:
        tuple (int, str): (api_id, api_hash)
    """
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            lines = f.read().splitlines()
            if len(lines) >= 2:
                try:
                    return int(lines[0].strip()), lines[1].strip()
                except ValueError:
                    pass

    print(f"{Fore.YELLOW}=== INITIAL CONFIGURATION ===")
    print(f"{Fore.WHITE}Retrieve your credentials from: {Fore.CYAN}https://my.telegram.org\n")

    while True:
        try:
            api_id = int(input(f"{Fore.GREEN}API ID (numeric): {Fore.WHITE}").strip())
            break
        except ValueError:
            print(f"{Fore.RED}Invalid ID. Must contain numbers only.")

    api_hash = input(f"{Fore.GREEN}API HASH: {Fore.WHITE}").strip()

    with open(CONFIG_FILE, "w") as f:
        f.write(f"{api_id}\n{api_hash}")

    print(f"\n{Fore.GREEN}✓ Credentials saved to {CONFIG_FILE}!\n")
    return api_id, api_hash

def load_config():
    """
    Loads cached or newly configured API credentials.

    Returns:
        tuple (int, str): (api_id, api_hash)
    """
    global _API_ID, _API_HASH
    if _API_ID is None or _API_HASH is None:
        _API_ID, _API_HASH = get_credentials()
    return _API_ID, _API_HASH
