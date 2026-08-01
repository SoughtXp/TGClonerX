import sys
from telethon.tl.types import Channel
from colorama import Fore, Style

async def check_cancel_prompt():
    """
    Displays an interactive CLI prompt when KeyboardInterrupt is triggered.

    Returns:
        None
    """
    print(f"\n\n{Fore.YELLOW}⚠️ Process Interrupted!")
    while True:
        choice = input(f"{Fore.WHITE}Type {Fore.RED}[C]{Fore.WHITE} to Cancel or {Fore.GREEN}[R]{Fore.WHITE} to Resume: ").strip().lower()
        if choice == 'c':
            print(f"\n{Fore.RED}❌ Operation cancelled. Exiting...")
            sys.exit(0)
        elif choice == 'r':
            print(f"\n{Fore.GREEN}▶️ Resuming process...\n")
            return

async def list_and_choose_chat(client, action_title):
    """
    Iterates user dialogs and prompts CLI user to select a channel or group.

    Parameters:
        client (TelegramClient): Active Telethon client instance.
        action_title (str): Header title to display.

    Returns:
        Channel: Selected Telethon channel entity.
    """
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== {action_title} ===")

    chats = []
    async for dialog in client.iter_dialogs():
        if isinstance(dialog.entity, Channel):
            chats.append(dialog)

    if not chats:
        print(f"{Fore.RED}No channels or groups found in account.")
        sys.exit()

    for idx, dialog in enumerate(chats, 1):
        chat_type = "Forum/Topics Enabled" if dialog.entity.forum else "Standard Channel/Group"
        print(f"{Fore.GREEN}[{idx}]{Fore.WHITE} {dialog.name} {Fore.YELLOW}({chat_type})")

    while True:
        try:
            choice = int(input(f"\n{Fore.CYAN}Enter selection number: "))
            if 1 <= choice <= len(chats):
                return chats[choice - 1].entity
            else:
                print(f"{Fore.RED}Invalid selection. Try again.")
        except ValueError:
            print(f"{Fore.RED}Please enter a valid number.")
