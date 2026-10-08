"""TCP 게임 클라이언트 (네트워크 계층)."""
import queue
import socket
import threading

from protocol import LineReader, ProtocolError, encode


class NetClient:
    def __init__(self):
        self.sock = None
        self.inbox = queue.Queue()
        self._send_lock = threading.Lock()

    def connect(self, host, port, name, timeout=5, auto_name=False):
        self.sock = socket.create_connection((host, port), timeout)
        self.sock.settimeout(None)
        threading.Thread(target=self._reader, daemon=True).start()
        self.send({"type": "join", "name": name, "auto_name": auto_name})

    def _reader(self):
        try:
            for msg in LineReader(self.sock).messages():
                self.inbox.put(msg)
        except (OSError, ProtocolError):
            pass
        finally:
            self.inbox.put({"type": "closed"})

    def send(self, msg):
        with self._send_lock:
            self.sock.sendall(encode(msg))

    def roll(self):
        self.send({"type": "roll"})

    def choose_color(self, slot):
        self.send({"type": "color", "slot": slot})

    def choose_branch(self, direction):
        self.send({"type": "branch", "direction": direction})

    def close(self):
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.sock.close()
            except OSError:
                pass
