import re
import html as python_html
from telethon.extensions import html

async def scan_channel_links(client, source, destination, topic_map=None, limit=300):
    """
    Scans recent messages in a source channel to extract unique links, hyperlinks, and mentions.

    Parameters:
        client (TelegramClient): Active Telethon client instance.
        source (Channel): Source Telegram channel/group entity.
        destination (Channel): Destination Telegram channel/group entity.
        topic_map (dict, optional): Topic mapping dictionary.
        limit (int, optional): Maximum number of recent messages to scan (default 300).

    Returns:
        list[dict]: List of tracked item dictionaries containing:
            - id: Unique item identifier.
            - preview: Message context preview snippet.
            - original_text: Original link or mention anchor text.
            - original_url: Original URL string.
            - replacement_text: Pre-filled suggested display text.
            - replacement_url: Pre-filled suggested target URL.
            - action: Recommended action ('replace', 'remove', or 'skip').
            - count: Occurrence count in source channel.
    """
    topic_map = topic_map or {}
    source_id_clean = None
    dest_id_clean = None

    if source:
        raw_s_id = str(getattr(source, 'id', ''))
        source_id_clean = re.sub(r'^-?100', '', raw_s_id)
        if not source_id_clean:
            source_id_clean = raw_s_id.lstrip('-')

    if destination:
        raw_d_id = str(getattr(destination, 'id', ''))
        dest_id_clean = re.sub(r'^-?100', '', raw_d_id)
        if not dest_id_clean:
            dest_id_clean = raw_d_id.lstrip('-')

    source_username = getattr(source, 'username', None)
    dest_username = getattr(destination, 'username', None)
    source_title = getattr(source, 'title', '').strip()
    dest_title = getattr(destination, 'title', '').strip()

    tracked_dict = {}

    try:
        async for msg in client.iter_messages(source, limit=limit):
            raw_content = getattr(msg, 'message', None) or getattr(msg, 'text', None) or ""
            if not raw_content:
                continue

            preview_snippet = raw_content[:80].strip().replace('\n', ' ')

            if msg.entities:
                try:
                    unparsed_html = html.unparse(raw_content, msg.entities)
                except Exception:
                    unparsed_html = raw_content
            else:
                unparsed_html = raw_content

            # 1. Extract HTML anchor links <a href="URL">TEXT</a>
            html_anchors = re.findall(r'<a\s+href="([^"]+)">([\s\S]*?)</a>', unparsed_html, re.IGNORECASE)
            for url, anchor_html in html_anchors:
                url_clean = url.strip()
                # Strip nested HTML tags inside anchor text and unescape HTML entities (e.g. &#x27; -> ')
                anchor_clean = python_html.unescape(re.sub(r'<[^>]+>', '', anchor_html).strip())
                if not anchor_clean:
                    anchor_clean = url_clean

                key = f"href:{url_clean}:{anchor_clean}"

                if key not in tracked_dict:
                    suggested_url = _suggest_url_replacement(
                        url_clean, source_id_clean, dest_id_clean, source_username, dest_username, topic_map
                    )
                    tracked_dict[key] = {
                        "id": f"item_{len(tracked_dict) + 1}",
                        "type": "anchor",
                        "preview": preview_snippet,
                        "original_text": anchor_clean,
                        "original_url": url_clean,
                        "replacement_text": anchor_clean,
                        "replacement_url": suggested_url,
                        "action": "replace",
                        "count": 1
                    }
                else:
                    tracked_dict[key]["count"] += 1

            # 2. Extract plain t.me or http/https URLs not inside href
            plain_urls = re.findall(r'(?<!href=")(?:https?://)?(?:www\.)?t\.me/[^\s"<>\'\)]+', unparsed_html, re.IGNORECASE)
            for url in plain_urls:
                url_clean = url.strip()
                key = f"plain_url:{url_clean}"
                if key not in tracked_dict:
                    suggested_url = _suggest_url_replacement(
                        url_clean, source_id_clean, dest_id_clean, source_username, dest_username, topic_map
                    )
                    tracked_dict[key] = {
                        "id": f"item_{len(tracked_dict) + 1}",
                        "type": "plain_url",
                        "preview": preview_snippet,
                        "original_text": url_clean,
                        "original_url": url_clean,
                        "replacement_text": url_clean,
                        "replacement_url": suggested_url,
                        "action": "replace",
                        "count": 1
                    }
                else:
                    tracked_dict[key]["count"] += 1

            # 3. Extract @mentions
            # Clean text without HTML tags for mention matching
            plain_text_only = re.sub(r'<[^>]+>', ' ', unparsed_html)
            mentions = re.findall(r'@[A-Za-z0-9_áàâãéèêíïóôõöúçÑñ\s]{3,35}', plain_text_only)
            for m in mentions:
                m_clean = python_html.unescape(m.strip())
                m_clean = re.sub(r'[\.,!\?:;]+$', '', m_clean)
                if not m_clean or m_clean.startswith("<"):
                    continue

                key = f"mention:{m_clean}"
                if key not in tracked_dict:
                    suggested_mention = f"@{dest_username}" if dest_username else f"@{dest_title}"
                    if source_title and source_title.lower() in m_clean.lower():
                        suggested_mention = f"@{dest_username}" if dest_username else f"@{dest_title}"
                    elif source_username and source_username.lower() in m_clean.lower():
                        suggested_mention = f"@{dest_username}" if dest_username else f"@{dest_title}"

                    tracked_dict[key] = {
                        "id": f"item_{len(tracked_dict) + 1}",
                        "type": "mention",
                        "preview": preview_snippet,
                        "original_text": m_clean,
                        "original_url": "",
                        "replacement_text": suggested_mention,
                        "replacement_url": "",
                        "action": "replace",
                        "count": 1
                    }
                else:
                    tracked_dict[key]["count"] += 1

    except Exception as e:
        print(f"Error tracking links: {e}")

    results = list(tracked_dict.values())
    results.sort(key=lambda x: x["count"], reverse=True)
    return results

def _suggest_url_replacement(url, source_id_clean, dest_id_clean, source_username, dest_username, topic_map):
    """
    Helper function to generate auto-suggested destination URL for a source link.
    """
    match_topic = re.search(r't\.me/c/(?:100)?(?:\d+)/(\d+)', url, re.IGNORECASE)
    if match_topic and topic_map:
        try:
            source_topic_id = int(match_topic.group(1))
            if source_topic_id in topic_map:
                dest_topic_id = topic_map[source_topic_id][0]
                return f"https://t.me/c/{dest_id_clean}/{dest_topic_id}"
        except Exception:
            pass

    if source_id_clean and dest_id_clean:
        if source_id_clean in url or f"100{source_id_clean}" in url:
            new_url = re.sub(r't\.me/c/(?:100)?' + re.escape(source_id_clean), f't.me/c/{dest_id_clean}', url, flags=re.IGNORECASE)
            if not new_url.startswith("http"):
                new_url = "https://" + new_url
            return new_url

    if source_username and dest_username:
        if source_username.lower() in url.lower():
            new_url = re.sub(re.escape(source_username), dest_username, url, flags=re.IGNORECASE)
            if not new_url.startswith("http"):
                new_url = "https://" + new_url
            return new_url

    return url
