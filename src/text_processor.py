import re
import html as python_html

def should_skip_message(text, link_rules=None):
    """
    Evaluates whether a message should be skipped based on user link rules.

    Parameters:
        text (str): The raw message text or HTML content to evaluate.
        link_rules (list): List of rule dictionaries from the Link Tracker interface.

    Returns:
        tuple (bool, str): (True, reason) if message should be skipped, else (False, "").
    """
    if not text or not link_rules:
        return False, ""

    for rule in link_rules:
        if isinstance(rule, dict) and rule.get("action") == "skip":
            orig_url = rule.get("original_url", "").strip()
            orig_text = rule.get("original_text", "").strip()

            if orig_url and orig_url in text:
                return True, f"contains ignored link URL '{orig_url}'"
            if orig_text and orig_text in text:
                return True, f"contains ignored mention/text '{orig_text}'"

    return False, ""

def process_message_text(text, source=None, destination=None, topic_map=None, filters=None, msg_map=None, link_rules=None):
    """
    Transforms message text and media captions by applying user-confirmed link rules,
    automatic topic URL mappings, message ID mappings, and channel mention updates.

    Parameters:
        text (str): Source message HTML text or caption.
        source (Channel): Source Telethon channel entity.
        destination (Channel): Destination Telethon channel entity.
        topic_map (dict): Mapping of source topic IDs to destination topic IDs.
        filters (dict): Filter configuration settings.
        msg_map (dict): SQLite DB mapping of source message IDs to destination message IDs.
        link_rules (list): List of user-confirmed interactive link rules.

    Returns:
        str: Processed message text ready for destination dispatch.
    """
    if not text:
        return text

    filters = filters or {}
    auto_map_topics = filters.get("auto_map_topics", True)
    auto_map_mentions = filters.get("auto_map_mentions", True)

    processed = text

    # 1. Apply interactive link rules (substitutions, removals, line wipes)
    if link_rules and isinstance(link_rules, list):
        for rule in link_rules:
            if not isinstance(rule, dict):
                continue

            action = rule.get("action", "replace")
            if action == "skip":
                continue

            orig_url = rule.get("original_url", "").strip()
            repl_url = rule.get("replacement_url", "").strip()
            orig_txt = rule.get("original_text", "").strip()
            repl_txt = rule.get("replacement_text", "").strip()

            # A) ACTION: REMOVE LINK & TEXT -> Removes the ENTIRE LINE containing the link/mention
            if action == "remove_text":
                lines = processed.split('\n')
                kept_lines = []

                clean_u = orig_url.rstrip('/') if orig_url else ''
                clean_txt = orig_txt.strip() if orig_txt else ''
                clean_txt_no_at = clean_txt.lstrip('@').strip() if clean_txt else ''

                for line in lines:
                    should_remove_line = False

                    if clean_u and clean_u.lower() in line.lower():
                        should_remove_line = True

                    if clean_txt and clean_txt.lower() in line.lower():
                        should_remove_line = True

                    if clean_txt_no_at and len(clean_txt_no_at) > 4 and clean_txt_no_at.lower() in line.lower():
                        should_remove_line = True

                    if not should_remove_line:
                        kept_lines.append(line)

                processed = '\n'.join(kept_lines)

            # B) ACTION: REMOVE LINK ONLY -> Strips <a href="..."> tags and orphaned @ symbols
            elif action == "remove":
                if orig_url:
                    clean_u = re.escape(orig_url.rstrip('/'))
                    pattern_anchor = re.compile(
                        r'(?:<(?:strong|b|em|i|span)[^>]*>)*\s*<a\s+href="' + clean_u + r'/?">([\s\S]*?)</a>\s*(?:</(?:strong|b|em|i|span)>)*',
                        re.IGNORECASE
                    )
                    processed = pattern_anchor.sub(r'\1', processed)
                    processed = re.sub(clean_u + r'/?', '', processed, flags=re.IGNORECASE)

                # Clean up orphaned @ at line start or before remaining text
                processed = re.sub(r'(?<=^|\n)@(?=\s|$)', '', processed)

            # C) ACTION: REPLACE LINK & TEXT (Substitutes URL and/or anchor text with replacements)
            elif action == "replace":
                if orig_url and repl_url:
                    processed = processed.replace(orig_url, repl_url)

                if orig_txt and repl_txt:
                    if orig_url:
                        clean_u = re.escape(repl_url if repl_url else orig_url.rstrip('/'))
                        pattern_anchor_repl = re.compile(
                            r'(<a\s+href="' + clean_u + r'/?">)([\s\S]*?)(</a>)',
                            re.IGNORECASE
                        )
                        def _repl_inner(m, new_t=repl_txt):
                            return f"{m.group(1)}{new_t}{m.group(3)}"
                        processed = pattern_anchor_repl.sub(_repl_inner, processed)

                    processed = processed.replace(orig_txt, repl_txt)
                    processed = processed.replace(python_html.escape(orig_txt), repl_txt)
                    html_orig = orig_txt.replace("'", "&#x27;").replace("&", "&amp;")
                    if html_orig != orig_txt:
                        processed = processed.replace(html_orig, repl_txt)

    # Clean up empty lines or trailing spacing left after removal
    processed = re.sub(r'\n{3,}', '\n\n', processed).strip()

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

    # 2. Topic & Message link mapping
    if auto_map_topics and dest_id_clean:
        def replace_link_match(match):
            prefix = match.group(1)
            raw_channel = match.group(2)
            try:
                link_id = int(match.group(3))
            except ValueError:
                return match.group(0)
            suffix = match.group(4) or ""

            if topic_map and link_id in topic_map:
                dest_topic_id = topic_map[link_id][0]
                return f"https://t.me/c/{dest_id_clean}/{dest_topic_id}{suffix}"

            if msg_map and link_id in msg_map:
                dest_msg_id = msg_map[link_id]
                return f"https://t.me/c/{dest_id_clean}/{dest_msg_id}{suffix}"

            if source_id_clean and (raw_channel == source_id_clean or raw_channel == f"100{source_id_clean}"):
                return f"https://t.me/c/{dest_id_clean}/{link_id}{suffix}"

            return match.group(0)

        pattern = re.compile(
            r'((?:https?://)?(?:www\.)?t\.me/c/)(100\d+|\d+)/(\d+)(/[^\s\"\'\<\>]+)?(?=[^0-9]|$)',
            re.IGNORECASE
        )
        processed = pattern.sub(replace_link_match, processed)

        source_username = getattr(source, 'username', None)
        dest_username = getattr(destination, 'username', None)
        if source_username and topic_map:
            for source_topic_id, (dest_topic_id, _) in topic_map.items():
                pattern_user = re.compile(
                    r'(?:https?://)?(?:www\.)?t\.me/' + re.escape(source_username) + r'/' + str(source_topic_id) + r'(?=[^0-9]|$)',
                    re.IGNORECASE
                )
                dest_base = f"https://t.me/{dest_username}" if dest_username else f"https://t.me/c/{dest_id_clean}"
                user_repl_url = f"{dest_base}/{dest_topic_id}"
                processed = pattern_user.sub(lambda m, rep=user_repl_url: rep, processed)

    # 3. Channel Mentions & Username Replacements
    if auto_map_mentions and source and destination:
        source_username = getattr(source, 'username', None)
        dest_username = getattr(destination, 'username', None)
        if source_username and dest_username:
            pattern_mention = re.compile(r'@' + re.escape(source_username) + r'\b', re.IGNORECASE)
            processed = pattern_mention.sub(lambda m, u=dest_username: f"@{u}", processed)

            pattern_tme = re.compile(r'(?:https?://)?(?:www\.)?t\.me/' + re.escape(source_username) + r'\b', re.IGNORECASE)
            processed = pattern_tme.sub(lambda m, u=dest_username: f"https://t.me/{u}", processed)

    return processed
