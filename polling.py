import time
import traceback
from handlers.admin_handlers import handle_message
from handlers.callback_handlers import handle_callback
from services.telegram_api import get_telegram_debug_info, get_updates


offset = None


def start_polling():
    global offset

    print("Bot started...")
    print("Telegram API startup debug:", get_telegram_debug_info())

    while True:
        try:
            updates = get_updates(offset)

            if not updates.get("ok"):
                print("getUpdates error:", updates)
                if updates.get("error_code") == 404:
                    print("Telegram API debug:", get_telegram_debug_info())
                time.sleep(2)
                continue

            for update in updates.get("result", []):
                update_id = update["update_id"]
                try:
                    if "message" in update:
                        handle_message(update)
                    elif "callback_query" in update:
                        handle_callback(update)
                except Exception as error:
                    print(f"Update handling error for update_id={update_id}: {error}")
                    traceback.print_exc()
                finally:
                    offset = update_id + 1

        except Exception as error:
            print("Polling error:", error)
            traceback.print_exc()

        time.sleep(1)