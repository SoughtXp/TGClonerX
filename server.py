import os
import sys
import io
import json
import queue
import asyncio
import threading
import sqlite3
import re
import traceback
from flask import Flask, request, jsonify, Response, render_template

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

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from telethon import TelegramClient, functions
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.types import Channel, MessageMediaWebPage

from src.config import CONFIG_FILE, APP_DIR, SETTINGS_FILE
from src.client import get_client as src_get_client
from src.database import init_db, is_already_cloned, register_clone, clear_clone_history, get_cloned_message_map
from src.text_processor import process_message_text, should_skip_message
from telethon.extensions import html

if getattr(sys, 'frozen', False):
    base_dir = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))
else:
    base_dir = os.path.abspath(os.path.dirname(__file__))

template_dir = os.path.join(base_dir, 'src', 'templates')
static_dir = os.path.join(base_dir, 'src', 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.secret_key = 'tg_cloner_x_web_secret_key'

sse_listeners = []
sse_lock = threading.Lock()

loop = None
async_thread = None
phone_code_hash = None
current_phone = None
cloning_task = None
cloning_cancelled = False
cloning_active = False

def get_client():
    """Retrieves Telethon client instance tied to global asyncio event loop."""
    return src_get_client(loop=loop)

def broadcast(event_type, data):
    """
    Broadcasts real-time events to all active SSE listener queues.

    Parameters:
        event_type (str): Event topic type ('log', 'progress', etc.).
        data (any): Event payload data.
    """
    event = {"type": event_type, "data": data}
    with sse_lock:
        for q in sse_listeners:
            q.put(event)

def start_async_loop():
    """Runs a dedicated background asyncio event loop thread for Telethon networking operations."""
    global loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_forever()

async_thread = threading.Thread(target=start_async_loop, daemon=True)
async_thread.start()

import concurrent.futures

def run_async(coro, timeout=20):
    """
    Schedules a coroutine onto the background event loop thread and blocks until complete or timed out.

    Parameters:
        coro (coroutine): Async coroutine to execute.
        timeout (int): Timeout in seconds before raising TimeoutError.

    Returns:
        any: Coroutine result.
    """
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=timeout)

FILTERS_FILE = "filters.json"
TRACKED_LINKS_FILE = "tracked_links.json"

def load_filters():
    """Loads saved filter settings from filters.json."""
    if os.path.exists(FILTERS_FILE):
        try:
            with open(FILTERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "source_id": "",
        "dest_id": "",
        "blocked_words": "",
        "skip_links": False,
        "clone_text": True,
        "clone_media": True,
        "auto_map_topics": True,
        "auto_map_mentions": True,
        "replacements": "",
        "link_rules": []
    }

def save_filters(filters):
    """Saves filter settings to filters.json."""
    try:
        with open(FILTERS_FILE, "w", encoding="utf-8") as f:
            json.dump(filters, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving filters: {e}")

def load_tracked_links():
    """Loads cached scan results from tracked_links.json."""
    if os.path.exists(TRACKED_LINKS_FILE):
        try:
            with open(TRACKED_LINKS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_tracked_links(links):
    """Saves scan results to tracked_links.json."""
    try:
        with open(TRACKED_LINKS_FILE, "w", encoding="utf-8") as f:
            json.dump(links, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving tracked links: {e}")

@app.route('/')
def index():
    """Renders main dashboard Web UI."""
    return render_template('index.html')

@app.route('/api/status', methods=['GET'])
def get_status():
    """Returns application initialization, authentication state, and filter settings."""
    config_configured = os.path.exists(CONFIG_FILE)
    api_id = None
    api_hash = None

    if config_configured:
        try:
            with open(CONFIG_FILE, "r") as f:
                lines = f.read().splitlines()
                if len(lines) >= 2:
                    api_id = lines[0].strip()
                    api_hash = lines[1].strip()
        except Exception:
            pass

    authorized = False
    phone = current_phone

    if config_configured:
        client = get_client()
        try:
            if not client.is_connected():
                run_async(client.connect())
            authorized = run_async(client.is_user_authorized())
            if authorized and not phone:
                me = run_async(client.get_me())
                if me:
                    phone = getattr(me, 'phone', None) or getattr(me, 'first_name', 'Authorized Account')
        except Exception as e:
            authorized = False

    return jsonify({
        "config_configured": config_configured,
        "api_id": api_id,
        "api_hash": api_hash,
        "authorized": authorized,
        "phone": phone,
        "settings": load_settings(),
        "filters": load_filters(),
        "tracked_links": load_tracked_links()
    })

@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Saves user preferences (language, theme)."""
    data = request.json or {}
    settings = load_settings()
    if 'language' in data:
        settings['language'] = data['language']
    if 'theme' in data:
        settings['theme'] = data['theme']
    save_settings(settings)
    return jsonify({"success": True, "settings": settings})

@app.route('/api/config', methods=['POST'])
def save_config():
    """Saves API ID and API HASH credentials."""
    data = request.json or {}
    api_id = data.get('api_id', '').strip()
    api_hash = data.get('api_hash', '').strip()

    if not api_id or not api_hash:
        return jsonify({"success": False, "error": "API ID and API HASH are required."}), 200

    try:
        with open(CONFIG_FILE, "w") as f:
            f.write(f"{api_id}\n{api_hash}")

        global src_get_client, _client
        import src.client
        src.client._client = None
        src.client._API_ID = int(api_id)
        src.client._API_HASH = api_hash

        client = get_client()
        if client.is_connected():
            run_async(client.disconnect())
        run_async(client.connect())

        broadcast("log", "Telegram API credentials saved successfully.")
        return jsonify({"success": True})
    except Exception as e:
        err_msg = str(e)
        if "api_id" in err_msg.lower() or "hash" in err_msg.lower():
            err_msg = "Invalid Telegram API ID or API HASH format. Please check credentials from my.telegram.org."
        return jsonify({"success": False, "error": err_msg}), 200

@app.route('/api/auth/send_code', methods=['POST'])
def send_code():
    """Sends phone verification code via Telegram API."""
    data = request.json or {}
    phone = data.get('phone', '').strip()

    if not phone:
        return jsonify({"success": False, "error": "Phone number is required."}), 200

    if not os.path.exists(CONFIG_FILE):
        return jsonify({"success": False, "error": "Please enter and save your Telegram API ID and API HASH above first."}), 200

    client = get_client()
    try:
        if not client.is_connected():
            run_async(client.connect())

        res = run_async(client.send_code_request(phone))
        global phone_code_hash, current_phone
        phone_code_hash = res.phone_code_hash
        current_phone = phone

        broadcast("log", f"Verification code sent to {phone}. Check your Telegram app.")
        return jsonify({"success": True})
    except Exception as e:
        err_msg = str(e)
        if "ApiIdInvalid" in err_msg or "API_ID_INVALID" in err_msg:
            err_msg = "Invalid API ID/HASH credentials. Please check your API credentials in Accounts & API tab."
        elif "PhoneNumberInvalid" in err_msg or "PHONE_NUMBER_INVALID" in err_msg:
            err_msg = "Invalid phone number format. Please ensure country code (e.g. +55) is correct."
        elif "FloodWait" in err_msg:
            err_msg = "Telegram rate limit reached (FloodWait). Please wait a few minutes before trying again."
        return jsonify({"success": False, "error": err_msg}), 200

@app.route('/api/auth/sign_in', methods=['POST'])
def sign_in():
    """Signs in user using verification code."""
    data = request.json or {}
    code = data.get('code', '').strip()

    if not code or not current_phone or not phone_code_hash:
        return jsonify({"success": False, "error": "Invalid verification session. Please request code again."}), 200

    client = get_client()
    try:
        run_async(client.sign_in(current_phone, code, phone_code_hash=phone_code_hash))
        broadcast("log", f"Account successfully connected ({current_phone}).")
        return jsonify({"success": True})
    except SessionPasswordNeededError:
        return jsonify({"success": False, "requires_2fa": True})
    except Exception as e:
        err_msg = str(e)
        if "PhoneCodeInvalid" in err_msg or "PHONE_CODE_INVALID" in err_msg:
            err_msg = "Incorrect verification code. Please check the code sent to your Telegram app."
        elif "PhoneCodeExpired" in err_msg or "PHONE_CODE_EXPIRED" in err_msg:
            err_msg = "Verification code expired. Please click Back and send code again."
        return jsonify({"success": False, "error": err_msg}), 200

@app.route('/api/auth/2fa', methods=['POST'])
def auth_2fa():
    """Submits 2FA password for account verification."""
    data = request.json or {}
    password = data.get('password', '').strip()

    if not password:
        return jsonify({"success": False, "error": "2FA password is required."}), 200

    client = get_client()
    try:
        run_async(client.sign_in(password=password))
        broadcast("log", "2FA authentication verified successfully.")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": f"2FA verification failed: {str(e)}"}), 200

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logs out and disconnects Telegram session."""
    client = get_client()
    try:
        if client.is_connected():
            run_async(client.log_out())
        global current_phone, phone_code_hash
        current_phone = None
        phone_code_hash = None
        broadcast("log", "Account disconnected.")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/chats', methods=['GET'])
def get_chats():
    """Returns list of user channels and groups."""
    if not os.path.exists(CONFIG_FILE):
        return jsonify({"success": False, "error": "Please configure Telegram API ID and API HASH first in Accounts & API tab."}), 200

    client = get_client()
    try:
        if not client.is_connected():
            run_async(client.connect())

        authorized = run_async(client.is_user_authorized())
        if not authorized:
            return jsonify({"success": False, "error": "Telegram account is not connected. Please log in using your phone number in Accounts & API tab."}), 200

        async def _fetch():
            chats = []
            async for dialog in client.iter_dialogs(limit=100):
                if isinstance(dialog.entity, Channel):
                    chat_type = "Forum" if getattr(dialog.entity, 'forum', False) else "Channel"
                    chats.append({
                        "id": dialog.entity.id,
                        "name": dialog.name,
                        "type": chat_type,
                        "is_forum": bool(getattr(dialog.entity, 'forum', False))
                    })
            return chats

        chats_list = run_async(_fetch(), timeout=25)
        return jsonify({"success": True, "chats": chats_list})
    except Exception as e:
        err_msg = str(e)
        if "not authorized" in err_msg.lower():
            err_msg = "Telegram account is not connected. Please log in in Accounts & API tab."
        return jsonify({"success": False, "error": err_msg}), 200

@app.route('/api/links/scan', methods=['POST'])
def scan_links_route():
    """Scans source channel for embedded links, plain URLs, and mentions."""
    data = request.json or {}
    source_id = data.get('source_id')
    dest_id = data.get('dest_id')
    if not source_id:
        return jsonify({"success": False, "error": "Source channel selection is required."}), 200

    client = get_client()
    try:
        if not client.is_connected():
            run_async(client.connect())

        async def _scan():
            source = None
            dest = None
            async for dialog in client.iter_dialogs(limit=100):
                if isinstance(dialog.entity, Channel):
                    if dialog.entity.id == int(source_id):
                        source = dialog.entity
                    if dest_id and dialog.entity.id == int(dest_id):
                        dest = dialog.entity
                if source and (not dest_id or dest):
                    break

            if not source:
                raise ValueError("Could not find source channel in user dialogs.")

            topic_map = {}
            if getattr(dest, 'forum', False):
                existing_topics = {}
                try:
                    result = await client(functions.messages.GetForumTopicsRequest(
                        peer=dest, offset_date=None, offset_id=0, offset_topic=0, limit=100
                    ))
                    if hasattr(result, 'topics') and result.topics:
                        for t in result.topics:
                            if hasattr(t, 'title') and t.title:
                                existing_topics[t.title.lower().strip()] = t.id
                except Exception:
                    pass

                try:
                    async for message in client.iter_messages(source, reply_to=None):
                        if message.action and getattr(message.action, 'title', None):
                            raw_title = getattr(message.action, 'title', None)
                            if raw_title is not None and str(raw_title).strip() and str(raw_title).strip().lower() != 'none':
                                t_title = str(raw_title).strip().lower()
                                if t_title and t_title in existing_topics:
                                    topic_map[message.id] = (existing_topics[t_title], str(raw_title).strip())
                except Exception:
                    pass

            from src.link_tracker import scan_channel_links
            return await scan_channel_links(client, source, dest, topic_map=topic_map)

        tracked_links = run_async(_scan())
        save_tracked_links(tracked_links)

        filters = load_filters()
        filters['source_id'] = str(source_id)
        filters['dest_id'] = str(dest_id)
        filters['link_rules'] = tracked_links
        save_filters(filters)

        return jsonify({"success": True, "links": tracked_links})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/links/save', methods=['POST'])
def save_links_route():
    """Saves user-configured link rules to tracked_links.json and filters.json."""
    data = request.json or {}
    link_rules = data.get('link_rules', [])
    source_id = data.get('source_id', '')
    dest_id = data.get('dest_id', '')

    if source_id or dest_id:
        filters = load_filters()
        if source_id: filters['source_id'] = str(source_id)
        if dest_id: filters['dest_id'] = str(dest_id)
        filters['link_rules'] = link_rules
        save_filters(filters)

    save_tracked_links(link_rules)
    return jsonify({"success": True})

async def run_cloner_process(source_id, dest_id, filters):
    """Executes main channel message replication process asynchronously."""
    global cloning_active, cloning_cancelled
    cloning_active = True
    cloning_cancelled = False

    client = get_client()
    try:
        init_db()

        source = None
        destination = None
        async for dialog in client.iter_dialogs():
            if isinstance(dialog.entity, Channel):
                if dialog.entity.id == int(source_id):
                    source = dialog.entity
                if dialog.entity.id == int(dest_id):
                    destination = dialog.entity
            if source and destination:
                break

        if not source or not destination:
            broadcast("log", "Error: Could not resolve channel entities.")
            cloning_active = False
            return

        is_forum = getattr(destination, 'forum', False)
        topic_map = {}

        if is_forum:
            broadcast("log", "[PHASE 1] Fetching destination forum topics...")
            existing_topics = {}
            try:
                try:
                    result = await client(functions.messages.GetForumTopicsRequest(
                        peer=destination, offset_date=None, offset_id=0, offset_topic=0, limit=100
                    ))
                except TypeError:
                    result = await client(functions.messages.GetForumTopicsRequest(
                        channel=destination, offset_date=None, offset_id=0, offset_topic=0, limit=100
                    ))
                if hasattr(result, 'topics') and result.topics:
                    for t in result.topics:
                        if getattr(t, 'title', None):
                            clean_t = str(t.title).strip().lower()
                            if clean_t:
                                existing_topics[clean_t] = t.id
                    broadcast("log", f"Found {len(existing_topics)} existing topic(s) in destination.")
            except Exception as e:
                broadcast("log", f"Warning: Could not fetch destination topics: {e}")

            broadcast("log", "[PHASE 1] Fetching source forum topics...")
            source_topics = []
            try:
                try:
                    res_src = await client(functions.messages.GetForumTopicsRequest(
                        peer=source, offset_date=None, offset_id=0, offset_topic=0, limit=100
                    ))
                except TypeError:
                    res_src = await client(functions.messages.GetForumTopicsRequest(
                        channel=source, offset_date=None, offset_id=0, offset_topic=0, limit=100
                    ))
                if hasattr(res_src, 'topics') and res_src.topics:
                    for t in res_src.topics:
                        if getattr(t, 'title', None):
                            clean_t = str(t.title).strip()
                            if clean_t and clean_t.lower() != 'none':
                                source_topics.append((t.id, clean_t))
            except Exception as e:
                broadcast("log", f"Notice: Falling back to message scan for source topics: {e}")

            if not source_topics:
                async for message in client.iter_messages(source, limit=200):
                    if message.action and getattr(message.action, 'title', None):
                        raw_title = getattr(message.action, 'title', None)
                        if raw_title is not None and str(raw_title).strip() and str(raw_title).strip().lower() != 'none':
                            source_topics.append((message.id, str(raw_title).strip()))

            for source_topic_id, topic_title in source_topics:
                if cloning_cancelled:
                    broadcast("log", "Clone process cancelled by user.")
                    cloning_active = False
                    return

                clean_title = topic_title.lower()
                if clean_title in existing_topics:
                    dest_topic_id = existing_topics[clean_title]
                    topic_map[source_topic_id] = (dest_topic_id, topic_title)
                    broadcast("log", f"[Reused Topic] '{topic_title}' -> Dest ID: {dest_topic_id}")
                else:
                    broadcast("log", f"[Creating Topic] '{topic_title}'...")
                    created_topic = None
                    try:
                        try:
                            created_topic = await client(functions.messages.CreateForumTopicRequest(
                                channel=destination, title=topic_title
                            ))
                        except TypeError:
                            created_topic = await client(functions.messages.CreateForumTopicRequest(
                                peer=destination, title=topic_title
                            ))
                    except Exception:
                        try:
                            created_topic = await client(functions.channels.CreateForumTopicRequest(
                                channel=destination, title=topic_title
                            ))
                        except Exception as e_topic:
                            broadcast("log", f"Error creating topic '{topic_title}': {e_topic}")

                    dest_topic_id = None
                    if hasattr(created_topic, 'updates'):
                        for u in created_topic.updates:
                            if hasattr(u, 'id'):
                                dest_topic_id = u.id
                                break
                            elif hasattr(u, 'message') and hasattr(u.message, 'id'):
                                dest_topic_id = u.message.id
                                break

                    if not dest_topic_id and hasattr(created_topic, 'updates') and created_topic.updates:
                        try:
                            dest_topic_id = created_topic.updates[0].id
                        except Exception:
                            pass

                    if dest_topic_id:
                        topic_map[source_topic_id] = (dest_topic_id, topic_title)
                        existing_topics[clean_title] = dest_topic_id
                        broadcast("log", f"✓ Created Topic '{topic_title}' (Dest Topic ID: {dest_topic_id})")

                await asyncio.sleep(0.3)

            broadcast("log", f"Phase 1 Completed: Mapped {len(topic_map)} topic(s).")

        broadcast("log", "[PHASE 2] Copying messages from source to destination...")
        async for msg in client.iter_messages(source, reverse=True):
            if cloning_cancelled:
                broadcast("log", "Replication process cancelled by user.")
                cloning_active = False
                return

            text = msg.text or ""
            if not msg.media and not filters.get("clone_text", True):
                continue
            if msg.media and not filters.get("clone_media", True):
                continue

            if filters.get("skip_links", False):
                if re.search(r"https?://\S+|www\.\S+|t\.me/\S+", text, re.IGNORECASE):
                    broadcast("log", f"[Filter] Skipping message {msg.id}: contains links.")
                    continue

            blocked_str = filters.get("blocked_words", "")
            if blocked_str:
                words = [w.strip().lower() for w in blocked_str.split(",") if w.strip()]
                has_blocked = False
                for w in words:
                    if w in text.lower():
                        broadcast("log", f"[Filter] Skipping message {msg.id}: contains blocked word '{w}'.")
                        has_blocked = True
                        break
                if has_blocked:
                    continue

            if is_already_cloned(source_id, dest_id, msg.id):
                continue

            dest_topic_id = None
            topic_name = "Main Chat"
            if is_forum:
                source_topic_id = None
                if msg.reply_to:
                    source_topic_id = getattr(msg.reply_to, 'reply_to_top_id', None) or getattr(msg.reply_to, 'reply_to_msg_id', None)
                elif msg.id in topic_map:
                    source_topic_id = msg.id

                if source_topic_id in topic_map:
                    dest_topic_id, topic_name = topic_map[source_topic_id]

            has_real_media = msg.media and not isinstance(msg.media, MessageMediaWebPage)
            content_preview = "Text Message"
            if has_real_media:
                content_preview = type(msg.media).__name__.replace("MessageMedia", "")
                if msg.text:
                    content_preview += f" ({msg.text[:25].strip()}...)"
            elif msg.text:
                content_preview = f"\"{msg.text[:30].strip()}...\""

            if msg.entities:
                raw_text = msg.message or ""
                try:
                    original_text = html.unparse(raw_text, msg.entities)
                except Exception:
                    original_text = msg.text or ""
            else:
                original_text = msg.text or ""

            link_rules = filters.get("link_rules", [])
            skip, reason = should_skip_message(original_text, link_rules)
            if skip:
                broadcast("log", f"Skipping message {msg.id}: {reason}.")
                continue

            msg_map = get_cloned_message_map(source_id, dest_id)
            processed_text = process_message_text(original_text, source, destination, topic_map, filters, msg_map=msg_map, link_rules=link_rules)

            while True:
                if cloning_cancelled:
                    return
                try:
                    broadcast("log", f"[Copying] Sending to [{topic_name}] -> {content_preview}")
                    sent_msg = None
                    try:
                        if has_real_media:
                            sent_msg = await client.send_file(destination, msg.media, caption=processed_text, parse_mode='html', reply_to=dest_topic_id)
                        elif msg.text:
                            sent_msg = await client.send_message(destination, processed_text, parse_mode='html', reply_to=dest_topic_id)
                    except Exception:
                        if has_real_media:
                            sent_msg = await client.send_file(destination, msg.media, caption=processed_text, reply_to=dest_topic_id)
                        elif msg.text:
                            sent_msg = await client.send_message(destination, processed_text, reply_to=dest_topic_id)

                    if sent_msg:
                        register_clone(source_id, dest_id, msg.id, sent_msg.id)

                    await asyncio.sleep(1.5)
                    break
                except FloodWaitError as e:
                    broadcast("log", f"FloodWait triggered! Sleeping for {e.seconds} seconds...")
                    await asyncio.sleep(e.seconds + 2)
                except Exception as e:
                    broadcast("log", f"Error copying message {msg.id}: {e}")
                    await asyncio.sleep(2)
                    break

        broadcast("log", "✓ Replication process completed successfully!")
    except Exception as e:
        broadcast("log", f"Fatal error during replication: {e}")
    finally:
        cloning_active = False

@app.route('/api/clone/clear_history', methods=['POST'])
def clear_history_route():
    """Clears cloned message database history."""
    data = request.json or {}
    source_id = data.get('source_id')
    dest_id = data.get('dest_id')
    try:
        clear_clone_history(source_id, dest_id)
        broadcast("log", "Replication history DB cleared successfully.")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/clone/start', methods=['POST'])
def clone_start():
    """Starts message replication process."""
    global cloning_task, cloning_cancelled, cloning_active
    if cloning_active:
        return jsonify({"success": False, "error": "Replication process already active"}), 400

    data = request.json or {}
    source_id = data.get('source_id')
    dest_id = data.get('destination_id') or data.get('dest_id')

    if not source_id or not dest_id:
        return jsonify({"success": False, "error": "Source and Destination IDs required"}), 400

    filters = {
        "source_id": str(source_id),
        "dest_id": str(dest_id),
        "blocked_words": data.get('blocked_words', ''),
        "skip_links": bool(data.get('skip_links', False)),
        "clone_text": bool(data.get('clone_text', True)),
        "clone_media": bool(data.get('clone_media', True)),
        "auto_map_topics": bool(data.get('auto_map_topics', True)),
        "auto_map_mentions": bool(data.get('auto_map_mentions', True)),
        "replacements": data.get('replacements', ''),
        "link_rules": data.get('link_rules', [])
    }
    save_filters(filters)

    cloning_task = asyncio.run_coroutine_threadsafe(
        run_cloner_process(source_id, dest_id, filters), loop
    )
    return jsonify({"success": True})

@app.route('/api/clone/running', methods=['GET'])
def clone_running():
    """Returns whether a replication process is running."""
    return jsonify({"success": True, "running": cloning_active})

@app.route('/api/clone/stop', methods=['POST'])
def clone_stop():
    """Stops active message replication process."""
    global cloning_cancelled, cloning_active
    cloning_cancelled = True
    cloning_active = False
    broadcast("log", "Stopping replication process...")
    return jsonify({"success": True})

@app.route('/api/events', methods=['GET'])
def sse_events():
    """Server-Sent Events (SSE) streaming endpoint for live logs."""
    def event_stream():
        q = queue.Queue()
        with sse_lock:
            sse_listeners.append(q)
        try:
            while True:
                try:
                    event = q.get(timeout=25)
                    yield f"data: {json.dumps(event)}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            with sse_lock:
                if q in sse_listeners:
                    sse_listeners.remove(q)

    return Response(event_stream(), mimetype="text/event-stream")

if __name__ == '__main__':
    print("Starting TGClonerX Web Dashboard...")
    print("Open browser at: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
