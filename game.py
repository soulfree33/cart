"""네트워크와 무관한 게임 규칙."""
import json
import random
from pathlib import Path

from mapdata import (AMOUNT_KINDS, DEFAULT_START_DIRECTION_ORDER, GameMap,
                     SHOP_CARD_COUNT, effect_kind, effect_range, effect_title)

with Path(__file__).with_name("item_cards.json").open(encoding="utf-8") as card_file:
    ITEM_CARDS = json.load(card_file)["cards"]
ITEM_CARD_COUNTS = {card["id"]: card["count"] for card in ITEM_CARDS}
with Path(__file__).with_name("shop_cards.json").open(encoding="utf-8") as card_file:
    SHOP_CARDS = json.load(card_file)["cards"]
SHOP_CARDS_BY_ID = {card["id"]: card for card in SHOP_CARDS}
SHOP_CARD_COUNTS = {card["id"]: card["count"] for card in SHOP_CARDS}
SHOP_CARD_COSTS = {card["id"]: card["cost_luci"] for card in SHOP_CARDS}

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
BASE_ITEM_CARD_CAPACITY = 2


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
        self.shop_cards = []
        self.shop_visits = []
        self.gear_gauge_upgraded = False
        self.status_effects = set()
        self.gear = MIN_GEAR
        self.connected = True

    @property
    def gear_limit(self):
        return MAX_GEAR if self.gear_gauge_upgraded else BASIC_MAX_GEAR


class Game:
    def __init__(self, game_map: GameMap, laps: int):
        self.players = []
        self.next_id = 0
        self.phase = "lobby"      # lobby / playing / finished
        self.max_gear = BASIC_MAX_GEAR
        self.turn = None          # 현재 차례 player id
        self.last_roll = None     # (pid, [주사위 눈들])
        self.pending_move = None
        self.pending_shop_choice = None
        self.shop_choice_seq = 0
        self.reaction_moves = []
        self.move_seq = 0
        self.last_move_pid = None
        self.last_move_path = []
        self.effect_seq = 0
        self.last_effect_events = []
        self.roll_seq = 0         # 굴린 횟수 (클라이언트가 새 굴림을 구분하는 용도)
        self.start_seq = 0        # 게임 시작 횟수 (선 정하기 연출 구분용)
        self.start_rolls = None   # 선 정하기 라운드 목록: [[{pid, value}, ...], ...]
        self.item_deck = []
        self.shop_stock = dict(SHOP_CARD_COUNTS)
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
        if self.pending_shop_choice and self.pending_shop_choice["pid"] == pid:
            self.pending_shop_choice = None
        self.reaction_moves = [(move_pid, steps) for move_pid, steps in self.reaction_moves
                               if move_pid != pid]
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

    def debug_teleport(self, pid, cell):
        if self.phase != "playing":
            raise GameError("게임 중에만 디버그 이동을 사용할 수 있습니다.")
        if self.pending_move:
            raise GameError("분기 이동 중에는 디버그 이동을 사용할 수 없습니다.")
        player = self.get(pid)
        if player is None or not player.connected:
            raise GameError("플레이어를 찾을 수 없습니다.")
        if (not isinstance(cell, int) or isinstance(cell, bool)
                or not 0 <= cell < len(self.map.cells)):
            raise GameError("선택한 맵 타일이 올바르지 않습니다.")

        player.cell = cell
        player.previous_cell = None
        player.route_history = [cell]
        player.route = []
        player.forced_next_cells.clear()
        self.last_move_path = []
        return [f"[디버그] {player.name} 님의 말을 {cell + 1}번 타일로 이동했습니다."]

    def _block_effect(self, player, effect_type, effect_name, logs):
        defense = None
        if "shield" in player.status_effects:
            player.status_effects.remove("shield")
            defense = "실드"
        elif effect_type in {"attack", "trap"} and "angel" in player.status_effects:
            defense = "천사"
        if defense:
            logs.append(
                f"[{defense}] {player.name} 님이 {effect_name} 효과를 무효화했습니다.")
            return True
        return False

    def _apply_gear_attack(self, targets, amount, card_name, logs, attacker, item_id):
        successful_targets = []
        for target in targets:
            if self._block_effect(target, "attack", card_name, logs):
                continue
            effective_amount = amount
            if effective_amount < 0:
                for effect in self._shop_effects_of_type(
                        target, "reduce_gear_loss_from_item_attack"):
                    if item_id in effect.get("item_ids", []):
                        effective_amount += effect.get("amount", 0)
            for effect in self._shop_effects(attacker):
                if (effect.get("type") == "additional_gear_loss_on_item_attack"
                        and item_id in effect.get("item_ids", [])):
                    effective_amount += effect.get("amount", 0)
            old = target.gear
            self._set_gear(target, old + effective_amount)
            if target.gear == old:
                logs.append(f"[{card_name}] {target.name} 님의 기어는 {old}단입니다.")
            else:
                logs.append(
                    f"[{card_name}] {target.name} 님의 기어가 "
                    f"{old}단에서 {target.gear}단으로 변경되었습니다.")
            successful_targets.append(target)
            for effect in self._shop_effects_of_type(target, "move_after_item_attack"):
                if item_id in effect.get("item_ids", []):
                    self.reaction_moves.append((target.id, effect.get("amount", 0)))
        return successful_targets

    @staticmethod
    def _shop_effects(player):
        return [SHOP_CARDS_BY_ID[card_id]["effect"]
                for card_id in player.shop_cards if card_id in SHOP_CARDS_BY_ID]

    def _has_shop_effect(self, player, effect_type):
        return any(effect.get("type") == effect_type
                   for effect in self._shop_effects(player))

    def _shop_effects_of_type(self, player, effect_type):
        return [effect for effect in self._shop_effects(player)
                if effect.get("type") == effect_type]

    def _gear_floor(self, player):
        return max(
            [MIN_GEAR] + [
                effect.get("minimum", MIN_GEAR)
                for effect in self._shop_effects(player)
                if effect.get("type") == "gear_floor"
            ])

    def _item_capacity(self, player):
        return BASE_ITEM_CARD_CAPACITY + sum(
            effect.get("amount", 0)
            for effect in self._shop_effects_of_type(player, "increase_item_capacity"))

    def _set_gear(self, player, value):
        player.gear = max(self._gear_floor(player), min(player.gear_limit, value))

    def _start_reaction_moves(self):
        logs = []
        while self.reaction_moves and not self.pending_move and self.phase == "playing":
            pid, steps = self.reaction_moves.pop(0)
            target = self.get(pid)
            if not target or not target.connected:
                continue
            self.last_move_path = []
            self.pending_move = {
                "pid": pid, "remaining": steps, "branch": None,
                "advance_turn": False,
            }
            logs.extend(self._continue_move())
            if self.pending_move:
                break
        return logs

    def _move_missile_successes(self, player, targets):
        effects = self._shop_effects_of_type(player, "multi_target_item_attack")
        steps_per_target = sum(effect.get("move_forward_per_success", 0)
                               for effect in effects)
        steps = len(targets) * steps_per_target
        if not steps:
            return []
        self.last_move_path = []
        self.pending_move = {
            "pid": player.id, "remaining": steps, "branch": None,
            "advance_turn": True,
        }
        return [f"[세이버 헬파이어] 공격 성공 대상 {len(targets)}명만큼 "
                f"{steps}칸 이동합니다."] + self._continue_move()

    def _move_back_along_route(self, player, steps):
        old_laps = player.laps_completed
        reversed_cells = []
        backward_path = []
        for _ in range(steps):
            neighbors = self.map.neighbor_ids(player.cell)
            if (len(player.route_history) < 2
                    or player.route_history[-1] != player.cell):
                break
            next_cell = player.route_history[-2]
            if next_cell not in neighbors:
                break
            reversed_cells.append(player.cell)
            was_start = player.cell == 0
            player.route_history.pop()
            player.previous_cell, player.cell = player.cell, next_cell
            backward_path.append(player.cell)
            self._record_shop_visits_for_path(player, (player.cell,))
            player.progress = max(0, player.progress - 1)
            if was_start:
                player.laps_completed = max(0, player.laps_completed - 1)
        if reversed_cells:
            player.forced_next_cells = (
                list(reversed(reversed_cells)) + player.forced_next_cells)
        return backward_path, len(reversed_cells), old_laps

    def use_item(self, pid, card_id, target_pid=None, debug_mode=False,
                 target_pids=None, use_super_booster=False):
        if self.phase != "playing":
            raise GameError("게임 중에만 아이템 카드를 사용할 수 있습니다.")
        player = self.get(pid)
        if player is None or not player.connected:
            raise GameError("플레이어를 찾을 수 없습니다.")
        if not debug_mode and pid != self.turn:
            raise GameError("자신의 차례에만 아이템 카드를 사용할 수 있습니다.")
        if self.pending_move or self.pending_shop_choice:
            raise GameError("이동이 끝난 뒤 아이템 카드를 사용할 수 있습니다.")
        if (not isinstance(card_id, int) or isinstance(card_id, bool)
                or card_id not in ITEM_CARD_COUNTS):
            raise GameError("잘못된 아이템 카드입니다.")
        if not debug_mode and card_id not in player.items:
            raise GameError("보유하지 않은 아이템 카드입니다.")
        if not isinstance(use_super_booster, bool):
            raise GameError("잘못된 부스터 효과 선택입니다.")
        if use_super_booster and (
                card_id != 3
                or not self._has_shop_effect(player, "choose_item_effect_upgrade")):
            raise GameError("슈퍼부스터 효과를 선택할 수 없습니다.")

        card_name = next(card["name"] for card in ITEM_CARDS if card["id"] == card_id)
        logs = []
        self.last_effect_events = []
        card_consumed = False
        connected = [p for p in self.players if p.connected]
        if card_id in (5, 16):
            trap_type = "mine" if card_id == 5 else "banana"
            self.place_trap(pid, trap_type)
            logs.append(
                f"{player.name} 님이 {card_name} 카드를 사용했습니다. "
                f"{player.cell + 1}번 타일에 설치했습니다.")
        elif card_id == 1:
            if (not isinstance(target_pid, int) or isinstance(target_pid, bool)):
                raise GameError("효과를 받을 플레이어를 선택해 주세요.")
            target = self.get(target_pid)
            if target is None or not target.connected:
                raise GameError("효과를 받을 플레이어를 선택해 주세요.")
            logs.append(f"{player.name} 님이 {card_name} 카드를 사용했습니다.")
            if not self._block_effect(target, "effect", card_name, logs):
                target.status_effects.add("cloud")
                logs.append(
                    f"{target.name} 님은 다음 기본 이동에서 주사위 눈 3이 1로 바뀝니다.")
        elif card_id == 2:
            if not connected:
                raise GameError("효과를 받을 플레이어가 없습니다.")
            target = max(connected, key=lambda p: p.progress)
            logs.append(f"{player.name} 님이 {card_name} 카드를 사용했습니다.")
            self._apply_gear_attack([target], -2, card_name, logs, player, card_id)
        elif card_id == 3:
            if use_super_booster:
                logs.append(f"{player.name} 님이 {card_name} 카드를 슈퍼부스터 효과로 사용했습니다.")
                logs.extend(self._start_item_move(player, 2))
                if card_id in player.items:
                    player.items.remove(card_id)
                return logs
            old = player.gear
            self._set_gear(player, player.gear + 2)
            logs.append(
                f"{player.name} 님이 {card_name} 카드를 사용했습니다. "
                f"기어 {old}단에서 {player.gear}단으로 변경되었습니다.")
        elif card_id == 4:
            player.status_effects.add("shield")
            logs.append(f"{player.name} 님이 {card_name} 카드를 사용했습니다.")
        elif card_id == 6:
            player.status_effects.add("angel")
            logs.append(f"{player.name} 님이 {card_name} 카드를 사용했습니다.")
        elif card_id == 7:
            logs.append(f"{player.name} 님이 {card_name} 카드를 사용했습니다.")
            for target in connected:
                if not self._block_effect(target, "effect", card_name, logs):
                    target.status_effects.add("demon_king")
                    logs.append(
                        f"{target.name} 님은 다음 이동에서 주사위를 1개만 굴립니다.")
        elif card_id == 8:
            targets = self._validate_missile_targets(
                player, target_pid, target_pids,
                multi_target=self._has_shop_effect(player, "multi_target_item_attack"))
            logs.append(f"{player.name} 님이 {card_name} 카드를 사용했습니다.")
            successful = self._apply_gear_attack(
                targets, -2, card_name, logs, player, card_id)
            if successful:
                logs.extend(self._move_missile_successes(player, successful))
        elif card_id == 9:
            target_cells = self._forward_tiles(player, {4, 5})
            targets = [p for p in connected if p.cell in target_cells]
            logs.append(f"{player.name} 님이 {card_name} 카드를 사용했습니다.")
            if targets:
                self._apply_gear_attack(targets, -3, card_name, logs, player, card_id)
            else:
                logs.append(f"[{card_name}] 효과를 받을 플레이어가 없습니다.")
        elif card_id == 10:
            if not connected:
                raise GameError("효과를 받을 플레이어가 없습니다.")
            target = max(connected, key=lambda p: p.progress)
            logs.append(f"{player.name} 님이 {card_name} 카드를 사용했습니다.")
            if not self._block_effect(target, "effect", card_name, logs):
                target.status_effects.add("ufo")
                logs.append(
                    f"1위 {target.name} 님은 다음 기본 이동에서 주사위를 1개 적게 굴립니다.")
        elif card_id == 11:
            if (not isinstance(target_pid, int) or isinstance(target_pid, bool)):
                raise GameError("앞선 플레이어를 선택해 주세요.")
            target = self.get(target_pid)
            if target is None or not target.connected or target.progress <= player.progress:
                raise GameError("내 앞에 있는 플레이어를 선택해 주세요.")
            logs.append(f"{player.name} 님이 {card_name} 카드를 사용했습니다.")
            if not self._block_effect(target, "attack", card_name, logs):
                roll = random.randint(1, 3)
                backward_path, moved_back, old_laps = self._move_back_along_route(
                    target, roll)
                self._lap_logs(target, old_laps, target.laps_completed, logs)
                if moved_back:
                    logs.append(
                        f"{target.name} 님은 {roll} 눈에 따라 {moved_back}칸 뒤로 이동합니다.")
                else:
                    logs.append(f"{target.name} 님은 뒤로 이동하지 못했습니다.")
                trap_logs, _, _ = self._trigger_traps(target)
                logs.extend(trap_logs)
                if moved_back:
                    logs.extend(self._apply_effects(target, arrived_by_move=True))
                for effect in self._shop_effects_of_type(
                        player, "use_item_after_success"):
                    if effect.get("trigger_item_id") != card_id:
                        continue
                    shop_card_name = next(
                        card["name"] for card in SHOP_CARDS
                        if card["effect"] == effect)
                    for affected in connected:
                        if not self._block_effect(
                                affected, "effect", shop_card_name, logs):
                            affected.status_effects.add("demon_king")
                            logs.append(
                                f"[{shop_card_name}] {affected.name} 님은 다음 이동에서 "
                                "주사위를 1개만 굴립니다.")
                if "demon_king" in player.status_effects:
                    player.status_effects.remove("demon_king")
                if card_id in player.items:
                    player.items.remove(card_id)
                    card_consumed = True
                self.last_roll = (pid, [roll])
                self.roll_seq += 1
                self.last_move_path = []
                self.pending_move = {
                    "pid": pid, "remaining": roll, "branch": None,
                }
                logs.extend(self._continue_move())
        elif card_id == 12:
            ahead = [p for p in connected
                     if p.id != pid and p.progress > player.progress]
            if not ahead:
                raise GameError("내 바로 앞에 있는 플레이어가 없습니다.")
            target = min(ahead, key=lambda p: p.progress)
            logs.append(f"{player.name} 님이 {card_name} 카드를 사용했습니다.")
            self._apply_gear_attack([target], -2, card_name, logs, player, card_id)
        elif card_id == 14:
            logs.append(f"{player.name} 님이 {card_name} 카드를 사용했습니다.")
            logs.extend(self._start_item_move(player, 2))
            if card_id in player.items:
                player.items.remove(card_id)
            logs.extend(self._start_reaction_moves())
            return logs
        elif card_id == 17:
            targets = [p for p in connected if p.id != pid and p.progress > player.progress]
            logs.append(f"{player.name} 님이 {card_name} 카드를 사용했습니다.")
            if targets:
                self._apply_gear_attack(targets, -2, card_name, logs, player, card_id)
            else:
                logs.append(f"[{card_name}] 앞선 플레이어가 없습니다.")

        if card_id in player.items and not card_consumed:
            player.items.remove(card_id)
        logs.extend(self._start_reaction_moves())
        return logs

    def _trigger_traps(self, player):
        triggered = [trap for trap in self.traps if trap["cell"] == player.cell]
        logs = []
        moved = False
        backward_path = []
        for trap in triggered:
            self.traps.remove(trap)
            trap_name = "지뢰" if trap["type"] == "mine" else "바나나"
            if self._block_effect(player, "trap", trap_name, logs):
                continue
            if trap["type"] == "mine":
                old_laps = player.laps_completed
                reversed_cells = []
                mine_path = []
                for _ in range(3):
                    neighbors = self.map.neighbor_ids(player.cell)
                    if (len(player.route_history) < 2
                            or player.route_history[-1] != player.cell):
                        break
                    next_cell = player.route_history[-2]
                    if next_cell not in neighbors:
                        break
                    reversed_cells.append(player.cell)
                    was_start = player.cell == 0
                    player.route_history.pop()
                    player.previous_cell, player.cell = player.cell, next_cell
                    mine_path.append(player.cell)
                    self._record_shop_visits_for_path(player, (player.cell,))
                    player.progress = max(0, player.progress - 1)
                    if was_start:
                        player.laps_completed = max(0, player.laps_completed - 1)
                if reversed_cells:
                    player.forced_next_cells = (
                        list(reversed(reversed_cells)) + player.forced_next_cells)
                    backward_path.extend(mine_path)
                    self._lap_logs(player, old_laps, player.laps_completed, logs)
                    logs.append(
                        f"[지뢰] {player.name} 님이 {len(reversed_cells)}칸 뒤로 이동했습니다.")
                    moved = True
                else:
                    logs.append(f"[지뢰] {player.name} 님은 뒤로 이동하지 못했습니다.")
            elif trap["type"] == "banana":
                old_gear = player.gear
                self._set_gear(player, player.gear - 3)
                logs.append(
                    f"[바나나] {player.name} 님의 기어가 "
                    f"{old_gear}단에서 {player.gear}단으로 내려갔습니다.")
        return logs, moved, backward_path

    # ---- 진행 ----
    def start(self):
        if self.phase != "lobby":
            raise GameError("이미 게임이 진행 중입니다.")
        if len(self.players) < MIN_PLAYERS:
            raise GameError(f"최소 {MIN_PLAYERS}명이 필요합니다.")
        self.item_deck = self._new_item_deck()
        random.shuffle(self.item_deck)
        self.shop_stock = dict(SHOP_CARD_COUNTS)
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
            p.shop_cards = []
            p.shop_visits = []
            p.gear_gauge_upgraded = False
            p.status_effects.clear()
        self.phase = "playing"
        self.winner = None
        self.last_roll = None
        self.pending_move = None
        self.pending_shop_choice = None
        self.reaction_moves = []
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

    def _record_shop_visits_for_path(self, player, cells):
        for cell in cells:
            effects = [effect for effect in self.map.effects_at(cell)
                       if effect_kind(effect) == "shop"]
            for effect in effects[:1]:
                allowed = set(effect.get("items", range(1, SHOP_CARD_COUNT + 1)))
                available_cards = sorted(
                    card_id for card_id, stock in self.shop_stock.items()
                    if stock > 0 and card_id in allowed)
                self.effect_seq += 1
                visit = {
                    "token": self.effect_seq,
                    "cell": cell,
                    "available_cards": available_cards,
                }
                player.shop_visits.append(visit)
                self.last_effect_events.append({
                    "seq": self.effect_seq,
                    "pid": player.id,
                    "kind": "shop_visit",
                    "shop_token": self.effect_seq,
                    "available_cards": available_cards,
                    "cell": cell,
                    "text": "상점 방문",
                })

    def purchase_shop(self, pid, shop_token, card_id=None, upgrade_gauge=False):
        if self.phase != "playing":
            raise GameError("게임 중에만 상점을 이용할 수 있습니다.")
        player = self.get(pid)
        if player is None or not player.connected:
            raise GameError("플레이어를 찾을 수 없습니다.")
        if (not isinstance(shop_token, int) or isinstance(shop_token, bool)):
            raise GameError("잘못된 상점 방문입니다.")
        if card_id is not None and (
                not isinstance(card_id, int) or isinstance(card_id, bool)):
            raise GameError("잘못된 상점 카드입니다.")
        if not isinstance(upgrade_gauge, bool):
            raise GameError("잘못된 기어 게이지 선택입니다.")
        visit = next((visit for visit in player.shop_visits
                      if visit["token"] == shop_token), None)
        if visit is None:
            raise GameError("이용할 수 있는 상점 방문이 없습니다.")
        if card_id is None and not upgrade_gauge:
            raise GameError("구매할 카드나 업그레이드를 선택해 주세요.")
        if upgrade_gauge and player.gear_gauge_upgraded:
            raise GameError("기어 게이지가 이미 업그레이드되어 있습니다.")
        if card_id is not None:
            if card_id not in SHOP_CARD_COUNTS:
                raise GameError("구매할 수 없는 상점 카드입니다.")
            if card_id not in visit["available_cards"]:
                raise GameError("이 상점에서 판매하지 않는 카드입니다.")
            if self.shop_stock.get(card_id, 0) <= 0:
                raise GameError("상점 카드가 품절되었습니다.")

        total_cost = (SHOP_CARD_COSTS.get(card_id, 0) if card_id is not None else 0)
        if upgrade_gauge:
            total_cost += 5
        if player.luci < total_cost:
            raise GameError("루찌가 부족합니다.")

        player.luci -= total_cost
        logs = []
        if card_id is not None:
            player.shop_cards.append(card_id)
            self.shop_stock[card_id] -= 1
            logs.append(
                f"{player.name} 님이 {SHOP_CARDS_BY_ID[card_id]['name']} 카드를 "
                f"{SHOP_CARD_COSTS[card_id]}루찌에 구매했습니다.")
            card_effect = SHOP_CARDS_BY_ID[card_id]["effect"]
            if card_effect.get("on_purchase"):
                old_gear = player.gear
                self._set_gear(player, max(player.gear, card_effect.get("minimum", MIN_GEAR)))
                if player.gear != old_gear:
                    logs.append(
                        f"[{SHOP_CARDS_BY_ID[card_id]['name']}] 기어가 "
                        f"{old_gear}단에서 {player.gear}단으로 올라갑니다.")
        if upgrade_gauge:
            player.gear_gauge_upgraded = True
            logs.append(f"{player.name} 님이 기어 게이지를 5루찌에 업그레이드했습니다.")
        player.shop_visits.remove(visit)
        return logs

    def close_shop(self, pid, shop_token):
        player = self.get(pid)
        if player is None or not player.connected:
            raise GameError("플레이어를 찾을 수 없습니다.")
        if (not isinstance(shop_token, int) or isinstance(shop_token, bool)):
            raise GameError("잘못된 상점 방문입니다.")
        visit = next((visit for visit in player.shop_visits
                      if visit["token"] == shop_token), None)
        if visit is None:
            raise GameError("이용할 수 있는 상점 방문이 없습니다.")
        player.shop_visits.remove(visit)
        return []

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
            p.shop_cards = []
            p.shop_visits = []
            p.gear_gauge_upgraded = False
            p.status_effects.clear()
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
        self.pending_shop_choice = None
        self.reaction_moves = []
        self.last_move_path = []
        self.last_effect_events = []
        self.start_rolls = None
        self.item_deck = []
        self.shop_stock = dict(SHOP_CARD_COUNTS)
        self.traps = []

    def _advance_turn(self):
        ids = [p.id for p in self.players]
        i = ids.index(self.turn)
        for k in range(1, len(ids) + 1):
            p = self.players[(i + k) % len(ids)]
            if p.connected:
                self.turn = p.id
                p.status_effects.discard("angel")
                return

    def start_roll(self, pid):
        """주사위를 굴리고 분기점 선택이 필요하면 이동을 잠시 멈춘다."""
        if self.phase != "playing":
            raise GameError("게임 진행 중이 아닙니다.")
        if pid != self.turn:
            raise GameError("당신의 차례가 아닙니다.")
        if self.pending_move or self.pending_shop_choice:
            raise GameError("현재 분기 이동을 먼저 마쳐야 합니다.")
        p = self.get(pid)
        dice_count = dice_for_gear(p.gear)
        if "ufo" in p.status_effects:
            dice_count = max(1, dice_count - 1)
        if "demon_king" in p.status_effects:
            dice_count = 1
        values = [random.randint(1, 3) for _ in range(dice_count)]
        cloud_active = "cloud" in p.status_effects
        if cloud_active:
            values = [1 if value == 3 else value for value in values]
        p.status_effects.difference_update(("cloud", "demon_king", "ufo"))
        self.last_roll = (pid, values)
        self.roll_seq += 1
        self.last_effect_events = []
        self.last_move_path = []
        logs = [f"{p.name}: 주사위 {' + '.join(map(str, values))} = {sum(values)}"]
        if self._has_shop_effect(p, "optional_reroll_one_die"):
            self._set_shop_choice(
                p, "optional_reroll_one_die", values=list(values),
                cloud_active=cloud_active)
            logs.append(f"[백기사] {p.name} 님은 주사위 하나를 다시 굴릴 수 있습니다.")
            return logs
        logs.extend(self._prepare_basic_move(p, values))
        return logs

    def _set_shop_choice(self, player, kind, **details):
        self.shop_choice_seq += 1
        self.pending_shop_choice = {
            "id": self.shop_choice_seq,
            "pid": player.id,
            "kind": kind,
            **details,
        }

    def _prepare_basic_move(self, player, values):
        effects = self._shop_effects_of_type(player, "bonus_basic_move")
        bonus = sum(effect.get("amount", 0) for effect in effects)
        total = sum(values) + bonus
        logs = []
        if bonus:
            logs.append(f"[흑기사] 기본 이동 거리가 {bonus}칸 증가합니다.")
        if (total > 0
                and self._has_shop_effect(player, "optional_move_adjustment")):
            self._set_shop_choice(
                player, "optional_move_adjustment", total=total,
                values=list(values))
            logs.append(f"[렉키] {player.name} 님은 기본 이동을 1칸 줄일 수 있습니다.")
            return logs
        logs.extend(self._start_basic_move(player, total))
        return logs

    def _start_basic_move(self, player, total):
        if total == 0:
            self.last_move_path = []
            self._advance_turn()
            return [f"[렉키] {player.name} 님이 이동을 생략했습니다."]
        self.pending_move = {
            "pid": player.id, "remaining": total, "branch": None,
            "advance_turn": True,
        }
        logs = [f"{player.name} 님이 기본 이동으로 {total}칸 이동합니다."]
        logs.extend(self._continue_move())
        return logs

    def _start_item_move(self, player, dice_count):
        if "demon_king" in player.status_effects:
            dice_count = 1
            player.status_effects.remove("demon_king")
        values = [random.randint(1, 3) for _ in range(dice_count)]
        total = sum(values)
        self.last_roll = (player.id, values)
        self.roll_seq += 1
        self.last_move_path = []
        self.pending_move = {
            "pid": player.id, "remaining": total, "branch": None,
            "advance_turn": True,
        }
        logs = [f"{player.name}: 주사위 {' + '.join(map(str, values))} = {total}"]
        logs.extend(self._continue_move())
        return logs

    def resolve_shop_card_choice(self, pid, choice_id, action, die_index=None):
        choice = self.pending_shop_choice
        if (not isinstance(choice_id, int) or isinstance(choice_id, bool)
                or not isinstance(action, str)
                or not choice or choice["pid"] != pid
                or choice["id"] != choice_id):
            raise GameError("선택할 수 있는 상점 카드 효과가 없습니다.")
        player = self.get(pid)
        if player is None or not player.connected or pid != self.turn:
            raise GameError("현재 차례의 플레이어만 선택할 수 있습니다.")
        logs = []
        if choice["kind"] == "optional_reroll_one_die":
            values = list(choice["values"])
            if action == "reroll":
                if (not isinstance(die_index, int) or isinstance(die_index, bool)
                        or not 0 <= die_index < len(values)):
                    raise GameError("다시 굴릴 주사위를 선택해 주세요.")
                value = random.randint(1, 3)
                if choice["cloud_active"] and value == 3:
                    value = 1
                old_value = values[die_index]
                values[die_index] = value
                logs.append(f"[백기사] 주사위 {old_value}를 다시 굴려 {value}가 나왔습니다.")
            elif action != "keep":
                raise GameError("잘못된 주사위 선택입니다.")
            self.pending_shop_choice = None
            self.last_roll = (pid, values)
            logs.extend(self._prepare_basic_move(player, values))
            return logs

        if choice["kind"] == "optional_move_adjustment":
            if action not in {"normal", "less"}:
                raise GameError("잘못된 이동 선택입니다.")
            total = choice["total"]
            if action == "less":
                total -= 1
                logs.append(f"[렉키] {player.name} 님이 기본 이동을 1칸 줄였습니다.")
            self.pending_shop_choice = None
            logs.extend(self._start_basic_move(player, total))
            return logs
        raise GameError("지원하지 않는 상점 카드 선택입니다.")

    def _validate_missile_targets(self, player, target_pid, target_pids, multi_target):
        if target_pids is None:
            target_pids = [target_pid] if target_pid is not None else []
        if not isinstance(target_pids, list):
            raise GameError("미사일 대상을 선택해 주세요.")
        effect = next(iter(self._shop_effects_of_type(
            player, "multi_target_item_attack")), None) if multi_target else None
        minimum = effect.get("minimum_targets", 1) if effect else 1
        maximum = effect.get("maximum_targets", 1) if effect else 1
        if not minimum <= len(target_pids) <= maximum:
            raise GameError("미사일 대상은 1~2명까지 선택할 수 있습니다." if multi_target
                            else "미사일 대상을 한 명 선택해 주세요.")
        if (any(not isinstance(pid, int) or isinstance(pid, bool) for pid in target_pids)
                or len(set(target_pids)) != len(target_pids)):
            raise GameError("미사일 대상 선택이 올바르지 않습니다.")
        targets = [self.get(pid) for pid in target_pids]
        if any(not target or not target.connected
               or target.progress <= player.progress for target in targets):
            raise GameError("내 앞에 있는 플레이어만 미사일 대상으로 선택할 수 있습니다.")
        return targets

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
        if self.pending_move or self.pending_shop_choice:
            raise GameError("분기점 선택이 필요합니다. start_roll()을 사용해 주세요.")
        return logs

    def _movement_options(self, p):
        return self._movement_options_at(p.cell, p.previous_cell)

    def _movement_options_at(self, cell, previous_cell):
        options = [next_cell for next_cell in self.map.neighbor_ids(cell)
                   if next_cell != previous_cell]
        options = [next_cell for next_cell in options
                   if self.map.can_advance(cell, next_cell)] or options
        source = self.map.cells[cell]
        is_drift_source = any(effect["cell"] == cell and effect.get("type") == "drift"
                              and "to" not in effect for effect in self.map.effects)
        if is_drift_source:
            drift_targets = {self.map.cell_id(target)
                             for start, target in self.map.drift_connection_pairs
                             if start == source}
            default_options = [cell for cell in options if cell not in drift_targets]
            options = default_options or options

        if previous_cell is not None:
            previous = self.map.cells[previous_cell]
            current = self.map.cells[cell]
            drift_arrivals = set(self.map.drift_connection_pairs)
            drift_arrivals.update(
                (self.map.path[effect["cell"]], self.map.path[effect["to"]])
                for effect in self.map.effects
                if effect.get("type") == "drift" and "to" in effect)
            if (previous, current) in drift_arrivals and options:
                direction = self.map.direction_between(previous_cell, cell)
                if direction is None:
                    dx, dy = current[0] - previous[0], current[1] - previous[1]
                    if dx and not dy:
                        direction = "right" if dx > 0 else "left"
                    elif dy and not dx:
                        direction = "down" if dy > 0 else "up"
                straight = [next_cell for next_cell in options
                            if self.map.direction_between(cell, next_cell) == direction]
                if straight:
                    return straight[:1]
                reverse = self.map.direction_between(cell, previous_cell)
                away = [next_cell for next_cell in options
                        if self.map.direction_between(cell, next_cell) != reverse]
                return (away or options)[:1]
        return options

    def _forward_tiles(self, player, offsets):
        states = {(player.cell, player.previous_cell, tuple(player.forced_next_cells))}
        reached = set()
        for distance in range(1, max(offsets) + 1):
            next_states = set()
            for cell, previous_cell, forced in states:
                if forced:
                    options, remaining_forced = (forced[0],), forced[1:]
                elif cell == 0 and previous_cell is None:
                    if self.map.start_direction is not None:
                        options = (self.map.cell_id(self.map.start_direction),)
                    else:
                        adjacent = self.map.neighbor_ids(cell)
                        first = next((candidate for direction in DEFAULT_START_DIRECTION_ORDER
                                      for candidate in adjacent
                                      if self.map.direction_between(cell, candidate) == direction),
                                     None)
                        options = (first,) if first is not None else ()
                    remaining_forced = ()
                else:
                    options = self._movement_options_at(cell, previous_cell)
                    remaining_forced = ()
                for next_cell in options:
                    next_states.add((next_cell, cell, remaining_forced))
            states = next_states
            if distance in offsets:
                reached.update(cell for cell, _, _ in states)
        return reached

    def _continue_move(self):
        pending = self.pending_move
        p = self.get(pending["pid"])
        self.last_move_pid = p.id
        advance_turn = pending.get("advance_turn", True)
        before_laps = p.laps_completed
        moved = []
        logs = []
        traps_processed = False
        trap_moved = False
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
            for effect in self.map.effects_at(p.cell):
                if effect_kind(effect) == "item_box":
                    logs.extend(self._draw_item_box(p, effect))
            self._record_shop_visits_for_path(p, (p.cell,))
            if p.laps_completed >= self.laps:
                trap_logs, trap_moved, trap_path = self._trigger_traps(p)
                logs.extend(trap_logs)
                traps_processed = True
                if trap_moved:
                    moved.extend(trap_path)
                    pending["remaining"] = 0
                    break
                self._lap_logs(p, before_laps, p.laps_completed, logs)
                self._record_move(moved)
                self.phase = "finished"
                self.winner = p.id
                self.turn = None
                self.pending_move = None
                self.pending_shop_choice = None
                self.reaction_moves.clear()
                for player in self.players:
                    player.shop_visits.clear()
                logs.append(f"{p.name} 님이 {self.laps}바퀴를 완주하고 승리했습니다!")
                return logs
        self._record_move(moved)
        self._lap_logs(p, before_laps, p.laps_completed, logs)
        if pending["branch"] is not None:
            return logs
        self.pending_move = None
        if not traps_processed:
            trap_logs, trap_moved, trap_path = self._trigger_traps(p)
            logs.extend(trap_logs)
            if trap_path:
                self.last_move_path.extend(trap_path)
                self.move_seq += 1
        logs.extend(self._apply_effects(p, arrived_by_move=trap_moved))
        if p.laps_completed >= self.laps:
            self.phase = "finished"
            self.winner = p.id
            self.turn = None
            self.pending_shop_choice = None
            self.reaction_moves.clear()
            for player in self.players:
                player.shop_visits.clear()
            logs.append(f"{p.name} 님이 {self.laps}바퀴를 완주하고 승리했습니다!")
        elif advance_turn:
            self._advance_turn()
        else:
            logs.extend(self._start_reaction_moves())
        return logs

    def _record_move(self, cells):
        self.last_move_path = list(cells)
        if cells:
            self.move_seq += 1

    def _lap_logs(self, p, old, new, logs):
        """출발 타일에 재진입해 완주한 바퀴를 기록한다."""
        for lap in range(old + 1, new + 1):
            logs.append(f"{p.name} 님 {lap}바퀴 완주! (남은 바퀴 {self.laps - lap})")

    def _draw_item_box(self, p, effect):
        title = effect_title(effect)
        if len(p.items) >= self._item_capacity(p):
            return [f"[{title}] {p.name} 님의 아이템 카드 보유 한도 "
                    f"({self._item_capacity(p)}장)에 도달했습니다."]
        card = self._draw_item_card(effect.get("pool"))
        p.items.append(card)
        self.effect_seq += 1
        self.last_effect_events.append({
            "seq": self.effect_seq, "pid": p.id,
            "text": f"{title} - 아이템 카드 {card}번 획득",
            "kind": "item_card_drawn", "card_id": card, "cell": p.cell,
        })
        return [f"[{title}] {p.name} 님이 아이템 카드 {card}번을 얻었습니다."]

    def _apply_effects(self, p, visited_cells=None, arrived_by_move=False):
        logs = []
        n = self.map.length
        effect_cell = p.cell if p.cell < n else None
        if effect_cell is None:
            return logs
        if visited_cells is None:
            visited_cells = set()
        if effect_cell in visited_cells:
            return logs
        visited_cells.add(effect_cell)

        for e in self.map.effects_at(effect_cell):
            kind, title = effect_kind(e), effect_title(e)
            notice = ""
            if kind == "item_box":
                if arrived_by_move:
                    logs.extend(self._draw_item_box(p, e))
                continue
            if (kind in {"gear", "move"}
                    and self._has_shop_effect(p, "ignore_map_effects")):
                lo, hi = effect_range(e) if kind in AMOUNT_KINDS else (0, 0)
                if hi < 0:
                    logs.append(f"[몬스터] {p.name} 님은 {title} 효과를 무시했습니다.")
                    continue
            if self._block_effect(p, "effect", title, logs):
                continue
            if kind in AMOUNT_KINDS:
                lo, hi = effect_range(e)
                amount = random.randint(lo, hi)
            if (kind in {"gear", "move"} and amount < 0
                    and self._has_shop_effect(p, "ignore_map_effects")):
                logs.append(f"[몬스터] {p.name} 님은 {title} 효과를 무시했습니다.")
                continue
            if kind == "gear":
                if amount > 0:
                    multiplier = 1
                    for effect in self._shop_effects_of_type(p, "multiply_gear_increase"):
                        multiplier *= effect.get("multiplier", 1)
                    amount *= multiplier
                old = p.gear
                self._set_gear(p, old + amount)
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
                    self._record_shop_visits_for_path(p, (p.cell,))
                    p.progress = max(0, p.progress + (1 if amount > 0 else -1))
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
                self._record_shop_visits_for_path(p, (p.cell,))
                if p.cell == 0:
                    p.laps_completed += 1
                self.last_move_path.append(p.cell)
                self.move_seq += 1
                self._lap_logs(p, old_laps, p.laps_completed, logs)
                logs.append(f"{p.name}가 드리프트 성공!")
                notice = "드리프트 성공!"
            elif kind == "shop":
                logs.append(f"[{title}] {p.name} 님이 상점에 도착했습니다. (루찌 {p.luci})")
                notice = "상점 도착"
            if notice and kind != "shop":
                self.effect_seq += 1
                self.last_effect_events.append({
                    "seq": self.effect_seq, "pid": p.id,
                    "text": notice if kind == "drift" else f"{title} - {notice}"
                })
            if kind in {"move", "drift"} and p.cell != effect_cell:
                logs.extend(self._apply_effects(p, visited_cells, True))
                return logs
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
            "pending_shop_choice": (
                {**self.pending_shop_choice,
                 "values": list(self.pending_shop_choice["values"])}
                if self.pending_shop_choice else None),
            "branch_request": self.pending_move["branch"] if self.pending_move else None,
            "move_seq": self.move_seq,
            "move_pid": self.last_move_pid,
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
                "item_capacity": self._item_capacity(p),
                "shop_cards": list(p.shop_cards),
                "shop_visits": [dict(visit) for visit in p.shop_visits],
                "gear_gauge_upgraded": p.gear_gauge_upgraded,
                "status_effects": sorted(p.status_effects),
                "dice": dice_for_gear(p.gear),
            } for p in self.players],
            "shop_stock": dict(self.shop_stock),
        }
