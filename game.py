"""네트워크와 무관한 게임 규칙."""
import json
import random
from pathlib import Path

from mapdata import (AMOUNT_KINDS, DEFAULT_START_DIRECTION_ORDER, GameMap,
                     effect_kind, effect_range, effect_title)

with Path(__file__).with_name("item_cards.json").open(encoding="utf-8") as card_file:
    ITEM_CARDS = json.load(card_file)["cards"]
ITEM_CARD_COUNTS = {card["id"]: card["count"] for card in ITEM_CARDS}

MAX_PLAYERS = 4
MIN_PLAYERS = 2
MAX_LAPS = 99
MAX_NAME_LENGTH = 30
# 플레이어 고유 색상 (images/pointer_*.png 의 색): 빨강, 핑크, 노랑, 파랑
COLORS = ["#e20122", "#fd3597", "#fed301", "#0082fe"]
CHARACTER_NAMES = ("배찌", "마리드", "디지니", "다오")
MIN_GEAR = 1
MAX_GEAR = 10
BASIC_MAX_GEAR = 6   # 기본(gage_basic) 게이지는 1~6단까지. 확장(gage_up) 시 10 으로 올린다.


def dice_for_gear(gear):
    """기어 단계별 굴릴 수 있는 최대 주사위 수."""
    if gear <= 2:
        return 1
    if gear <= 5:
        return 2
    if gear <= 9:
        return 3
    return 4


class GameError(Exception):
    pass


class Player:
    def __init__(self, pid, slot, name):
        self.id = pid
        self.slot = slot          # 0~3 (색상/말 위치)
        self.name = name
        self.progress = 0         # 출발선부터 이동한 총 칸 수
        self.cell = 0             # 현재 실제 칸 ID (분기 전용 칸 포함)
        self.previous_cell = None
        self.route_history = [0]
        self.forced_next_cells = []
        self.laps_completed = 0
        self.route = []           # 선택한 분기 경로에서 아직 지나지 않은 칸 ID
        self.luci = 0             # 루찌 (게임 내 돈)
        self.items = []           # 보유 아이템 카드 번호
        self.gear = MIN_GEAR
        self.connected = True


class Game:
    def __init__(self, game_map: GameMap, laps: int):
        self.players = []
        self.next_id = 0
        self.phase = "lobby"      # lobby / playing / finished
        self.max_gear = BASIC_MAX_GEAR
        self.turn = None          # 현재 차례 player id
        self.last_roll = None     # (pid, [주사위 눈들])
        self.pending_move = None
        self.move_seq = 0
        self.last_move_path = []
        self.effect_seq = 0
        self.last_effect_events = []
        self.roll_seq = 0         # 굴린 횟수 (클라이언트가 새 굴림을 구분하는 용도)
        self.start_seq = 0        # 게임 시작 횟수 (선 정하기 연출 구분용)
        self.start_rolls = None   # 선 정하기 라운드 목록: [[{pid, value}, ...], ...]
        self.item_deck = []
        self.traps = []
        self.winner = None
        self.set_map(game_map)
        self.set_laps(laps)

    # ---- 설정 ----
    def _require_lobby(self):
        if self.phase != "lobby":
            raise GameError("대기실에서만 변경할 수 있습니다.")

    def set_map(self, game_map):
        self._require_lobby()
        self.map = game_map

    def set_laps(self, laps):
        self._require_lobby()
        if not isinstance(laps, int) or not (1 <= laps <= MAX_LAPS):
            raise GameError(f"바퀴 수는 1~{MAX_LAPS} 범위여야 합니다.")
        self.laps = laps

    def place_trap(self, pid, trap_type):
        if self.phase != "playing":
            raise GameError("게임 중에만 함정을 설치할 수 있습니다.")
        if trap_type not in ("mine", "banana"):
            raise GameError("지원하지 않는 함정입니다.")
        player = self.get(pid)
        if player is None:
            raise GameError("플레이어를 찾을 수 없습니다.")
        trap = {"cell": player.cell, "type": trap_type}
        self.traps.append(trap)
        return dict(trap)

    @property
    def goal(self):
        return self.laps * self.map.length

    # ---- 플레이어 ----
    def add_player(self, name, auto_name=False):
        if self.phase != "lobby":
            raise GameError("이미 게임이 진행 중입니다.")
        if len(self.players) >= MAX_PLAYERS:
            raise GameError("방이 가득 찼습니다. (최대 4명)")
        used = {p.slot for p in self.players}
        slot = next(i for i in range(MAX_PLAYERS) if i not in used)
        name = (CHARACTER_NAMES[slot] if auto_name else
            (name or "").strip()[:MAX_NAME_LENGTH] or f"플레이어{slot + 1}")
        p = Player(self.next_id, slot, name)
        p.auto_name = auto_name
        self.next_id += 1
        self.players.append(p)
        return p

    def set_color(self, pid, slot):
        """대기실에서 플레이어의 색상(slot)을 바꾼다. 다른 플레이어가 쓰는 색상은 고를 수 없다."""
        self._require_lobby()
        p = self.get(pid)
        if p is None:
            raise GameError("플레이어를 찾을 수 없습니다.")
        if not isinstance(slot, int) or isinstance(slot, bool) or not (0 <= slot < MAX_PLAYERS):
            raise GameError("잘못된 색상입니다.")
        if any(q.slot == slot and q.id != pid for q in self.players):
            raise GameError("다른 플레이어가 이미 선택한 색상입니다.")
        p.slot = slot
        if p.auto_name:
            p.name = CHARACTER_NAMES[slot]

    def remove_player(self, pid):
        """접속 종료 처리. 진행 중이면 연결 해제 표시만 하고 턴을 넘긴다."""
        p = self.get(pid)
        if p is None:
            return
        if self.pending_move and self.pending_move["pid"] == pid:
            self.pending_move = None
        if self.phase == "lobby":
            self.players.remove(p)
            return
        p.connected = False
        if self.phase == "playing":
            if not any(q.connected for q in self.players):
                self.reset()
            elif self.turn == pid:
                self._advance_turn()

    def get(self, pid):
        return next((p for p in self.players if p.id == pid), None)

    # ---- 진행 ----
    def start(self):
        if self.phase != "lobby":
            raise GameError("이미 게임이 진행 중입니다.")
        if len(self.players) < MIN_PLAYERS:
            raise GameError(f"최소 {MIN_PLAYERS}명이 필요합니다.")
        self.item_deck = self._new_item_deck()
        random.shuffle(self.item_deck)
        self.traps = []
        for p in self.players:
            p.progress = 0
            p.cell = 0
            p.previous_cell = None
            p.route_history = [0]
            p.forced_next_cells = []
            p.laps_completed = 0
            p.route = []
            p.gear = MIN_GEAR
            p.luci = 0
            p.items = []
        self.phase = "playing"
        self.winner = None
        self.last_roll = None
        self.pending_move = None
        self.last_move_path = []
        logs = self._decide_first()
        return logs

    def _decide_first(self):
        """모두 주사위 1개를 굴려 가장 높은 사람이 선공. 동점이면 동점자끼리 다시 굴린다."""
        self.start_seq += 1
        self.start_rolls = []
        logs = []
        contenders = [p.id for p in self.players]
        while True:
            rnd = [{"pid": pid, "value": random.randint(1, 3)} for pid in contenders]
            self.start_rolls.append(rnd)
            text = ", ".join(f"{self.get(r['pid']).name} {r['value']}" for r in rnd)
            logs.append(f"[선 정하기 {len(self.start_rolls)}차] {text}")
            top = max(r["value"] for r in rnd)
            contenders = [r["pid"] for r in rnd if r["value"] == top]
            if len(contenders) == 1:
                break
            logs.append("동점! 동점자끼리 다시 굴립니다.")
        self.turn = contenders[0]
        logs.append(f"{self.get(self.turn).name} 님이 선공입니다.")
        return logs

    @staticmethod
    def _new_item_deck(pool=None):
        allowed = set(pool) if pool is not None else None
        return [card_id for card_id, count in ITEM_CARD_COUNTS.items()
                if allowed is None or card_id in allowed
                for _ in range(count)]

    def _draw_item_card(self, pool=None):
        allowed = set(pool) if pool is not None else None
        available = [card for card in self.item_deck
                     if allowed is None or card in allowed]
        if not available:
            refill = self._new_item_deck(pool)
            if not refill:
                raise GameError("아이템 박스 풀에 정의된 카드가 없습니다.")
            random.shuffle(refill)
            self.item_deck.extend(refill)
            available = [card for card in self.item_deck
                         if allowed is None or card in allowed]
        card = random.choice(available)
        self.item_deck.remove(card)
        return card

    def reset(self):
        self.players = [p for p in self.players if p.connected]
        for p in self.players:
            p.luci = 0
            p.items = []
            p.progress = 0
            p.cell = 0
            p.previous_cell = None
            p.route_history = [0]
            p.forced_next_cells = []
            p.laps_completed = 0
            p.route = []
            p.gear = MIN_GEAR
        self.phase = "lobby"
        self.turn = None
        self.winner = None
        self.last_roll = None
        self.pending_move = None
        self.last_move_path = []
        self.last_effect_events = []
        self.start_rolls = None
        self.item_deck = []
        self.traps = []

    def _advance_turn(self):
        ids = [p.id for p in self.players]
        i = ids.index(self.turn)
        for k in range(1, len(ids) + 1):
            p = self.players[(i + k) % len(ids)]
            if p.connected:
                self.turn = p.id
                return

    def start_roll(self, pid):
        """주사위를 굴리고 분기점 선택이 필요하면 이동을 잠시 멈춘다."""
        if self.phase != "playing":
            raise GameError("게임 진행 중이 아닙니다.")
        if pid != self.turn:
            raise GameError("당신의 차례가 아닙니다.")
        if self.pending_move:
            raise GameError("현재 분기 이동을 먼저 마쳐야 합니다.")
        p = self.get(pid)
        values = [random.randint(1, 3) for _ in range(dice_for_gear(p.gear))]
        total = sum(values)
        self.last_roll = (pid, values)
        self.roll_seq += 1
        self.last_effect_events = []
        self.pending_move = {"pid": pid, "remaining": total, "branch": None}
        self.last_move_path = []
        dice_text = " + ".join(map(str, values))
        logs = [f"{p.name}: 주사위 {dice_text} = {total}"]
        logs.extend(self._continue_move())
        return logs

    def choose_branch(self, pid, direction):
        """현재 분기점에서 선택한 경로를 따라 남은 이동을 계속한다."""
        pending = self.pending_move
        if not pending or pending["pid"] != pid or pending["branch"] is None:
            raise GameError("선택할 수 있는 분기점이 없습니다.")
        if direction not in pending["branch"]["choices"]:
            raise GameError("잘못된 분기 방향입니다.")
        p = self.get(pid)
        choices = pending["branch"]["choice_cells"]
        next_cell = next((cell for cell in self._movement_options(p)
                  if self.map.direction_between(p.cell, cell) == direction), None)
        if next_cell is None or next_cell not in choices.values():
            raise GameError("선택할 수 없는 인접 경로입니다.")
        pending["next_cell"] = next_cell
        pending["branch"] = None
        label = {"up": "위", "right": "오른쪽", "down": "아래", "left": "왼쪽"}[direction]
        return [f"{p.name} 님이 {label} 경로를 선택했습니다."] + self._continue_move()

    def roll(self, pid):
        """분기점이 없는 맵을 위한 동기식 호환 API."""
        logs = self.start_roll(pid)
        if self.pending_move:
            raise GameError("분기점 선택이 필요합니다. start_roll()을 사용해 주세요.")
        return logs

    def _movement_options(self, p):
        options = [cell for cell in self.map.neighbor_ids(p.cell)
                   if cell != p.previous_cell]
        source = self.map.cells[p.cell]
        is_drift_source = any(effect["cell"] == p.cell and effect.get("type") == "drift"
                              and "to" not in effect for effect in self.map.effects)
        if is_drift_source:
            drift_targets = {self.map.cell_id(target)
                             for start, target in self.map.drift_connection_pairs
                             if start == source}
            default_options = [cell for cell in options if cell not in drift_targets]
            options = default_options or options

        if p.previous_cell is not None:
            previous = self.map.cells[p.previous_cell]
            current = self.map.cells[p.cell]
            drift_arrivals = set(self.map.drift_connection_pairs)
            drift_arrivals.update(
                (self.map.path[effect["cell"]], self.map.path[effect["to"]])
                for effect in self.map.effects
                if effect.get("type") == "drift" and "to" in effect)
            if (previous, current) in drift_arrivals and options:
                direction = self.map.direction_between(p.previous_cell, p.cell)
                if direction is None:
                    dx, dy = current[0] - previous[0], current[1] - previous[1]
                    if dx and not dy:
                        direction = "right" if dx > 0 else "left"
                    elif dy and not dx:
                        direction = "down" if dy > 0 else "up"
                straight = [cell for cell in options
                            if self.map.direction_between(p.cell, cell) == direction]
                if straight:
                    return straight[:1]
                reverse = self.map.direction_between(p.cell, p.previous_cell)
                away = [cell for cell in options
                        if self.map.direction_between(p.cell, cell) != reverse]
                return (away or options)[:1]
        return options

    def _continue_move(self):
        pending = self.pending_move
        p = self.get(pending["pid"])
        before_laps = p.laps_completed
        moved = []
        logs = []
        while pending["remaining"] > 0:
            next_cell = pending.pop("next_cell", None)
            if next_cell is None and p.forced_next_cells:
                next_cell = p.forced_next_cells.pop(0)
            if next_cell is None:
                if p.cell == 0 and p.previous_cell is None:
                    if self.map.start_direction is not None:
                        next_cell = self.map.cell_id(self.map.start_direction)
                    else:
                        adjacent = self.map.neighbor_ids(p.cell)
                        next_cell = next((cell for direction in DEFAULT_START_DIRECTION_ORDER
                                          for cell in adjacent
                                          if self.map.direction_between(p.cell, cell) == direction),
                                         None)
                        if next_cell is None:
                            raise GameError("출발 타일에 이동할 수 있는 연결이 없습니다.")
                else:
                    options = self._movement_options(p)
                    if len(options) > 1:
                        choices = {self.map.direction_between(p.cell, cell): cell for cell in options}
                        pending["branch"] = {"pid": p.id, "cell": p.cell,
                                              "choices": list(choices), "choice_cells": choices}
                        break
                    if not options:
                        raise GameError("이전 타일을 제외한 이동 경로가 없습니다.")
                    next_cell = options[0]
            previous_cell = p.cell
            p.previous_cell = previous_cell
            p.cell = next_cell
            p.route_history.append(p.cell)
            p.progress += 1
            if p.cell == 0:
                p.laps_completed += 1
            pending["remaining"] -= 1
            moved.append(p.cell)
            if p.laps_completed >= self.laps:
                self._lap_logs(p, before_laps, p.laps_completed, logs)
                self._record_move(moved)
                self.phase = "finished"
                self.winner = p.id
                self.turn = None
                self.pending_move = None
                logs.append(f"{p.name} 님이 {self.laps}바퀴를 완주하고 승리했습니다!")
                return logs
        self._record_move(moved)
        self._lap_logs(p, before_laps, p.laps_completed, logs)
        if pending["branch"] is not None:
            return logs
        self.pending_move = None
        logs.extend(self._apply_effects(p))
        if p.laps_completed >= self.laps:
            self.phase = "finished"
            self.winner = p.id
            self.turn = None
            logs.append(f"{p.name} 님이 {self.laps}바퀴를 완주하고 승리했습니다!")
        else:
            self._advance_turn()
        return logs

    def _record_move(self, cells):
        self.last_move_path = list(cells)
        if cells:
            self.move_seq += 1

    def _lap_logs(self, p, old, new, logs):
        """출발 타일에 재진입해 완주한 바퀴를 기록한다."""
        for lap in range(old + 1, new + 1):
            logs.append(f"{p.name} 님 {lap}바퀴 완주! (남은 바퀴 {self.laps - lap})")

    def _apply_effects(self, p):
        """플레이어가 멈춘 칸의 효과를 적용한다. 이동 효과로 닿은 칸의 효과는 다시 발동하지 않는다."""
        logs = []
        n = self.map.length
        effect_cell = p.cell if p.cell < n else None
        for e in self.map.effects_at(effect_cell) if effect_cell is not None else []:
            kind, title = effect_kind(e), effect_title(e)
            notice = ""
            if kind in AMOUNT_KINDS:
                lo, hi = effect_range(e)
                amount = random.randint(lo, hi)
            if kind == "gear":
                old = p.gear
                p.gear = max(MIN_GEAR, min(self.max_gear, old + amount))
                if p.gear == old:
                    logs.append(f"[{title}] {p.name} 님의 기어는 {old}단 그대로입니다.")
                    notice = f"기어 {old}단 유지"
                else:
                    word = "올라갑니다" if p.gear > old else "내려갑니다"
                    logs.append(f"[{title}] {p.name} 님의 기어가 {old}단 → {p.gear}단으로 {word}. "
                                f"(주사위 최대 {dice_for_gear(p.gear)}개)")
                    notice = f"기어 {old}단에서 {p.gear}단으로 변경"
            elif kind == "move":
                old_laps = p.laps_completed
                moved_cells = []
                reversed_cells = []
                for _ in range(abs(amount)):
                    if amount < 0:
                        neighbors = self.map.neighbor_ids(p.cell)
                        if (len(p.route_history) < 2
                                or p.route_history[-1] != p.cell):
                            break
                        next_cell = p.route_history[-2]
                        if next_cell not in neighbors:
                            break
                        reversed_cells.append(p.cell)
                        p.route_history.pop()
                    else:
                        options = self._movement_options(p)
                        if not options:
                            break
                        next_cell = options[0]
                    p.previous_cell, p.cell = p.cell, next_cell
                    if amount > 0:
                        p.route_history.append(p.cell)
                    p.progress += 1
                    if p.cell == 0:
                        p.laps_completed = max(0, p.laps_completed + (1 if amount > 0 else -1))
                    moved_cells.append(p.cell)
                if reversed_cells:
                    p.forced_next_cells = list(reversed(reversed_cells)) + p.forced_next_cells
                moved = len(moved_cells)
                if moved == 0:
                    logs.append(f"[{title}] {p.name} 님은 제자리입니다.")
                    notice = "제자리"
                else:
                    self.last_move_path.extend(moved_cells)
                    self.move_seq += 1
                    self._lap_logs(p, old_laps, p.laps_completed, logs)
                    way = "앞으로" if amount > 0 else "뒤로"
                    logs.append(f"[{title}] {p.name} 님이 {way} {abs(moved)}칸 이동 → "
                                f"{p.cell + 1}번 칸")
                    notice = f"{way} {abs(moved)}칸 이동"
            elif kind == "luci":
                old = p.luci
                p.luci = max(0, old + amount)
                logs.append(f"[{title}] {p.name} 님의 루찌 {old} → {p.luci} ({p.luci - old:+d})")
                delta = p.luci - old
                notice = f"루찌 {abs(delta)} {'획득' if delta > 0 else '차감'}" if delta else "루찌 변화 없음"
            elif kind == "drift":
                if "to" in e:
                    target_cell = e["to"]
                else:
                    source = self.map.cells[p.cell]
                    target = next(target for start, target in self.map.drift_connection_pairs
                                  if start == source)
                    target_cell = self.map.cell_id(target)
                old_cell = p.cell
                old_laps = p.laps_completed
                p.previous_cell, p.cell = old_cell, target_cell
                p.route_history.append(p.cell)
                p.progress += 1
                if p.cell == 0:
                    p.laps_completed += 1
                self.last_move_path.append(p.cell)
                self.move_seq += 1
                self._lap_logs(p, old_laps, p.laps_completed, logs)
                logs.append(f"{p.name}가 드리프트 성공!")
                notice = "드리프트 성공!"
            elif kind == "item_box":
                card = self._draw_item_card(e.get("pool"))
                p.items.append(card)
                logs.append(f"[{title}] {p.name} 님이 아이템 카드 {card}번을 얻었습니다.")
                notice = f"아이템 카드 {card}번 획득"
            elif kind == "shop":
                logs.append(f"[{title}] {p.name} 님이 상점에 도착했습니다. (루찌 {p.luci})")
                notice = "상점 도착"
            if notice:
                self.effect_seq += 1
                self.last_effect_events.append({
                    "seq": self.effect_seq, "pid": p.id,
                    "text": notice if kind == "drift" else f"{title} - {notice}"
                })
        return logs

    # ---- 직렬화 ----
    def snapshot(self):
        n = self.map.length
        return {
            "type": "state",
            "phase": self.phase,
            "map": self.map.to_dict(),
            "laps": self.laps,
            "max_gear": self.max_gear,
            "turn": self.turn,
            "winner": self.winner,
            "last_roll": ({"pid": self.last_roll[0], "values": self.last_roll[1]}
                          if self.last_roll else None),
            "branch_request": self.pending_move["branch"] if self.pending_move else None,
            "move_seq": self.move_seq,
            "move_pid": self.last_roll[0] if self.last_roll else None,
            "move_path": list(self.last_move_path),
            "roll_seq": self.roll_seq,
            "start_seq": self.start_seq,
            "start_rolls": self.start_rolls,
            "effect_events": list(self.last_effect_events),
            "traps": [dict(trap) for trap in self.traps],
            "players": [{
                "id": p.id, "slot": p.slot, "name": p.name,
                "connected": p.connected,
                "cell": p.cell,
                "lap": min(p.laps_completed + 1, self.laps),
                "laps_completed": p.laps_completed,
                "progress": p.progress,
                "gear": p.gear,
                "luci": p.luci,
                "items": list(p.items),
                "dice": dice_for_gear(p.gear),
            } for p in self.players],
        }
