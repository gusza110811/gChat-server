import typing
import time, datetime

class Commands:
    def __init__(self, socket:"socket.socket", server:"server.Server", clients:"list[server.Server]", messages:list[tuple[str,str,str,str]],
                 plugin_user_connect_handlers:list[typing.Callable], plugin_user_disconnect_handlers:list[typing.Callable], plugin_receive_handlers:list[typing.Callable], plugin_change_name_handlers:list[typing.Callable], plugin_change_channel_handlers:list[typing.Callable]):
        self.socket = socket
        self.server = server
        self.address = server.address
        self.clients = clients
        self.messages = messages
        self.mapping = {
            "NAME" : self.NAME,
            "JOIN" : self.JOIN,
            "MSG": self.MSG,
            "LIST": self.LIST,
            "FETCH": self.FETCH,
            "FETCHC": self.FETCHC,
            "PING": self.PING,
            "QUIT": self.QUIT,

            "GET": self.teapot,
            "POST": self.teapot,
            "HEAD": self.teapot,
        }
        self.uid = server.uid
        self.pinged = False

        self.plugin_user_connect_handlers = plugin_user_connect_handlers
        self.plugin_user_disconnect_handlers = plugin_user_disconnect_handlers
        self.plugin_receive_handlers = plugin_receive_handlers
        self.plugin_change_name_handlers = plugin_change_name_handlers
        self.plugin_change_channel_handlers = plugin_change_channel_handlers

    def NAME(self, arg:str):
        try:
            newname = arg.split()[0]
            if ";" in newname:
                self.socket.send(b"ERR Rejected RejectedUsername Cannot use semicolon\n")
                return
            if newname.startswith("anon-"):
                self.socket.send(b"ERR Rejected RejectedUsername anon- prefix is reserved\n")
                return
            for client in self.clients:
                if client.username == newname:
                    self.socket.send(b"ERR Rejected RejectedUsername Username taken\n")
                    return

            for handler in self.plugin_change_name_handlers:
                try:
                    result = handler(self.uid, newname)
                    if result:
                        self.socket.send(("ERR Rejected RejectedUsername " + result + "\n").encode("utf-8"))
                        return
                except Exception as e:
                    print(f"[ERROR] Plugin handler error: {e}")
            
            oldname = self.server.username
            if oldname == newname:
                return
            self.server.username = newname
            for client in self.clients:
                client.recieve_message(f"is now {newname}",self.server.channel,oldname)
            self.socket.send(f"NOTE NAME = {self.server.username}\n".encode("utf-8"))
            print(f"[{self.uid}] " + (f"{oldname} is now" if oldname else "New user") + f" {self.server.username}")
        except IndexError:
            self.socket.send(b"ERR BadCommand NoParameter\n")

    def JOIN(self, arg:str):
        if len(arg.split()) == 0:
            self.socket.send(b"ERR BadCommand NoParameter\n")
            return
        target_channel = arg.split()[0]
        if target_channel == self.server.channel:
            return
        if ";" in target_channel:
            self.socket.send(b"ERR Rejected RejectedChannel Cannot use semicolon\n")
            return

        for handler in self.plugin_change_channel_handlers:
            try:
                result = handler(self.uid, target_channel)
                if result:
                    self.socket.send(("ERR Rejected RejectedChannel " + result + "\n").encode("utf-8"))
                    return
            except Exception as e:
                print(f"[ERROR] Plugin handler error: {e}")
        
        if self.server.username:
            for client in self.clients:
                client.recieve_message("left the channel",self.server.channel,self.server.username)
        self.server.channel = target_channel
        self.socket.send(f"NOTE CH = {self.server.channel}\n".encode("utf-8"))
        print(f"[{self.uid}] {(self.server.username or '')} joined {self.server.channel}")
        for client in self.clients:
            client.recieve_message("joined the channel",self.server.channel,self.server.username)

    def MSG(self, arg:str):
        print(f"[{self.uid}] {datetime.datetime.fromtimestamp(round(time.time()))} #{self.server.channel} <{self.server.username}> {arg}")

        for handler in self.plugin_receive_handlers:
            try:
                result = handler(self.uid, self.server.channel, arg)
                if result:
                    if result != "Shadowed":
                        self.socket.send(("ERR Rejected Unauthorized " + result + "\n").encode("utf-8"))
                    return
            except Exception as e:
                print(f"[ERROR] Plugin handler error: {e}")

        self.messages.append((round(time.time()),self.server.channel,self.server.username,arg))
        for client in self.clients:
            client.recieve_message(arg,self.server.channel,self.server.username)

    def LIST(self, arg:str):
        print(f"[{self.uid}] {(self.server.username or '')} requested list")
        self.socket.send(b"CTRL begin list\n")
        for client in self.clients:
            if not client.username: continue
            self.socket.send((client.username+"\n").encode("utf-8"))
        self.socket.send(b"CTRL end list\n")
    
    def FETCH(self, arg:str):
        try:
            n = int(arg.split()[0])
        except (IndexError, ValueError):
            n = len(self.messages)  # default: all
        
        print(f"[{self.uid}] {(self.server.username or '')} requested {n} messages")

        messages = self.messages.copy()
        messages.reverse()
        self.socket.send(b"CTRL begin fetch\n")
        count = 0
        while count < n and messages:
            message = messages.pop(0)
            self.socket.send(
                f"{message[0]} ; {message[1]} ; {message[2]} ; {message[3]}\n".encode("utf-8")
            )
            count += 1
        self.socket.send(b"CTRL end fetch\n")

    def FETCHC(self, arg:str):
        try:
            n = int(arg.split()[0])
        except (IndexError, ValueError):
            n = len(self.messages)  # default: all

        messages = self.messages.copy()
        messages.reverse()
        print(f"[{self.uid}] {(self.server.username or '')} requested {n} messages in {self.server.channel}")
        self.socket.send(b"CTRL begin fetch\n")
        count = 0
        while count < n and messages:
            message = messages.pop(0)
            if message[1] != self.server.channel:
                continue
            self.socket.send(
                f"{message[0]} ; {message[1]} ; {message[2]} ; {message[3]}\n".encode("utf-8")
            )
            count += 1
        self.socket.send(b"CTRL end fetch\n")
    
    def PING(self,arg:str):
        if not self.pinged:
            self.socket.send(b"NOTE LINE_END = LF\n")
            self.socket.send(b"NOTE CH = all\n")
            self.socket.send(f"NOTE NAME = {self.server.username}\n".encode("utf-8"))
            self.pinged = True

            for handler in self.plugin_user_connect_handlers:
                try:
                    handler(self.uid)
                except Exception as e:
                    print(f"[ERROR] Plugin handler error: {e}")

        print(f"[{self.uid}] {(self.server.username or '')} sent PING")
        self.socket.send(b"PONG\n")

    def QUIT(self,arg:str):
        for handler in self.plugin_user_disconnect_handlers:
            try:
                handler(self.uid)
            except Exception as e:
                print(f"[ERROR] Plugin handler error: {e}")

        print(f"[{self.uid}] {(self.server.username or '')} requested to disconnect")
        self.server.active = False

    def teapot(self,arg:str):
        print(f"[{self.uid}] {(self.server.username or '')} attempted to use http command")
        message = """this is not a website<br>
<a href=\"https://github.com/gusza110811/gChat\">get the client</a>"""
        self.socket.send(f"HTTP/1.1 400 Bad Request\r\nContent-Type: text/html\r\nContent-Length: {len(message)}\r\nConnection: close\r\n\r\n".encode() + message.encode())
        self.server.active = False

if typing.TYPE_CHECKING:
    import socket, server
