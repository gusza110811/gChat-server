# gChat Plugins

**This gChat implementation** supports small Python modules as plugins. They are loaded automatically when the server starts and can hook into connection, message, name, channel, and shutdown events.

## 1. How plugins are loaded

The server searches for plugin files using the `plugins` list in `cfg.json` or the `GCHAT_PLUGINS` environment variable.

Example config:

```json
{
  "host": "localhost",
  "port": 3355,
  "maxClient": 16,
  "plugins": ["*.plugin.py", "plugins/*.plugin.py"]
}
```

Environment equivalent:

```bash
export GCHAT_PLUGINS="*.plugin.py plugins/*.plugin.py"
```

Each matching file is imported with `importlib`. If the file exposes a `main()` function, it is called like this:

```python
handlers = plugin_module.main(update_var, get_var, list_user, send)
```

The return value must be a dictionary of handler lists.

## 2. Plugin entry point

Every plugin should define:

```python
def main(update_var, get_var, list_user, send):
    ...
    return {
        "connect": [on_connect],
        "disconnect": [on_disconnect],
        "receive": [on_receive],
        "change_name": [on_change_name],
        "change_channel": [on_change_channel],
        "shutdown": [on_shutdown],
    }
```

The keys are optional. You can return only the handlers you need.

## 3. API passed into plugins

The `main()` function receives four helpers:

### `update_var(user_id, var_name, value)`

Sets a per-user value.

Supported names:
- `"username"`
- `"channel"`

Examples:

```python
update_var(user_id, "username", "alice")
update_var(user_id, "channel", "all")
```

This also sends server notes to the client:

- `NOTE NAME = <name>`
- `NOTE CH = <channel>`

### `get_var(user_id, var_name)`

Reads a per-user value.

```python
name = get_var(user_id, "username")
channel = get_var(user_id, "channel")
```

Returns `None` if the user is missing or the variable is unknown.

### `list_user()`

Returns all connected users as a list of tuples:

```python
[
    (uid, username, channel),
    ...
]
```

Example:

```python
for uid, name, channel in list_user():
    print(uid, name, channel)
```

### `send(send_as, channel, message)`

Broadcasts a message to everyone in a channel using a given sender name.

```python
send("greeterbot", "all", "Welcome!")
```

This calls the normal in-server message delivery path. It is useful for bot messages and announcements.

## 4. Handler types

### `connect`
Called when a client sends `PING` and is fully connected.

Signature:

```python
def on_connect(user_id):
    pass
```

No return value is required.

Example:
- initialize per-user state
- send a welcome message
- move someone to an auth channel

### `disconnect`
Called when a client leaves or disconnects.

Signature:

```python
def on_disconnect(user_id):
    pass
```

Use it to clean up state.

### `receive`
Called whenever a client sends a chat message.

Signature:

```python
def on_receive(user_id, channel, message):
    return 0
```

Return values:
- `0` or `None`: allow the message
- `"shadow"`: suppress the message and do not broadcast it
- any other non-empty string: reject the message with an error like:
  - `ERR Rejected Unauthorized <reason>`

Example:

```python
def on_receive(user_id, channel, message):
    if channel == "announcement" and not is_admin(user_id):
        return "Not allowed to post in announcement channel"
    return 0
```

Important:
- Returning `"Shadowed"` is used when the plugin wants to consume the message silently.
- This is how auth plugins can intercept username/password input without letting it reach the normal chat flow.

### `change_name`
Called when a client tries to set a new username with `NAME`.

Signature:

```python
def on_change_name(user_id, new_name):
    return 0
```

Return values:
- `0` or `None`: allow rename
- `"shadow"`: Skip normal rename process
- non-empty string: reject rename with:
  - `ERR Rejected RejectedUsername <reason>`

Example:

```python
def on_change_name(user_id, new_name):
    if new_name.lower() == "root":
        return "reserved username"
    return 0
```

### `change_channel`
Called when a client tries to `JOIN` a channel.

Signature:

```python
def on_change_channel(user_id, new_channel):
    return 0
```

Return values:
- `0` or `None`: allow join
- `"shadow"`: Skip normal channel changing process
- non-empty string: reject join with:
  - `ERR Rejected RejectedChannel <reason>`

### `shutdown`
Called when the server exits and is doing shutdown cleanup.

Signature:

```python
def on_shutdown():
    pass
```

Use it to save plugin state to disk.

## 5. Minimal plugin template

```python
def main(update_var, get_var, list_user, send):
    def on_connect(user_id):
        pass

    def on_disconnect(user_id):
        pass

    def on_receive(user_id, channel, message):
        return 0

    def on_change_name(user_id, new_name):
        return 0

    def on_change_channel(user_id, new_channel):
        return 0

    def on_shutdown():
        pass

    return {
        "connect": [on_connect],
        "disconnect": [on_disconnect],
        "receive": [on_receive],
        "change_name": [on_change_name],
        "change_channel": [on_change_channel],
        "shutdown": [on_shutdown],
    }
```

## 6. Example: Greeter

It does the following:

- Listen for "Hi" and "Hello" from any user
- Respond

The key pattern is:

```python
def on_receive(user_id, channel, message):
    text = (message or "").strip()
    low = text.lower()

    greeting = TRIGGERS.get(low)
    if greeting is None:
        return

    sender_name = get_name(user_id)

    reply = f"{greeting}, {sender_name}!"
    send(BOT_NAME, channel, reply)
```

## 7. Best practices

- Keep plugin code small and focused.
- Avoid blocking the server thread with long sleeps or network calls.
- Save persistent data in a file in `on_shutdown()`.
- Fail gracefully: exceptions in plugin handlers are caught and printed by the server, but the server keeps running.
- Be stateless; use `get_var()` and `update_var()` to stay consistent with server state.

## 8. Notes

- Plugins are loaded once at startup.
- Every user receives a numeric `user_id` generated by the server.
- The server does not require plugin code to inherit from any class; a plain Python function is enough.
- A plugin is not a separate process. It runs in the same Python process as the server.
- The plugin system is not a required nor standardized part of gChat. Other implementations of the server may use a different plugin system or none at all.
- If you are creating a bot that doesn't need more than sending and receiving messages, it is recommended to simply create an automated client instead of a plugin. This keeps the server side simple and avoids potential issues with plugin errors affecting the server.

## 9. Typical plugin development flow

1. Create a file ending in `.plugin.py`
2. Add it to `cfg.json` or `GCHAT_PLUGINS`
3. Define `main(update_var, get_var, list_user, send)`
4. Return the handler dictionary
5. Test with `PING`, `NAME`, `JOIN`, and `MSG`
6. Save state in `on_shutdown()` if needed

This plugin system is intentionally lightweight: it gives you hooks, not a framework. That makes it easy to add auth, moderation, logging, or bot features without changing the server core.
