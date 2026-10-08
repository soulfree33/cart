"""TCP 통신용 메시지 프로토콜: 줄바꿈으로 구분된 JSON (UTF-8)."""
import json

DEFAULT_PORT = 5000
MAX_LINE = 1024 * 1024


class ProtocolError(Exception):
    pass


def encode(msg: dict) -> bytes:
    return json.dumps(msg, ensure_ascii=False).encode("utf-8") + b"\n"


class LineReader:
    """소켓에서 줄 단위 JSON 메시지를 읽어 dict 로 돌려준다."""

    def __init__(self, sock):
        self.sock = sock
        self.buf = b""

    def messages(self):
        while True:
            while b"\n" in self.buf:
                line, self.buf = self.buf.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line.decode("utf-8"))
                except ValueError as e:
                    raise ProtocolError(f"잘못된 메시지: {e}")
                if not isinstance(msg, dict):
                    raise ProtocolError("메시지는 객체여야 합니다.")
                yield msg
            data = self.sock.recv(4096)
            if not data:
                return
            self.buf += data
            if len(self.buf) > MAX_LINE:
                raise ProtocolError("메시지가 너무 큽니다.")
