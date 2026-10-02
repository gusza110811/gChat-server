#!/usr/bin/python3
import socket
import threading
import commands
import json
import os, sys
import argparse
import signal
import random
import importlib.util
import glob
import re

host = "localhost"
port = 3355
ipv6 = False
maxClient = 16
plugins = ["*.plugin.py"]

messages:list[tuple[int,str,str,str]] = []

clients:list["Server"] = []

# WIP - plugins

"""
    update_var(user_id: int, var_name: str, value) -> None
    get_var(user_id: int, var_name: str) -> str
    list_user() -> list[tuple[int, str, str]]  # (id, name, channel)
    send(send_as: str, channel: str, message: str) -> None

    on_connect(user_id: int) -> None
    on_disconnect(user_id: int) -> None
    on_receive(user_id: int, channel: str, message: str) -> None
    on_change_name(user_id: int, req: str) -> bool
    on_change_channel(user_id: int, req: str) -> bool
"""

def update_var(user_id: int, var_name:str, value):
    client = next((client for client in clients if client.uid == user_id), None)
    if client:
        if var_name == "username":
            client.username = value
            client.socket.send(f"NOTE NAME = {client.username}\n".encode("utf-8"))
        elif var_name == "channel":
            client.channel = value
            client.socket.send(f"NOTE CH = {client.channel}\n".encode("utf-8"))

def get_var(user_id: int, var_name:str):
    client = next((client for client in clients if client.uid == user_id), None)
    if client:
        if var_name == "username":
            return client.username
        elif var_name == "channel":
            return client.channel
    return None

def list_user():
    return [(client.uid, client.username, client.channel) for client in clients]

def send(send_as: str, channel:str, message:str):
    for client in clients:
        client.recieve_message(message, channel, send_as)


__dir__ = os.path.dirname(os.path.abspath(__file__))

plugin_user_connect_handlers = []
plugin_user_disconnect_handlers = []
plugin_receive_handlers = []
plugin_change_name_handlers = []
plugin_change_channel_handlers = []
plugin_shutdown_handlers = []

class Server(threading.Thread):
    def __init__(self, sockt:tuple[socket.socket,tuple[str,int]]):
        self.socket, self.address = sockt
        global clients
        global messages
        global plugin_user_connect_handlers
        global plugin_user_disconnect_handlers
        global plugin_receive_handlers
        global plugin_change_name_handlers
        global plugin_change_channel_handlers

        self.clients = clients
        self.clients.append(self)
        super().__init__(target=self.run,daemon=True)
        self.uid = None

        uid = random.randint(0,65535)
        while any(client.uid == uid for client in clients):
            uid = random.randint(0,65535)
        self.uid = uid

        self.username = f"anon-{self.uid}"
        self.channel = "all"

        self.active = False

        self.commands = commands.Commands(self.socket,self, clients, messages, plugin_user_connect_handlers, plugin_user_disconnect_handlers, plugin_receive_handlers, plugin_change_name_handlers, plugin_change_channel_handlers)

    def recieve_message(self, message, channel, sender="*"):
        try:
            self.socket.send(f"RECV {channel} ; {sender} ; {message}\n".encode("utf-8"))
        except BrokenPipeError:
            return

    def run(self):
        print(f"[{self.uid}] {self.username} Connected")
        print(f"[{self.uid}] Address: {self.address[0]} port {self.address[1]}")

        self.active = True
        sock = self.socket
        commands = self.commands
        sock.settimeout(120.0)

        buffer = ""
        try:
            while self.active:
                try:
                    data = sock.recv(512).decode("utf-8", errors="ignore")
                except ConnectionResetError:
                    break
                if not data:
                    break
                buffer += data
                while "\n" in buffer and self.active:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    name, *args = line.split(maxsplit=1)
                    arg = args[0] if args else ""

                    func = commands.mapping.get(name)
                    if not func:
                        sock.send(b"ERR BadCommand InvalidCommand\n")
                        continue

                    func(arg)
        except TimeoutError:
            pass

        self.clients.remove(self)
        sock.close()
        print(f"[{self.uid}] {self.username} Disconnected" + " (timed out)" if self.active else "")

def exit_handler(path):
    print(messages)

    for handler in plugin_shutdown_handlers:
        try:
            handler()
        except Exception as e:
            print(f"[ERROR] Plugin shutdown handler error: {e}")

    with open(path,"w") as msg:
        print(f"Saving messages to {path}")
        json.dump(messages,msg)
    sys.exit(0)

def load_plugins(plugins):
    for plugin in plugins:
        try:
            name = os.path.basename(plugin)

            spec = importlib.util.spec_from_file_location(name, plugin)
            plugin_module = importlib.util.module_from_spec(spec)
            sys.modules[name] = plugin_module
            spec.loader.exec_module(plugin_module)
            print(f"Loaded plugin `{name}`")

            if hasattr(plugin_module, "main"):
                handlers = plugin_module.main(update_var, get_var, list_user, send)
                plugin_user_connect_handlers.extend(handlers.get("connect", []))
                plugin_user_disconnect_handlers.extend(handlers.get("disconnect", []))
                plugin_receive_handlers.extend(handlers.get("receive", []))
                plugin_change_name_handlers.extend(handlers.get("change_name", []))
                plugin_change_channel_handlers.extend(handlers.get("change_channel", []))
                plugin_shutdown_handlers.extend(handlers.get("shutdown", []))
        except Exception as e:
            print(f"[ERROR] Failed to load plugin {plugin}: {e}")

if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description="gChat Server")
    argparser.add_argument("--config", "-c", help="Path to config file (default: ./cfg.json)", default="cfg.json")
    argparser.add_argument("--messages", "-m", help="Path to messages file (default: ./messages.json)", default="messages.json")
    argparser.add_argument("--env", "-e", help="Load config from environment variables (overrides config file)", action="store_true")

    args = argparser.parse_args()

    if not args.env:
        try:
            with open(args.config) as config:
                configs:dict = json.load(config)
                host:str = configs.get("host","localhost")
                port:int = configs.get("port",3355)
                maxClient = configs.get("maxClient",16)
                tmp:list[str] = configs.get("plugins",["*.plugin.py"])
                plugins = []
                for item in tmp:
                    plugins.extend(glob.glob(item))
            if host.startswith("[") and host.endswith("]"):
                host = host[1:-1]
                ipv6 = True
        except FileNotFoundError:
            with open("cfg.json","w") as config:
                configs = {
                    "host": host,
                    "port": port,
                    "maxClient": maxClient,
                }
                json.dump(configs,config, indent=4)
    else:
        host = os.getenv("GCHAT_HOST", host)
        port = int(os.getenv("GCHAT_PORT", port))
        maxClient = int(os.getenv("GCHAT_MAX_CLIENT", maxClient))
        tmp:list[str] = re.split(r"(?<!\\) ", os.getenv("GCHAT_PLUGINS","*.plugin.py"))
        plugins = []
        for item in tmp:
            plugins.extend(glob.glob(item))
        if host.startswith("[") and host.endswith("]"):
            host = host[1:-1]
            ipv6 = True
    if ipv6:
        if not socket.has_ipv6:
            raise RuntimeError("IPv6 is not supported on this system")
        if host == "auto":
            # get public ip automatically
            host = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET6)[0][4][0]
        sock = socket.socket(socket.AF_INET6,socket.SOCK_STREAM)
    else:
        sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    load_plugins(plugins)
    print(f"Listening on {host} port {port} with max {maxClient} clients")
    sock.bind((host,port))
    sock.listen(maxClient)

    filedir = os.path.dirname(__file__)

    message_save_path = args.messages
    print(f"Message save path: {message_save_path}")
    signal.signal(signal.SIGTERM, lambda signum, frame: exit_handler(message_save_path))
    signal.signal(signal.SIGINT, lambda signum, frame: exit_handler(message_save_path))

    if os.path.isfile(message_save_path):
        print(f"Loading messages from {message_save_path}")
        with open(message_save_path,"r") as msg:
            messages = json.load(msg)
    try:
        while True:
            connection = sock.accept()
            server = Server(connection)
            server.start()
    except KeyboardInterrupt:
        exit_handler(message_save_path)
