# deepseek wrote this entire thing and it works somehow
# dont ask me why it works, i dont know either
import json

def main(update_var, get_var, list_user, send):
    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    AUTH_CHANNEL_PREFIX = "auth"
    MAIN_CHANNEL = "all"
    BOT_NAME = "authbot"
    STORAGE_FILE  = "gchat_users.json"

    registered = json.load(open(STORAGE_FILE))

    states = {}

    def get_name(user_id):
        try:
            return get_var(user_id, "username") or "anon"
        except Exception:
            return "anon"

    def get_channel(user_id):
        try:
            return get_var(user_id, "channel") or MAIN_CHANNEL
        except Exception:
            return MAIN_CHANNEL

    def send_to_user(user_id, message):
        """Send a message to the channel the user is currently in."""
        channel = get_channel(user_id)
        send(BOT_NAME, channel, message)

    def on_connect(user_id):
        states[user_id] = {"state": "anonymous"}

    def on_disconnect(user_id):
        states.pop(user_id, None)

    def on_receive(user_id, channel, message):
        state = states.get(user_id)
        if not state:
            # Unknown user
            return
        if state["state"] == "authenticated":
            return

        if state["state"] == "anonymous":
            return

        text = message.strip()

        if state["state"] == "awaiting_credentials":
            if ";" not in text:
                send_to_user(user_id, "Invalid format. Please use: {name};{pass}")
                return "shadow"

            name, password = text.split(";", 1)
            name = name.strip()
            password = password.strip()

            if not name or not password:
                send_to_user(user_id, "Name and password cannot be empty. Please use: {name};{pass}")
                return "shadow"

            if name in registered:
                if registered[name] == password:
                    # Successful login
                    update_var(user_id, "username", name)
                    update_var(user_id, "channel", MAIN_CHANNEL)
                    state["state"] = "authenticated"
                    send(BOT_NAME, MAIN_CHANNEL, f"{name} has joined.")
                else:
                    send_to_user(user_id, "Incorrect password. Try again: {name};{pass}")
            else:
                # Not registered – ask for password confirmation
                state["state"] = "awaiting_confirm"
                state["pending_name"] = name
                state["pending_pass"] = password
                send_to_user(
                    user_id,
                    f"Name '{name}' is not registered. "
                    "Please send your password again to confirm registration."
                )

        elif state["state"] == "awaiting_confirm":
            confirm_pass = text  # user just sends the password again
            if confirm_pass == state["pending_pass"]:
                # Register the new account
                registered[state["pending_name"]] = state["pending_pass"]
                # Log the user in
                update_var(user_id, "username", state["pending_name"])
                update_var(user_id, "channel", MAIN_CHANNEL)
                state["state"] = "authenticated"
                send(BOT_NAME, MAIN_CHANNEL, f"{state['pending_name']} has joined.")
            else:
                send_to_user(
                    user_id,
                    "Passwords do not match. Please start over with: {name};{pass}"
                )
                state["state"] = "awaiting_credentials"
                state.pop("pending_name", None)
                state.pop("pending_pass", None)

        return "shadow"

    def on_change_name(user_id, req):
        state = states.get(user_id)
        if state and state["state"] != "authenticated":
            return "Manual name changes not allowed; If you are trying to log in or register, join #auth"
        return 0

    def on_change_channel(user_id, req):
        if req == "auth":
            update_var(user_id, "channel", AUTH_CHANNEL_PREFIX + f"-{user_id}")
            states[user_id] = {"state": "awaiting_credentials"}
            send_to_user(user_id, "Welcome! Please authenticate with: {name};{pass}")
            return "shadow"
        
        if req.startswith("auth-"):
            return "Direct access to this channel is reserved. If you are trying to authenticate, joining #auth will redirect you to the correct channel"
        return 0

    def on_shutdown():
        try:
            with open(STORAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(registered, f, ensure_ascii=False, indent=2)
            print(f"[{BOT_NAME}] saved {len(registered)} account(s) to {STORAGE_FILE}")
        except Exception as e:
            print(f"[{BOT_NAME}] failed to save {STORAGE_FILE}: {e}")

    # ------------------------------------------------------------------
    # Register handlers with the server
    # ------------------------------------------------------------------
    return {
        "connect":        [on_connect],
        "disconnect":     [on_disconnect],
        "receive":        [on_receive],
        "change_name":    [on_change_name],
        "change_channel": [on_change_channel],
        "shutdown":       [on_shutdown]
    }