import asyncio
from telethon import functions
from telethon.tl.types import MessageReplyHeader, Updates, MessageMediaWebPage
from telethon.errors import FloodWaitError
from colorama import Fore, Style

from src.utils import check_cancel_prompt, list_and_choose_chat
from src.database import init_db, is_already_cloned, register_clone, get_cloned_message_map
from src.text_processor import process_message_text, should_skip_message
from telethon.extensions import html

async def run_cloner(client):
    """
    CLI runner for channel and forum replication.

    Parameters:
        client (TelegramClient): Active Telethon client instance.

    Returns:
        None

    Example:
        >>> await run_cloner(client)
    """
    print(f"{Fore.GREEN}Successfully connected to Telegram!")
    init_db()

    source = await list_and_choose_chat(client, "SELECT SOURCE CHANNEL (COPY FROM)")
    destination = await list_and_choose_chat(client, "SELECT DESTINATION CHANNEL (REPLICATE TO)")

    if source.id == destination.id:
        print(f"{Fore.RED}Error: Source and destination channels cannot be the same.")
        return

    print(f"\n{Fore.LIGHTBLACK_EX}💡 Tip: Press Ctrl + C at any time to pause or cancel script.")

    is_forum = getattr(destination, 'forum', False)

    topic_map = {}
    if is_forum:
        print(f"\n{Fore.YELLOW}[PHASE 1] Fetching destination forum topics...")
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
                print(f"{Fore.GREEN}✓ Found {len(existing_topics)} existing topic(s) in destination.")
        except Exception as e:
            print(f"{Fore.RED}✗ Warning: Could not fetch destination topics: {e}")

        print(f"\n{Fore.YELLOW}[PHASE 1] Fetching source forum topics...")
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
            print(f"{Fore.RED}Notice: Falling back to message scan for source topics: {e}")

        if not source_topics:
            async for message in client.iter_messages(source, limit=200):
                if message.action and getattr(message.action, 'title', None):
                    raw_title = getattr(message.action, 'title', None)
                    if raw_title is not None and str(raw_title).strip() and str(raw_title).strip().lower() != 'none':
                    await asyncio.sleep(0.5)

            print(f"\n{Fore.GREEN}Phase 1 Completed: Mapped {len(topic_map)} topic(s).")
        except Exception as e:
            print(f"{Fore.RED}Error scanning source topics: {e}")

    filters = {}

    input(f"\n{Fore.GREEN}Press ENTER to start message replication...{Style.RESET_ALL}")
    print(f"\n{Fore.YELLOW}[PHASE 2] Copying messages from source to destination...")

    try:
        async for msg in client.iter_messages(source, reverse=True):
            text = msg.text or ""
            if not msg.media and not filters.get("clone_text", True):
                continue
            if msg.media and not filters.get("clone_media", True):
                continue
            if filters.get("skip_links", False):
                import re
                if re.search(r"https?://\S+|www\.\S+|t\.me/\S+", text, re.IGNORECASE):
                    print(f"{Fore.YELLOW}[Filter] Skipping message {msg.id}: contains links.")
                    continue
            blocked_str = filters.get("blocked_words", "")
            if blocked_str:
                words = [w.strip().lower() for w in blocked_str.split(",") if w.strip()]
                has_blocked = False
                for w in words:
                    if w in text.lower():
                        print(f"{Fore.YELLOW}[Filter] Skipping message {msg.id}: contains blocked word '{w}'.")
                        has_blocked = True
                        break
                if has_blocked:
                    continue

            if is_already_cloned(source.id, destination.id, msg.id):
                continue

            dest_topic_id = None
            topic_name = "Main Chat"
            if is_forum:
                source_topic_id = None
                if msg.reply_to and hasattr(msg.reply_to, 'reply_to_top_id'):
                    source_topic_id = msg.reply_to.reply_to_top_id or msg.reply_to.reply_to_msg_id

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
                print(f"{Fore.YELLOW}[Filter] Skipping message {msg.id}: {reason}.")
                continue

            msg_map = get_cloned_message_map(source.id, destination.id)
            processed_text = process_message_text(original_text, source, destination, topic_map, filters, msg_map=msg_map, link_rules=link_rules)

            while True:
                try:
                    print(f"{Fore.CYAN}[Copying]{Fore.WHITE} Sending to [{Fore.MAGENTA}{topic_name}{Fore.WHITE}] -> {Fore.YELLOW}{content_preview}")

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
                        register_clone(source.id, destination.id, msg.id, sent_msg.id)

                    await asyncio.sleep(1.5)
                    break

                except FloodWaitError as e:
                    print(f"\n{Fore.RED}FloodWait triggered! Sleeping for {e.seconds} seconds...{Style.RESET_ALL}")
                    await asyncio.sleep(e.seconds + 2)
                except Exception as e:
                    print(f"{Fore.RED}Error copying message {msg.id}: {e}")
                    await asyncio.sleep(2)
                    break

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Replication process paused by user.")

    print(f"\n{Fore.GREEN}Replication completed successfully!")
