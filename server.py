"""TCP 게임 서버."""
import socket
import threading

from game import Game, GameError, MAX_PLAYERS
from mapdata import GameMap, default_map
from protocol import DEFAULT_PORT, LineReader, ProtocolError, encode


class GameServer:
    def __init__(self, host="0.0.0.0", port=DEFAULT_PORT, game_map: GameMap = None,
                 laps=3, auto_start=False):
        self.host = host
        self.port = port
        self.auto_start = auto_start      # 4명이 모이면 자동 시작
        self.lock = threading.RLock()
        self.game = Game(game_map or default_map(), laps)
        self.clients = {}                 # pid -> socket
        self._listen = None
        self._running = False

    # ---- 수명주기 ----
    def start(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.host, self.port))
        s.listen(8)
        self._listen = s
        self._running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def stop(self):
        self._running = False
        if self._listen:
            try:
                self._listen.close()
            except OSError:
                pass
        with self.lock:
            for c in list(self.clients.values()):
                self._close(c)

    @staticmethod
    def _close(sock):
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    # ---- 호스트 조작 (스레드 안전) ----
    def set_map(self, game_map):
        with self.lock:
            self.game.set_map(game_map)
            self._broadcast_state()

    def set_laps(self, laps):
        with self.lock:
            self.game.set_laps(laps)
            self._broadcast_state()

    def start_game(self):
        with self.lock:
            logs = self.game.start()
            self._broadcast_log(f"게임 시작! ({self.game.map.name}, {self.game.laps}바퀴)")
            for line in logs:
                self._broadcast_log(line)
            self._broadcast_state()

    def reset_game(self):
        with self.lock:
            self.game.reset()
            self._broadcast_log("대기실로 돌아갑니다.")
            self._broadcast_state()

    # ---- 내부 ----
    def _accept_loop(self):
        while self._running:
            try:
                conn, _ = self._listen.accept()
            except OSError:
                break
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _send(self, sock, msg):
        try:
            sock.sendall(encode(msg))
            return True
        except OSError:
            return False

    def _broadcast(self, msg):
        for pid, c in list(self.clients.items()):
            if not self._send(c, msg):
                self._close(c)      # 읽기 스레드가 정리한다

    def _broadcast_state(self):
        self._broadcast(self.game.snapshot())

    def _broadcast_log(self, text):
        self._broadcast({"type": "log", "text": text})

    def _serve(self, conn):
        pid = None
        try:
            for msg in LineReader(conn).messages():
                kind = msg.get("type")
                with self.lock:
                    try:
                        if pid is None:
                            if kind != "join":
                                continue
                            player = self.game.add_player(str(msg.get("name", "")),
                                                          auto_name=msg.get("auto_name") is True)
                            pid = player.id
                            self.clients[pid] = conn
                            self._send(conn, {"type": "welcome", "pid": pid})
                            self._broadcast_log(f"{player.name} 님이 입장했습니다.")
                            if self.auto_start and len(self.game.players) == MAX_PLAYERS:
                                self.start_game()
                            else:
                                self._broadcast_state()
                        elif kind == "color":
                            self.game.set_color(pid, msg.get("slot"))
                            self._broadcast_state()
                        elif kind == "roll":
                            for line in self.game.start_roll(pid):
                                self._broadcast_log(line)
                            self._broadcast_state()
                        elif kind == "branch":
                            for line in self.game.choose_branch(pid, msg.get("direction")):
                                self._broadcast_log(line)
                            self._broadcast_state()
                    except GameError as e:
                        self._send(conn, {"type": "error", "text": str(e)})
                        if pid is None:
                            break
        except (OSError, ProtocolError):
            pass
        finally:
            with self.lock:
                if pid is not None and self.clients.get(pid) is conn:
                    del self.clients[pid]
                    p = self.game.get(pid)
                    if p:
                        self._broadcast_log(f"{p.name} 님이 나갔습니다.")
                    self.game.remove_player(pid)
                    self._broadcast_state()
            self._close(conn)
