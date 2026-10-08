"""맵 데이터 모델. 맵은 최대 11x11 격자 위의 연결된 타일 그래프로 구성된다.
상하좌우로 맞닿은 타일은 자동 연결되며 path의 0번 타일이 출발/결승선이다.

JSON 형식:
{
  "name": "기본 맵",
  "width": 4, "height": 3,
    "path": [[0,0],[1,0], ...],     # 타일 좌표 (0번 = 출발/결승선, 이후 순서는 이동 경로가 아님)
    "connections": [                 # 연결된 인접 타일 좌표 쌍 (생략 시 모든 인접 타일 자동 연결)
        [[0,0],[1,0]], [[1,0],[2,0]]
    ],
    "drift_connections": [          # 드리프트 성공 타일에서 목적지로만 이동 가능한 연결
        [[0,0],[0,1]]
    ],
    "branch_cells": [[2,1], ...],   # (자동 생성) 분기 전용 칸 좌표. 직접 수정하지 않는다
    "branches": [                   # (선택) 분기점과 분기 후 재합류까지의 경로
        {"cell": 3, "options": {
            "straight": [[4,0],[5,0],[6,0]],
            "left": [[3,1],[4,1],[6,0]],
            "right": [[3,-1],[4,-1],[6,0]]
        }}
    ],
  "effects": [                    # (선택) 칸 효과. cell 은 path 의 0부터 시작하는 인덱스
    {"cell": 3, "type": "gear", "amount": 1},       # 멈춘 칸에서 기어 +1
    {"cell": 4, "type": "n2o", "amount": 1},       # 앞으로 고정 1칸 (amount 생략 시 기본값)
    {"cell": 9, "type": "drift", "to": 2}           # 2번 칸으로 바로 이동
  ]
}

branches는 이전 맵 파일과의 호환을 위한 형식이다. branches의 cell은 path 인덱스(0부터)이며,
각 방향 경로는 분기점 다음 칸부터 공통 재합류 칸까지의
좌표 목록이다. 세 경로는 인접한 칸으로 이어져야 하며 이동 칸 수도 같아야 한다. straight는 path의
기본 진행과 일치해야 하고, 마지막 이동 방향도 재합류 지점의 원래 경로 진행 방향과 일치해야 한다.
분기점에 도착한 플레이어는 straight/left/right 중 하나를 선택한다.
branch_cells는 branches에서 사용한 좌표를 자동 저장하는 필드이며, 맵 로드 시 branches로 재구성된다.

칸 효과 (플레이어가 그 칸에 "멈췄을 때" 발동. 한 칸에 여러 개를 둘 수 있고 적은 순서대로 적용된다)

  type            설명                          파라미터
  --------------  ----------------------------  ---------------------------------------------
  gear            기어 증감                     amount (필수)  예: 1, -1, [1, 2]
  move            이동 (양수=앞, 음수=뒤)       amount (필수)  예: 3, -1, [1, 2]
  luci            루찌(돈) 증감                 amount (필수)  예: 5, [1, 3], -2
  collision       충돌: 기어 -1                 amount 로 덮어쓰기 가능
  big_collision   대형충돌: 기어 -2              amount 로 덮어쓰기 가능
    n2o             N2O: 앞으로 고정 이동         amount (선택, 기본 1). 1칸/2칸을 따로 배치
  booster         부스터 존: 앞으로 3칸         amount 로 덮어쓰기 가능
  back            뒤로 1칸                      amount 로 덮어쓰기 가능
  fall            추락: 뒤로 2칸                amount 로 덮어쓰기 가능
    drift           드리프트: 특정 칸으로 이동    to (필수) 이동할 칸 인덱스. 항상 앞으로 진행
                                                하며, 출발선을 지나면 바퀴 수가 늘어난다
    drift           드리프트                      to 생략 시 드리프트 전용 연결의 출발 타일 표시
  shop            상점                          items (선택) 판매 카드 번호 목록 (1~15)
  item_box        아이템 박스                   pool  (선택) 나올 수 있는 아이템 카드 번호 (1~17)

amount 는 정수 하나(고정값) 또는 [최소, 최대] (범위 안에서 무작위, 양끝 포함). 0이 아닌 값이어야 하며
절댓값은 9 이하. 이동 효과로 도착한 칸의 효과는 다시 발동하지 않는다(연쇄 없음).
"""
import json
import os

MAX_SIZE = 11
DEFAULT_START_DIRECTION_ORDER = ("right", "down", "left", "up")
MAPS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "maps")
DEFAULT_MAP_PATH = os.path.join(MAPS_DIR, "default_map.json")


class MapError(ValueError):
    pass


MAX_EFFECT_AMOUNT = 9
SHOP_CARD_COUNT = 15          # images/shop_card_01..15.png
ITEM_CARD_COUNT = 17          # images/item_card_01..17.png

# 프리셋 효과: type -> (실제 종류, 기본 amount)
PRESETS = {
    "collision": ("gear", -1),
    "big_collision": ("gear", -2),
    "n2o": ("move", 1),
    "booster": ("move", 3),
    "back": ("move", -1),
    "fall": ("move", -2),
}
AMOUNT_KINDS = ("gear", "move", "luci")
EFFECT_TYPES = AMOUNT_KINDS + ("drift", "shop", "item_box") + tuple(PRESETS)

TITLES = {
    "gear": "기어", "move": "이동", "luci": "루찌", "collision": "충돌", "big_collision": "대형충돌",
    "n2o": "N2O", "booster": "부스터 존", "back": "후진", "fall": "추락", "drift": "드리프트",
    "shop": "상점", "item_box": "아이템 박스",
}


def effect_kind(e):
    """프리셋을 실제 종류로 변환한다. drift without `to` marks a drift-success tile."""
    t = e.get("type")
    return PRESETS[t][0] if t in PRESETS else t


def effect_title(e):
    return TITLES.get(e.get("type"), str(e.get("type")))


def effect_range(e):
    """효과의 (최소, 최대) amount. 프리셋은 amount 가 없으면 기본값을 쓴다."""
    amount = e.get("amount", PRESETS.get(e.get("type"), (None, None))[1])
    ok = lambda v: isinstance(v, int) and not isinstance(v, bool)
    if ok(amount):
        lo = hi = amount
    elif isinstance(amount, (list, tuple)) and len(amount) == 2 and all(ok(v) for v in amount):
        lo, hi = amount
    else:
        raise MapError(f"효과의 amount 는 정수 또는 [최소, 최대] 여야 합니다: {e}")
    if lo > hi or (lo == 0 and hi == 0) or max(abs(lo), abs(hi)) > MAX_EFFECT_AMOUNT:
        raise MapError(f"효과의 amount 는 0이 아닌 값(±{MAX_EFFECT_AMOUNT} 이내, 최소<=최대)이어야 합니다: {e}")
    return lo, hi


def _fmt_range(lo, hi, unit=""):
    return f"{lo:+d}{unit}" if lo == hi else f"{lo:+d}~{hi:+d}{unit}"


def effect_label(e):
    """보드 칸에 표시할 짧은 설명."""
    kind, title = effect_kind(e), effect_title(e)
    if kind == "gear":
        desc = f"기어 {_fmt_range(*effect_range(e))}"
    elif kind == "luci":
        desc = _fmt_range(*effect_range(e))
    elif kind == "move":
        lo, hi = effect_range(e)
        if lo > 0:
            desc = f"앞으로 {lo}" if lo == hi else f"앞으로 {lo}~{hi}"
        elif hi < 0:
            if lo == hi == -2:
                return "추락 -2"
            desc = f"이동 {_fmt_range(lo, hi)}"
            if e["type"] in ("move", "back", "fall"):
                return desc
        else:
            desc = f"이동 {_fmt_range(lo, hi)}"
        if e["type"] in ("move", "back"):
            return desc
    elif kind == "drift":
        if "to" not in e:
            return title
        desc = f"→ {e['to'] + 1}번"
    else:
        return title
    return desc if e["type"] == "gear" else f"{title} {desc}"


def effect_tone(e):
    """+1: 유리한 효과, -1: 불리한 효과, 0: 중립."""
    kind = effect_kind(e)
    if kind in AMOUNT_KINDS:
        lo, hi = effect_range(e)
        return 1 if lo > 0 else -1 if hi < 0 else 0
    return 1 if kind in ("drift", "item_box") else 0


class GameMap:
    def __init__(self, name, width, height, path, effects=None, branches=None, validate=True,
                 connections=None, drift_connections=None, start_direction=None):
        self.name = str(name)
        self.width = width
        self.height = height
        self.path = [tuple(c) for c in path]
        self.effects = []
        for effect in effects or []:
            normalized = dict(effect)
            if normalized.get("type") == "drift_success":
                normalized["type"] = "drift"
                normalized.pop("to", None)
            self.effects.append(normalized)
        self.branches = [dict(b) for b in (branches or [])]
        self.connections = (None if connections is None else
                            [tuple(sorted((tuple(edge[0]), tuple(edge[1]))))
                             for edge in connections])
        self.drift_connections = [
            (tuple(edge[0]), tuple(edge[1])) for edge in (drift_connections or [])]
        self.start_direction = tuple(start_direction) if start_direction is not None else None
        if validate:
            self.validate()

    def effects_at(self, cell):
        return [e for e in self.effects if e["cell"] == cell]

    @property
    def cells(self):
        cells = list(self.path)
        for branch in self.branches:
            for direction in ("straight", "left", "right"):
                for coord in branch["options"][direction]:
                    coord = tuple(coord)
                    if coord not in cells:
                        cells.append(coord)
        return cells

    def branch_options(self, cell):
        return next((b["options"] for b in self.branches if b["cell"] == cell), None)

    def branch_route(self, cell, direction):
        options = self.branch_options(cell)
        if options is None or direction not in options:
            raise MapError(f"분기점 {cell} 에서 선택할 수 없는 방향입니다: {direction}")
        ids = {coord: i for i, coord in enumerate(self.cells)}
        return [ids[tuple(coord)] for coord in options[direction]]

    @property
    def connection_pairs(self):
        if self.connections is not None:
            return list(self.connections)
        coords = sorted(set(self.cells))
        drift_edges = {tuple(sorted(edge)) for edge in self.drift_connections}
        return [edge for edge in sorted(tuple(sorted((coord, neighbor)))
                                        for coord in coords
                                        for neighbor in ((coord[0] + 1, coord[1]),
                                                         (coord[0], coord[1] + 1))
                                        if neighbor in coords)
                if edge not in drift_edges]

    @property
    def drift_connection_pairs(self):
        return list(self.drift_connections)

    def cell_id(self, coord):
        return self.cells.index(tuple(coord))

    def neighbor_ids(self, cell):
        cells = self.cells
        x, y = cells[cell]
        by_coord = {coord: index for index, coord in enumerate(cells)}
        adjacent = {coord: set() for coord in cells}
        for first, second in self.connection_pairs:
            adjacent[first].add(second)
            adjacent[second].add(first)
        for source, target in self.drift_connection_pairs:
            adjacent[source].add(target)
        return [by_coord[coord] for coord in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y))
                if coord in adjacent[(x, y)]]

    def direction_between(self, source, target):
        x1, y1 = self.cells[source]
        x2, y2 = self.cells[target]
        return {(0, -1): "up", (1, 0): "right", (0, 1): "down", (-1, 0): "left"}.get(
            (x2 - x1, y2 - y1))

    def _validate_effect(self, e):
        if not isinstance(e.get("cell"), int) or not (0 <= e["cell"] < len(self.path)):
            raise MapError(f"효과의 cell 이 경로 범위를 벗어났습니다: {e}")
        if e.get("type") not in EFFECT_TYPES:
            raise MapError(f"지원하지 않는 효과 종류: {e.get('type')!r}")
        kind = effect_kind(e)
        if kind in AMOUNT_KINDS:
            effect_range(e)
        elif kind == "drift":
            to = e.get("to")
            if to is None:
                return
            if not isinstance(to, int) or isinstance(to, bool) or not (0 <= to < len(self.path)):
                raise MapError(f"드리프트의 to 는 경로 범위 안의 칸 번호여야 합니다: {e}")
            if to == e["cell"]:
                raise MapError(f"드리프트의 to 는 자기 칸과 달라야 합니다: {e}")
        else:
            key, count = ("items", SHOP_CARD_COUNT) if kind == "shop" else ("pool", ITEM_CARD_COUNT)
            ids = e.get(key)
            if ids is not None and (not isinstance(ids, list) or not ids or not all(
                    isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= count for v in ids)):
                raise MapError(f"{key} 는 1~{count} 범위의 카드 번호 목록이어야 합니다: {e}")

    def validate(self):
        w, h = self.width, self.height
        if not (isinstance(w, int) and isinstance(h, int)) or not (1 <= w <= MAX_SIZE and 1 <= h <= MAX_SIZE):
            raise MapError(f"맵 크기는 1~{MAX_SIZE} 범위여야 합니다.")
        if len(self.path) < 4:
            raise MapError("맵에는 최소 4개의 타일이 필요합니다.")
        if len(self.path) > w * h:
            raise MapError("경로가 맵 크기를 초과합니다.")
        seen = set()
        for c in self.path:
            if len(c) != 2 or not all(isinstance(v, int) for v in c):
                raise MapError(f"잘못된 좌표: {c}")
            x, y = c
            if not (0 <= x < w and 0 <= y < h):
                raise MapError(f"맵 범위를 벗어난 좌표: {c}")
            if c in seen:
                raise MapError(f"중복된 좌표: {c}")
            seen.add(c)
        branch_cells = set()
        for b in self.branches:
            cell = b.get("cell")
            options = b.get("options")
            if not isinstance(cell, int) or isinstance(cell, bool) or not (0 <= cell < len(self.path)):
                raise MapError(f"분기점 cell 이 경로 범위를 벗어났습니다: {b}")
            if cell in branch_cells:
                raise MapError(f"분기점이 중복되었습니다: {cell}")
            branch_cells.add(cell)
            if not isinstance(options, dict) or set(options) != {"straight", "left", "right"}:
                raise MapError(f"분기점에는 straight, left, right 경로가 모두 필요합니다: {b}")
            routes = [options[d] for d in ("straight", "left", "right")]
            if any(not isinstance(route, list) or not route for route in routes):
                raise MapError(f"각 분기 방향에는 하나 이상의 좌표가 필요합니다: {b}")
            if len({len(route) for route in routes}) != 1:
                raise MapError(f"분기 경로는 재합류까지 이동 칸 수가 같아야 합니다: {b}")
            merge = tuple(routes[0][-1])
            if merge not in self.path or any(tuple(route[-1]) != merge for route in routes):
                raise MapError(f"분기 경로는 같은 맵 경로 칸에서 재합류해야 합니다: {b}")
            straight = [self.path[(cell + i + 1) % len(self.path)] for i in range(len(routes[0]))]
            if [tuple(c) for c in routes[0]] != straight:
                raise MapError(f"straight 경로는 path 의 기본 진행 방향과 일치해야 합니다: {b}")
            first_steps = set()
            for route in routes:
                previous = self.path[cell]
                seen_route = {previous}
                for coord in route:
                    if (not isinstance(coord, (list, tuple)) or len(coord) != 2
                            or not all(isinstance(v, int) and not isinstance(v, bool) for v in coord)):
                        raise MapError(f"잘못된 분기 좌표입니다: {coord}")
                    coord = tuple(coord)
                    if not (0 <= coord[0] < w and 0 <= coord[1] < h):
                        raise MapError(f"분기 좌표가 맵 범위를 벗어났습니다: {coord}")
                    if abs(previous[0] - coord[0]) + abs(previous[1] - coord[1]) != 1:
                        raise MapError(f"분기 경로의 칸이 인접하지 않습니다: {previous} -> {coord}")
                    if coord in seen_route and coord != merge:
                        raise MapError(f"분기 경로 안에 중복 좌표가 있습니다: {coord}")
                    seen_route.add(coord)
                    previous = coord
                first_steps.add(tuple(route[0]))
            if len(first_steps) != 3:
                raise MapError(f"직진/좌/우 분기 경로는 서로 다른 칸으로 시작해야 합니다: {b}")
            merge_index = self.path.index(merge)
            previous_on_path = self.path[(merge_index - 1) % len(self.path)]
            expected_direction = (merge[0] - previous_on_path[0],
                                  merge[1] - previous_on_path[1])
            for route in routes:
                last_before_merge = tuple(route[-2]) if len(route) > 1 else self.path[cell]
                direction = (merge[0] - last_before_merge[0],
                             merge[1] - last_before_merge[1])
                if direction != expected_direction:
                    raise MapError(
                        f"분기 경로는 원래 경로의 진행 방향으로 재합류해야 합니다: {b}")
        for e in self.effects:
            self._validate_effect(e)
        cells = self.cells
        cell_ids = {coord: index for index, coord in enumerate(cells)}
        if self.start_direction is not None:
            if self.start_direction not in cell_ids:
                raise MapError("출발 방향의 도착 타일이 맵에 없습니다.")
            if self.cell_id(self.start_direction) not in self.neighbor_ids(0):
                raise MapError("출발 방향은 출발 타일과 연결된 타일이어야 합니다.")
        if self.connections is not None:
            seen_connections = set()
            for edge in self.connections:
                if len(edge) != 2:
                    raise MapError(f"연결은 두 타일 좌표로 구성되어야 합니다: {edge}")
                first, second = edge
                if first not in cell_ids or second not in cell_ids:
                    raise MapError(f"연결의 타일이 맵에 없습니다: {edge}")
                if abs(first[0] - second[0]) + abs(first[1] - second[1]) != 1:
                    raise MapError(f"연결할 타일은 상하좌우로 인접해야 합니다: {edge}")
                if edge in seen_connections:
                    raise MapError(f"중복된 타일 연결입니다: {edge}")
                seen_connections.add(edge)
        drift_sources = {self.path[e["cell"]] for e in self.effects
                 if e.get("type") == "drift" and "to" not in e}
        drift_outgoing = {source: 0 for source in drift_sources}
        seen_drift_connections = set()
        regular_edges = set(self.connection_pairs)
        for source, target in self.drift_connection_pairs:
            edge = tuple(sorted((source, target)))
            if source not in cell_ids or target not in cell_ids:
                raise MapError(f"드리프트 연결의 타일이 맵에 없습니다: {(source, target)}")
            if abs(source[0] - target[0]) + abs(source[1] - target[1]) != 1:
                raise MapError(f"드리프트 연결은 인접한 타일이어야 합니다: {(source, target)}")
            if source not in drift_sources:
                raise MapError(f"드리프트 연결 출발 타일에 드리프트 성공 효과가 없습니다: {source}")
            if edge in regular_edges:
                raise MapError(f"드리프트 전용 연결을 일반 연결과 중복할 수 없습니다: {edge}")
            if (source, target) in seen_drift_connections:
                raise MapError(f"중복된 드리프트 연결입니다: {(source, target)}")
            seen_drift_connections.add((source, target))
            drift_outgoing[source] += 1
            if drift_outgoing[source] > 1:
                raise MapError(f"드리프트 성공 타일은 하나의 방향 연결만 가질 수 있습니다: {source}")
        if any(count != 1 for count in drift_outgoing.values()):
            raise MapError("드리프트 성공 타일마다 드리프트 연결을 하나 지정해야 합니다.")
        neighbors = {index: set() for index in range(len(cells))}
        for first, second in self.connection_pairs:
            a, b = cell_ids[first], cell_ids[second]
            neighbors[a].add(b)
            neighbors[b].add(a)
        for source, target in self.drift_connection_pairs:
            a, b = cell_ids[source], cell_ids[target]
            neighbors[a].add(b)
            neighbors[b].add(a)
        if any(len(adjacent) < 2 for adjacent in neighbors.values()):
            raise MapError("모든 타일은 폐곡선을 위해 인접한 타일이 2개 이상이어야 합니다.")
        visited = set()
        pending = [0]
        while pending:
            cell = pending.pop()
            if cell in visited:
                continue
            visited.add(cell)
            pending.extend(neighbors[cell])
        if len(visited) != len(cells):
            raise MapError("모든 타일은 하나의 연결된 경로에 포함되어야 합니다.")
        pending_states = [(0, None)]
        visited_states = set()
        reachable_cells = set()
        while pending_states:
            cell, previous = pending_states.pop()
            state = (cell, previous)
            if state in visited_states:
                continue
            visited_states.add(state)
            reachable_cells.add(cell)
            if cell == 0 and previous is None:
                if self.start_direction is not None:
                    options = [self.cell_id(self.start_direction)]
                else:
                    adjacent = self.neighbor_ids(cell)
                    options = next(([neighbor] for direction in DEFAULT_START_DIRECTION_ORDER
                                    for neighbor in adjacent
                                    if self.direction_between(cell, neighbor) == direction), [])
            else:
                options = [neighbor for neighbor in self.neighbor_ids(cell) if neighbor != previous]
            if not options:
                raise MapError("드리프트 방향을 고려했을 때 되돌아가지 않고 이동할 수 없는 구간이 있습니다.")
            pending_states.extend((neighbor, cell) for neighbor in options)
        if len(reachable_cells) != len(cells):
            raise MapError("출발 타일에서 이동할 수 없는 타일이 있습니다.")

    @property
    def length(self):
        return len(self.path)

    def to_dict(self):
        return {"name": self.name, "width": self.width, "height": self.height,
                "path": [list(c) for c in self.path],
                "branch_cells": [list(c) for c in self.cells[len(self.path):]],
                "effects": [dict(e) for e in self.effects],
                "connections": [[list(a), list(b)] for a, b in self.connection_pairs],
                "drift_connections": [[list(a), list(b)]
                                      for a, b in self.drift_connection_pairs],
                "start_direction": (list(self.start_direction)
                                    if self.start_direction is not None else None),
                "branches": [{"cell": b["cell"], "options": {
                    d: [list(c) for c in b["options"][d]]
                for d in ("straight", "left", "right")}} for b in self.branches]}

    @classmethod
    def from_dict(cls, d):
        try:
            return cls(d["name"], d["width"], d["height"], d["path"],
                       d.get("effects"), d.get("branches"), connections=d.get("connections"),
                       drift_connections=d.get("drift_connections"),
                       start_direction=d.get("start_direction"))
        except (KeyError, TypeError, AttributeError) as e:
            raise MapError(f"맵 데이터 형식 오류: {e!r}")

    @classmethod
    def load(cls, filename):
        with open(filename, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def save(self, filename):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)


def default_map():
    """4x3 테두리를 도는 10칸짜리 순환 맵."""
    path = [(0, 0), (1, 0), (2, 0), (3, 0), (3, 1),
            (3, 2), (2, 2), (1, 2), (0, 2), (0, 1)]
    effects = [{"cell": c, "type": "gear", "amount": 1} for c in (2, 3, 4, 5)]
    effects.append({"cell": 7, "type": "gear", "amount": -1})
    return GameMap("기본 맵 (10칸)", 4, 3, path, effects)
