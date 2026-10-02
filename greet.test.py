BOT_NAME = "greeter"

TRIGGERS = {
    "hi":    "Hi",
    "hello": "Hello",
}


def main(update_var, get_var, list_user, send):
    def get_name(user_id):
        try:
            return get_var(user_id, "username") or "anon"
        except Exception:
            return "anon"

    def get_channel(user_id):
        try:
            return get_var(user_id, "channel") or "all"
        except Exception:
            return "all"

    def on_connect(user_id):
        name = get_name(user_id)
        channel = get_channel(user_id)
        print(f"[{BOT_NAME}] {name} ({user_id}) connected on #{channel}")

    def on_disconnect(user_id):
        name = get_name(user_id)
        print(f"[{BOT_NAME}] {name} ({user_id}) disconnected")

    def on_receive(user_id, channel, message):
        text = (message or "").strip()
        low = text.lower()

        greeting = TRIGGERS.get(low)
        if greeting is None:
            return

        sender_name = get_name(user_id)

        reply = f"{greeting}, {sender_name}!"
        send(BOT_NAME, channel, reply)

    def on_change_name(user_id, req):
        return

    def on_change_channel(user_id, req):
        return

    return {
        "connect":         [on_connect],
        "disconnect":      [on_disconnect],
        "receive":         [on_receive],
        "change_name":     [on_change_name],
        "change_channel":  [on_change_channel],
    }