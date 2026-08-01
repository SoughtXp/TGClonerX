import sys
import os
import io
import threading
import webview
from colorama import Fore

# Safe stream redirection for PyInstaller --windowed mode
class NullStream:
    def write(self, text):
        pass
    def flush(self):
        pass
    def isatty(self):
        return False

if sys.stdout is None or not hasattr(sys.stdout, 'write'):
    sys.stdout = NullStream()
if sys.stderr is None or not hasattr(sys.stderr, 'write'):
    sys.stderr = NullStream()

from server import app

class WindowAPI:
    """JS Bridge API for PyWebView window management cleanly decoupled from circular references."""
    def minimize(self):
        if webview.windows:
            webview.windows[0].minimize()

    def toggle_maximize(self):
        if webview.windows:
            webview.windows[0].toggle_fullscreen()

    def close(self):
        if webview.windows:
            webview.windows[0].destroy()

    def open_url(self, url):
        import webbrowser
        webbrowser.open(url)

api = WindowAPI()

def start_flask():
    """Starts Flask web server in a background thread."""
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)

def main():
    """
    Application entry point for TGClonerX Windows Desktop App.
    Launches Flask backend in a background thread and presents a frameless desktop GUI window.
    """
    if '--cli' in sys.argv:
        from src.client import get_client
        from src.cloner import run_cloner
        client = get_client()
        with client:
            try:
                client.loop.run_until_complete(run_cloner(client))
            except (KeyboardInterrupt, SystemExit):
                print(f"\n{Fore.RED}CLI runner closed.")
    else:
        server_thread = threading.Thread(target=start_flask, daemon=True)
        server_thread.start()

        webview.create_window(
            title='TGClonerX',
            url='http://127.0.0.1:5000',
            width=1200,
            height=780,
            resizable=True,
            frameless=True,
            easy_drag=False,
            background_color='#000000',
            js_api=api
        )
        webview.start(debug=False)

if __name__ == '__main__':
    main()
