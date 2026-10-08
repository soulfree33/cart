"""카트라이더 보드게임 진입점.

  python main.py                     # GUI (서버/클라이언트 선택)
  python main.py server [--map 파일] [--laps N] [--port P]   # 콘솔 전용 서버
"""
import argparse
import sys

from mapdata import DEFAULT_MAP_PATH, GameMap
from protocol import DEFAULT_PORT


def run_server_cli(args):
    from server import GameServer

    server = GameServer("0.0.0.0", args.port, GameMap.load(args.map), args.laps, auto_start=True)
    server.start()
    print(f"서버 시작: 포트 {args.port}, 맵 '{server.game.map.name}', {args.laps}바퀴")
    print("4명이 모이면 자동 시작합니다. 명령: start(바로 시작) / reset / quit")
    try:
        for line in sys.stdin:
            cmd = line.strip()
            try:
                if cmd == "start":
                    server.start_game()
                elif cmd == "reset":
                    server.reset_game()
                elif cmd == "quit":
                    break
            except Exception as e:
                print("오류:", e)
    except KeyboardInterrupt:
        pass
    server.stop()


def main():
    parser = argparse.ArgumentParser(description="카트라이더 보드게임")
    sub = parser.add_subparsers(dest="cmd")
    sp = sub.add_parser("server", help="콘솔 서버 실행")
    # sp.add_argument("--map", default=DEFAULT_MAP_PATH)
    # sp.add_argument("--laps", type=int, default=3)
    sp.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    if args.cmd == "server":
        run_server_cli(args)
    else:
        import gui
        gui.run()


if __name__ == "__main__":
    main()
