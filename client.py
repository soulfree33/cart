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

    def use_item(self, card_id, target_pid=None, target_pids=None,
                 use_super_booster=False):
        self.send({
            "type": "use_item", "card_id": card_id, "target_pid": target_pid,
            "target_pids": target_pids,
            "use_super_booster": use_super_booster,
        })

    def resolve_shop_card_choice(self, choice_id, action, die_index=None):
        self.send({
            "type": "shop_card_choice", "choice_id": choice_id,
            "action": action, "die_index": die_index,
        })

    def purchase_shop(self, shop_token, card_id, upgrade_gauge):
        self.send({
            "type": "shop_purchase",
            "shop_token": shop_token,
            "card_id": card_id,
            "upgrade_gauge": upgrade_gauge,
        })

    def close_shop(self, shop_token):
        self.send({"type": "shop_close", "shop_token": shop_token})

    def debug_teleport(self, cell):
        self.send({"type": "debug_teleport", "cell": cell})

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
