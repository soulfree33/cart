"""tkinter GUI: 시작 화면(서버/클라이언트 선택) + 게임 화면."""
import math
import os
import random
import socket
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

import errorlog
from client import NetClient
from game import (CHARACTER_NAMES, COLORS, ITEM_CARDS, MAX_LAPS,
                  MAX_NAME_LENGTH, MAX_PLAYERS, SHOP_CARDS)
from mapdata import (DEFAULT_MAP_PATH, MAPS_DIR, MAX_SIZE, GameMap, MapError,
                     SHOP_CARD_COUNT, effect_kind, effect_label, effect_range)
from protocol import DEFAULT_PORT
from server import GameServer

CANVAS = 640
POPUP_BACKGROUND = "#ffffff"
BOARD_BACKGROUND = "#2c3e50"
VICTORY_GOLD = "#ffd700"
VICTORY_ANIMATION_MS = 5000
VICTORY_FLASHES = 3
VICTORY_FLASH_INTERVAL_MS = VICTORY_ANIMATION_MS // (VICTORY_FLASHES * 2)
CARD_SLOT_HEIGHT = 170
CARD_SLOT_LABEL_HEIGHT = 20
CARD_PANEL_PADDING = 10
CARD_GROUP_GAP = 54
CARD_SLOT_GAP = 16
CARD_PANEL_HEIGHT = CARD_SLOT_HEIGHT + CARD_SLOT_LABEL_HEIGHT + CARD_PANEL_PADDING * 2
ITEM_CARD_DISPLAY_WIDTH = 300
ITEM_CARD_DISPLAY_HEIGHT = round(ITEM_CARD_DISPLAY_WIDTH * 1000 / 680)
SHOP_CARD_THUMB_HEIGHT = 84
SHOP_CARD_PREVIEW_HEIGHT = 250
ITEM_CARD_FLIGHT_MS = 800
ITEM_CARD_FRAME_MS = 25
ITEM_CARD_FLIGHT_FRAMES = ITEM_CARD_FLIGHT_MS // ITEM_CARD_FRAME_MS
ITEM_CARD_HOLD_MS = 3000
ITEM_CARDS_BY_ID = {card["id"]: card for card in ITEM_CARDS}
SHOP_CARDS_BY_ID = {card["id"]: card for card in SHOP_CARDS}
IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")

# 기어 게이지 이미지 (원본 764x634 기준 좌표). numbers: 기어 1단, 2단, ... 숫자의 중심 좌표,
# center: 부채꼴의 중심, radius: 숫자보다 안쪽(아래)에 위치하는 ▲ 마커의 중심 반지름
GAUGE_SRC_W = 764
GAUGE_SRC_H = 634
GAUGE_TARGET_W = 300    # Pillow 가 있을 때 표시 너비 (없으면 1/2 축소)
RIGHT_PANEL_BASE_WIDTH = GAUGE_TARGET_W
PLAYER_ROWS = 4         # 플레이어 목록이 항상 확보하는 줄 수
CHARACTER_FILES = ("bajji.png", "marid.png", "dijini.png", "dao.png")  # 빨강, 핑크, 노랑, 파랑
TRAP_IMAGE_FILES = {"mine": "trap_ufo_disc.png", "banana": "trap_banana_peel.png"}
STATUS_IMAGE_FILES = {
    "cloud": "status_cloud.png",
    "demon_king": "status_skull.png",
    "ufo": "status_ufo.png",
    "shield": "item_card_04.png",
    "angel": "item_card_06.png",
}
CHARACTER_BUTTON_H = 58
COLOR_MENU_BASE_H = 108
MARKER_SIZE = 44        # ▲ 크기 (원본 기준 px)
GAUGES = {
    "basic": {
        "file": "gage_basic.png", "center": (383, 402), "radius": 218,
        "numbers": [(121, 373), (146, 298), (197, 225), (265, 168), (342, 140), (426, 135)],
    },
    "up": {
        "file": "gage_up.png", "center": (382, 402), "radius": 218,
        "numbers": [(118, 373), (143, 293), (190, 214), (256, 160), (334, 132),
                    (420, 132), (500, 157), (568, 208), (622, 282), (648, 368)],
    },
}

# 주사위 애니메이션 설정
DICE_W, DICE_H, DIE_SIZE, DIE_GAP = 270, 100, 56, 10
ANIM_FRAMES = 12        # 랜덤 눈이 바뀌는 횟수
ANIM_BASE_MS = 50       # 초반 프레임 간격 (후반으로갈수록 느려짐)
ANIM_SLOW_MS = 9
ANIM_HOLD_MS = 500      # 결과를 보여주는 시간
ORDER_HOLD_MS = 900     # 선 정하기 라운드별 결과 표시 시간
ORDER_FINAL_MS = 1200   # 선공 발표 시간
MOVE_STEP_MS = 280      # 말이 한 칸 이동하는 간격

# 팝업 관련 설정
POPUP_HOLD_MS = 600    # 팝업 페이드 시작 전 대기 시간
POPUP_FADE_INTERVAL_MS = 50  # 팝업 페이드 갱신 간격
POPUP_FADE_STEPS = 8

# 주사위 눈 배치 (3x3 격자에서 (열, 행))
PIPS = {
    1: [(1, 1)],
    2: [(0, 0), (2, 2)],
    3: [(0, 0), (1, 1), (2, 2)],
}

EDITOR_EFFECTS = {
    "기어 +1": {"type": "gear", "amount": 1},
    "기어 +2": {"type": "gear", "amount": 2},
    "기어 -1": {"type": "gear", "amount": -1},
    "이동 -1": {"type": "move", "amount": -1},
    "추락": {"type": "fall"},
    "N2O +1": {"type": "n2o"},
    "N2O +2": {"type": "n2o", "amount": 2},
    "부스터 +3": {"type": "booster"},
    "루찌 +1": {"type": "luci", "amount": 1},
    "루찌 +2": {"type": "luci", "amount": 2},
    "루찌 +3": {"type": "luci", "amount": 3},
    "루찌 +4": {"type": "luci", "amount": 4},
    "루찌 +5": {"type": "luci", "amount": 5},
    "루찌 -5": {"type": "luci", "amount": -5},
    "대형충돌": {"type": "big_collision"},
    "드리프트": {"type": "drift"},
    "상점": {"type": "shop"},
    "아이템 박스": {"type": "item_box"},
}
EDITOR_TILE_KINDS = ("일반 타일", "출발 타일")


def _lighten(color, ratio=0.55):
    """'#rrggbb' 색을 흰색 쪽으로 ratio 만큼 섞어 연하게 만든다."""
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(round(v + (255 - v) * ratio) for v in (r, g, b))


_FONT_BASE = {}


def set_font_scale(k, fixed_size=None):
    """tk/ttk 위젯이 쓰는 기본 글꼴 크기를 처음 크기의 k 배로 맞춘다."""
    for name in ("TkDefaultFont", "TkTextFont", "TkFixedFont"):
        f = tkfont.nametofont(name)
        base = _FONT_BASE.setdefault(name, f.cget("size"))
        f.configure(size=fixed_size if fixed_size is not None else round(base * k) or base)


def _load_gauge_image(filename, width=GAUGE_TARGET_W):
    """게이지 이미지를 불러와 원본 대비 배율과 함께 돌려준다. 실패하면 (None, 1.0).

    Pillow 가 있으면 width 로 부드럽게 리사이즈하고, 없으면 tkinter 기본 PhotoImage 로 1/2 축소한다.
    """
    path = os.path.join(IMAGES_DIR, filename)
    try:
        try:
            from PIL import Image, ImageTk
            img = Image.open(path).convert("RGBA")
            w = width
            img = img.resize((w, round(img.height * w / img.width)), Image.LANCZOS)
            return ImageTk.PhotoImage(img), w / GAUGE_SRC_W
        except ImportError:
            photo = tk.PhotoImage(file=path).subsample(2)
            return photo, photo.width() / GAUGE_SRC_W
    except (OSError, tk.TclError):
        return None, 1.0


def _load_board_background(master):
    path = os.path.join(IMAGES_DIR, "grass.jpg")
    try:
        from PIL import Image, ImageTk
        return ImageTk.PhotoImage(Image.open(path).convert("RGB"), master=master)
    except ImportError:
        try:
            return tk.PhotoImage(file=path, master=master)
        except (OSError, tk.TclError):
            return None
    except (OSError, tk.TclError):
        return None


class LauncherFrame(ttk.Frame):
    def __init__(self, app):
        super().__init__(app, padding=16)
        self.app = app
        self.mode = tk.StringVar(value="server")
        self.name = tk.StringVar(value=socket.gethostname().strip() or "플레이어")
        self._name_edited = True
        self.name.trace_add("write", self._mark_name_edited)
        self.host = tk.StringVar(value="127.0.0.1")
        self.port = tk.StringVar(value=str(DEFAULT_PORT))
        self.map_path = tk.StringVar(value=DEFAULT_MAP_PATH)
        self.laps = tk.IntVar(value=3)

        ttk.Label(self, text="카트라이더 보드게임", font=("", 16, "bold")).grid(
            row=0, column=0, columnspan=3, pady=(0, 12))
        ttk.Radiobutton(self, text="서버로 시작 (호스트)", variable=self.mode, value="server",
                        command=self._refresh).grid(row=1, column=0, columnspan=3, sticky="w")
        ttk.Radiobutton(self, text="클라이언트로 접속", variable=self.mode, value="client",
                        command=self._refresh).grid(row=2, column=0, columnspan=3, sticky="w")

        ttk.Label(self, text="이름").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(self, textvariable=self.name, width=24).grid(row=3, column=1, columnspan=2, sticky="we")
        ttk.Label(self, text="서버 주소").grid(row=4, column=0, sticky="w", pady=4)
        self.host_entry = ttk.Entry(self, textvariable=self.host, width=24)
        self.host_entry.grid(row=4, column=1, columnspan=2, sticky="we")
        ttk.Label(self, text="포트").grid(row=5, column=0, sticky="w", pady=4)
        ttk.Entry(self, textvariable=self.port, width=24).grid(row=5, column=1, columnspan=2, sticky="we")

        # ttk.Label(self, text="맵 파일").grid(row=6, column=0, sticky="w", pady=4)
        # self.map_entry = ttk.Entry(self, textvariable=self.map_path, width=24)
        # self.map_entry.grid(row=6, column=1, sticky="we")
        # self.map_btn = ttk.Button(self, text="찾기", width=5, command=self._browse)
        # self.map_btn.grid(row=6, column=2)
        # ttk.Label(self, text="승리 바퀴 수").grid(row=7, column=0, sticky="w", pady=4)
        # self.laps_spin = ttk.Spinbox(self, from_=1, to=MAX_LAPS, textvariable=self.laps, width=6)
        # self.laps_spin.grid(row=7, column=1, sticky="w")

        ttk.Button(self, text="시작", command=self._connect).grid(
            row=8, column=0, columnspan=3, pady=(14, 0), sticky="we")
        self._refresh()

    def _refresh(self):
        server = self.mode.get() == "server"
        self.host_entry.state(["disabled"] if server else ["!disabled"])
        # for w in (self.map_entry, self.map_btn, self.laps_spin):
        #     w.state(["!disabled"] if server else ["disabled"])

    def _mark_name_edited(self, *_):
        self._name_edited = True

    def _browse(self):
        f = filedialog.askopenfilename(initialdir=MAPS_DIR, filetypes=[("맵 파일", "*.json")])
        if f:
            self.map_path.set(f)

    def _connect(self):
        server = None
        try:
            port = int(self.port.get())
            name = self.name.get().strip() or "플레이어"
            if self.mode.get() == "server":
                game_map = GameMap.load(self.map_path.get())
                server = GameServer("0.0.0.0", port, game_map, int(self.laps.get()),
                                    debug_mode=self.app.debug_mode)
                server.start()
                host = "127.0.0.1"
            else:
                host = self.host.get().strip()
            client = NetClient()
            client.connect(host, port, name, auto_name=not self._name_edited)
        except Exception as e:  # 입력/맵/네트워크 오류를 모두 사용자에게 표시
            if server:
                server.stop()
            messagebox.showerror("오류", str(e))
            return
        self.app.start_game(client, server)


class GameFrame(ttk.Frame):
    def __init__(self, app, client, server):
        super().__init__(app, padding=8)
        self.app, self.client, self.server = app, client, server
        self.debug_mode = app.debug_mode
        self.pid = None
        self.state = None
        self.animating = False
        self.shown_seq = None        # 화면에 반영한 마지막 roll_seq
        self.shown_move_seq = 0      # 화면에 반영한 마지막 이동 구간
        self.shown_start_seq = None  # 화면에 반영한 마지막 start_seq
        self.pending_logs = []       # 다음 state 와 함께 표시할 로그 (애니메이션 중 결과 노출 방지)
        self.branch_dialog = None
        self.branch_prompt_key = None
        self.popup_queue = []
        self.popup_active = False
        self.popup_items = ()
        self.popup_mode = None
        self.popup_text = ""
        self.popup_color = "#ffffff"
        self.popup_after = None
        self.item_card_queue = []
        self.item_animation_sources = {}
        self.item_animation_uses_pillow = None
        self.item_card_animation_id = None
        self.item_card_animation_image = None
        self.item_card_hold_after = None
        self.item_card_hold_bind_id = None
        self.item_card_hitboxes = []
        self.hovered_item_index = None
        self.item_popup = None
        self.item_popup_image = None
        self.item_popup_card_id = None
        self.shop_effect_dialog = None
        self.shop_effect_dialog_id = None
        self.shop_queue = []
        self.shop_popup = None
        self.shop_popup_token = None
        self.shop_available_cards = set()
        self.shop_card_images = {}
        self.shop_preview_image = None
        self.shop_preview_label = None
        self.shop_description_label = None
        self.shop_card_buttons = {}
        self.shop_selected_card_id = None
        self.shop_upgrade_selected = False
        self.shop_purchase_pending = False
        self.shop_balance_label = None
        self.shop_remaining_label = None
        self.shop_upgrade_button = None
        self.shop_buy_button = None
        self.debug_teleport_armed = False
        self.board_geometry = None
        self.victory_popup_key = None
        self.turn_popup_key = None
        self.last_popup_effect_seq = 0
        self.edit_mode = False
        self.editor_map = None
        self.editor_widgets = []
        self.selected_editor_cell = None
        self.editor_grid_geometry = None
        self.hover_editor_edge = None
        self._sash_clamp_pending = False
        self.k = 1.0                 # 현재 확대 배율 (창 크기 / 최소 창 크기)
        self.base = None             # 배율 1.0 일 때의 프레임 요청 크기 (= 최소 창 크기)
        self._scale_job = None
        self._last_override = {}

        self.panes = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        self.panes.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.board_area = ttk.Frame(self.panes)
        self.board_area.rowconfigure(0, weight=1)
        self.board_area.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(self.board_area, width=CANVAS, height=CANVAS,
                    bg=BOARD_BACKGROUND, highlightthickness=0)
        self.board_background_image = _load_board_background(self)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Button-1>", self._on_editor_canvas_click)
        self.canvas.bind("<Motion>", self._on_editor_canvas_motion)
        self.canvas.bind("<Leave>", self._on_editor_canvas_leave)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.card_slots_canvas = tk.Canvas(self.board_area, width=CANVAS,
                          height=CARD_PANEL_HEIGHT,
                          bg=BOARD_BACKGROUND, highlightthickness=0)
        self.card_slots_canvas.grid(row=1, column=0, sticky="ew")
        self.card_slots_canvas.bind("<Motion>", self._on_card_slots_motion)
        self.card_slots_canvas.bind("<Leave>", self._on_card_slots_leave)
        self.card_slots_canvas.bind("<Button-1>", self._on_card_slots_click)
        self.panes.add(self.board_area, weight=1)

        self.right_panel = ttk.Frame(self.panes)
        self.right_panel.columnconfigure(0, weight=1)
        self.right_panel.rowconfigure(1, weight=1)
        self.panes.add(self.right_panel, weight=0)
        self.panes.bind("<B1-Motion>", self._schedule_right_panel_sash_clamp, add="+")

        side = ttk.Frame(self.right_panel, padding=0)
        side.grid(row=0, column=0, sticky="new")
        self.info = tk.Label(side, text="", font=self._font(11, True), wraplength=260,
                             height=2, anchor="nw", justify="left")
        self.info.pack(anchor="w")
        self.status = tk.Label(side, text="", wraplength=260, height=2, anchor="nw", justify="left")
        self.status.pack(anchor="w", pady=(4, 8))
        # 플레이어 목록 / 색상 메뉴: 같은 칸에 높이를 확보하는 spacer 를 겹쳐 내용이 바뀌어도 창 크기가 일정하게 한다
        pwrap = ttk.Frame(side)
        pwrap.pack(anchor="w", fill="x")
        pwrap.columnconfigure(0, weight=1)
        self.players_spacer = ttk.Frame(pwrap, width=1)
        self.players_spacer.grid(row=0, column=0)
        self.players_box = ttk.LabelFrame(pwrap, text="순서", padding=0)
        self.players_box.grid(row=0, column=0, sticky="ew")
        cwrap = ttk.Frame(side)
        cwrap.pack(anchor="w", fill="x")
        self.color_wrap = cwrap
        self.color_spacer = ttk.Frame(cwrap, width=1)
        self.color_spacer.grid(row=0, column=0)
        self.color_box = ttk.Frame(cwrap)     # 대기실에서만 내용이 채워지는 색상 선택 메뉴
        self.color_box.grid(row=0, column=0, sticky="nw")
        self.gauge_images = {}       # 게이지 종류 -> (PhotoImage, scale)  (GC 방지를 겸한 캐시)
        self.character_images = {}   # (색상 슬롯, 높이) -> PhotoImage
        self.trap_images = {}        # (함정 종류, 크기) -> PhotoImage
        self.status_images = {}      # (효과 이름, 크기) -> PhotoImage
        self.item_card_images = {}   # (카드 번호, 크기) -> PhotoImage
        self.gauge_name = None
        gw = GAUGE_TARGET_W
        self.gauge_canvas = tk.Canvas(side, highlightthickness=0, width=gw,
                                      height=round(gw * GAUGE_SRC_H / GAUGE_SRC_W))
        self.gauge_canvas.pack(pady=(8, 0))
        self.dice_canvas = tk.Canvas(side, width=DICE_W, height=DICE_H, highlightthickness=0)
        self.dice_canvas.pack(pady=8)
        self.roll_btn = ttk.Button(side, text="주사위 굴리기", command=self._roll, state="disabled")
        self.roll_btn.pack(fill="x")

        if server:
            host = ttk.LabelFrame(side, text="게임 설정", padding=6)
            host.pack(fill="x", pady=(12, 0))
            self.laps = tk.IntVar(value=server.game.laps)
            row = ttk.Frame(host)
            row.pack(fill="x")
            ttk.Label(row, text="바퀴 수").pack(side="left")
            ttk.Spinbox(row, from_=1, to=MAX_LAPS, textvariable=self.laps, width=5).pack(side="left", padx=4)
            ttk.Button(row, text="적용", width=5, command=self._apply_laps).pack(side="left")
            map_row = ttk.Frame(host)
            map_row.pack(fill="x", pady=2)
            self.map_select_btn = ttk.Button(map_row, text="맵 선택...", command=self._choose_map)
            self.map_select_btn.pack(side="left", fill="x", expand=True)
            self.edit_map_btn = ttk.Button(map_row, text="맵 수정", command=self._edit_map)
            self.edit_map_btn.pack(side="left", padx=(3, 0))
            self.save_map_btn = ttk.Button(map_row, text="맵 저장...", command=self._save_map)
            self.save_map_btn.pack(side="left", padx=(3, 0))
            self.start_btn = ttk.Button(host, text="게임 시작", command=self._start)
            self.start_btn.pack(fill="x", pady=2)
            ttk.Button(host, text="대기실로 (다시 하기)", command=lambda: self._host_call(server.reset_game)
                       ).pack(fill="x", pady=2)

        self.log = tk.Text(self.right_panel, width=35, height=10, state="disabled", wrap="word")
        self.log.grid(row=1, column=0, sticky="nsew", padx=10, pady=(8, 0))
        self.bind("<Configure>", self._on_configure)
        self._apply_scale(1.0)
        self.after(100, self._poll)

    # ---- 창 크기에 따른 확대 ----
    def _font(self, size, bold=False):
        s = 10 if self.edit_mode else max(1, round(size * self.k))
        return ("", s, "bold") if bold else ("", s)

    def set_base(self):
        """현재(배율 1.0) 요청 크기를 기준 크기로 저장한다. 최소 창 크기로도 쓰인다."""
        self.base = (self.winfo_reqwidth(), self.winfo_reqheight())
        return self.base

    def _on_configure(self, e):
        if e.widget is not self or self.base is None:
            return
        if self._scale_job:
            self.after_cancel(self._scale_job)
        self._scale_job = self.after(80, self._rescale)

    def _rescale(self):
        self._scale_job = None
        k = min(self.winfo_width() / self.base[0], self.winfo_height() / self.base[1])
        k = max(1.0, int(k * 20) / 20)       # 0.05 단위로 내림 (불필요한 재계산 방지)
        if k != self.k:
            self._apply_scale(k)
        self._schedule_right_panel_sash_clamp(None)

    def _apply_scale(self, k):
        self.k = k
        set_font_scale(k, fixed_size=10 if self.edit_mode else None)
        self.info.config(font=self._font(11, True), wraplength=round(260 * k))
        self.status.config(wraplength=round(260 * k))
        # 실제 위젯 크기를 재서 목록/메뉴가 차지할 높이를 미리 확보한다
        probe = tk.Label(self, text="X", font=self._font(11, True))
        row_h = probe.winfo_reqheight()
        probe.destroy()
        self.players_spacer.config(height=PLAYER_ROWS * row_h,
                                   width=round((RIGHT_PANEL_BASE_WIDTH - 20) * k))
        self.color_spacer.config(height=round(COLOR_MENU_BASE_H * k))
        self.dice_canvas.config(width=round(DICE_W * k), height=round(DICE_H * k))
        self.card_slots_canvas.config(height=round(CARD_PANEL_HEIGHT * k))
        self._draw_card_slots(self.state)
        w = round(GAUGE_TARGET_W * k)
        self.gauge_canvas.config(width=w, height=round(w * GAUGE_SRC_H / GAUGE_SRC_W))
        self.gauge_images.clear()            # 새 크기로 다시 불러온다
        self.character_images.clear()
        self.gauge_name = None
        self._schedule_right_panel_sash_clamp(None)
        if self.state:
            self._render()

    def _schedule_right_panel_sash_clamp(self, _event):
        if not self._sash_clamp_pending:
            self._sash_clamp_pending = True
            self.after_idle(self._clamp_right_panel_sash)

    def _clamp_right_panel_sash(self):
        self._sash_clamp_pending = False
        total_width = self.panes.winfo_width()
        panel_width = self.right_panel.winfo_width()
        if total_width <= 1 or panel_width <= 1:
            return
        minimum_panel_width = round(GAUGE_TARGET_W * self.k)
        if panel_width < minimum_panel_width:
            sash_position = self.panes.sashpos(0)
            self.panes.sashpos(0, max(0, sash_position - (minimum_panel_width - panel_width)))

    def _on_canvas_configure(self, _e):
        if self.state:
            if self.edit_mode:
                self._render()
            else:
                self._draw_board(self.state, self._last_override)

    # ---- 호스트 조작 ----
    def _host_call(self, fn, *args):
        try:
            fn(*args)
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def _apply_laps(self):
        try:
            laps = int(self.laps.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("오류", "바퀴 수는 숫자여야 합니다.")
            return
        self._host_call(self.server.set_laps, laps)

    def _choose_map(self):
        f = filedialog.askopenfilename(initialdir=MAPS_DIR, filetypes=[("맵 파일", "*.json")])
        if not f:
            return
        try:
            gm = GameMap.load(f)
        except Exception as e:
            messagebox.showerror("맵 오류", str(e))
            return
        self._host_call(self.server.set_map, gm)

    def _edit_map(self):
        if self.edit_mode:
            self._finish_map_edit()
            return
        if not self.state or self.state["phase"] != "lobby":
            return

        current = self.server.game.map
        cells = current.cells
        min_width = max(x for x, _ in cells) + 1
        min_height = max(y for _, y in cells) + 1
        dialog = tk.Toplevel(self)
        dialog.title("맵 크기 설정")
        dialog.transient(self.winfo_toplevel())
        dialog.resizable(False, False)
        ttk.Label(dialog, text="맵 크기").grid(row=0, column=0, columnspan=2, padx=12, pady=(12, 6))
        ttk.Label(dialog, text="가로").grid(row=1, column=0, padx=(12, 6), pady=4, sticky="e")
        width = ttk.Combobox(dialog, state="readonly", width=6,
                             values=tuple(range(min_width, MAX_SIZE + 1)))
        width.set(current.width)
        width.grid(row=1, column=1, padx=(0, 12), pady=4, sticky="w")
        ttk.Label(dialog, text="세로").grid(row=2, column=0, padx=(12, 6), pady=4, sticky="e")
        height = ttk.Combobox(dialog, state="readonly", width=6,
                              values=tuple(range(min_height, MAX_SIZE + 1)))
        height.set(current.height)
        height.grid(row=2, column=1, padx=(0, 12), pady=4, sticky="w")

        def confirm():
            try:
                resized = GameMap(current.name, int(width.get()), int(height.get()), current.path,
                                  current.effects, current.branches,
                                  connections=current.connection_pairs,
                                  drift_connections=current.drift_connection_pairs,
                                  start_direction=current.start_direction)
                coords = resized.cells
                coord_ids = {coord: index for index, coord in enumerate(coords)}
                effects = []
                for effect in resized.effects:
                    updated = dict(effect)
                    updated["cell"] = coord_ids[resized.path[effect["cell"]]]
                    if effect.get("type") == "drift" and "to" in effect:
                        updated["to"] = coord_ids[resized.path[effect["to"]]]
                    effects.append(updated)
                resized = GameMap(resized.name, resized.width, resized.height, coords,
                                  effects, validate=False,
                                  connections=resized.connection_pairs,
                                  drift_connections=resized.drift_connection_pairs,
                                  start_direction=resized.start_direction)
            except (ValueError, MapError) as e:
                messagebox.showerror("맵 크기 오류", str(e), parent=dialog)
                return
            self.editor_map = resized
            self.edit_mode = True
            set_font_scale(self.k, fixed_size=10)
            self.selected_editor_cell = 0
            dialog.grab_release()
            dialog.destroy()
            self._render()

        actions = ttk.Frame(dialog)
        actions.grid(row=3, column=0, columnspan=2, padx=12, pady=12, sticky="e")
        ttk.Button(actions, text="취소", command=dialog.destroy).pack(side="right", padx=(4, 0))
        ttk.Button(actions, text="확인", command=confirm).pack(side="right")
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.grab_set()
        width.focus_set()

    def _finish_map_edit(self):
        if not self.editor_map:
            return
        try:
            self.editor_map.validate()
            self.server.set_map(self.editor_map)
        except Exception as e:
            messagebox.showerror("맵 적용 오류", str(e))
            return
        self.edit_mode = False
        self.editor_map = None
        set_font_scale(self.k)
        self._apply_state(self.server.game.snapshot())

    def _save_map(self):
        game_map = self.editor_map if self.edit_mode else self.server.game.map
        filename = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(), initialdir=MAPS_DIR,
            initialfile=f"{game_map.name}.json", defaultextension=".json",
            filetypes=[("맵 파일", "*.json")])
        if not filename:
            return
        try:
            game_map.validate()
            game_map.save(filename)
            self.server.set_map(game_map)
        except Exception as e:
            messagebox.showerror("맵 저장 오류", str(e))
            return
        self._apply_state(self.server.game.snapshot())

    def _clear_editor_widgets(self):
        for widget in self.editor_widgets:
            widget.destroy()
        self.editor_widgets.clear()

    def _editor_effect_choice(self, cell):
        effects = [effect for effect in self.editor_map.effects if effect["cell"] == cell]
        if not effects:
            return "없음"
        effect = effects[0]
        kind = effect_kind(effect)
        for label, template in EDITOR_EFFECTS.items():
            if kind != effect_kind(template):
                continue
            if kind in ("gear", "move", "luci"):
                if effect_range(effect) != effect_range(template):
                    continue
            elif effect.get("type") != template.get("type"):
                continue
            return label
        return f"기존 효과: {effect_label(effect)}"

    def _set_editor_effect(self, cell, choice):
        if not self.editor_map or choice.startswith("기존 효과:"):
            return
        current = self.editor_map
        effects = [dict(effect) for effect in current.effects if effect["cell"] != cell]
        source = current.path[cell]
        removing_drift = (any(effect["cell"] == cell and effect["type"] == "drift"
                              and "to" not in effect
                              for effect in current.effects)
                          and choice != "드리프트")
        drift_connections = [edge for edge in current.drift_connection_pairs
                             if not (removing_drift and edge[0] == source)]
        start_direction = current.start_direction
        if (removing_drift and current.path[0] == source
                and start_direction is not None and (source, start_direction) in current.drift_connection_pairs):
            start_direction = None
        template = EDITOR_EFFECTS.get(choice)
        if template:
            effect = dict(template)
            effect["cell"] = cell
            effects.append(effect)
        if choice == "드리프트":
            self.selected_editor_cell = cell
        self.editor_map = GameMap(current.name, current.width, current.height, current.path,
                                  effects, validate=False,
                                  connections=current.connection_pairs,
                                  drift_connections=drift_connections,
                                  start_direction=start_direction)
        self._render()
        if choice == "드리프트":
            messagebox.showinfo(
                "드리프트 방향 설정",
                "드리프트 타일과 연결할 인접한 변을 클릭하세요.\n"
                "다른 변을 선택하면 드리프트 방향이 변경됩니다.",
                parent=self.winfo_toplevel())

    def _replace_editor_tiles(self, coords):
        if not self.editor_map:
            return
        current = self.editor_map
        coord_ids = {tuple(coord): index for index, coord in enumerate(coords)}
        new_coords = set(coord_ids)
        old_coords = set(current.path)
        connections = {edge for edge in current.connection_pairs
                       if edge[0] in new_coords and edge[1] in new_coords}
        drift_connections = [edge for edge in current.drift_connection_pairs
                     if edge[0] in new_coords and edge[1] in new_coords]
        start_direction = current.start_direction
        if (not coords or coords[0] != current.path[0] or start_direction is None
            or start_direction not in new_coords
            or ((coords[0], start_direction) not in drift_connections
                and tuple(sorted((coords[0], start_direction))) not in connections)):
            start_direction = None
        for coord in new_coords - old_coords:
            for neighbor in new_coords:
                if abs(coord[0] - neighbor[0]) + abs(coord[1] - neighbor[1]) == 1:
                    connections.add(tuple(sorted((coord, neighbor))))
        effects = []
        for effect in current.effects:
            coord = current.path[effect["cell"]]
            if coord not in coord_ids:
                continue
            updated = dict(effect)
            updated["cell"] = coord_ids[coord]
            if effect.get("type") == "drift" and "to" in effect:
                target = current.path[effect["to"]]
                if target not in coord_ids:
                    continue
                updated["to"] = coord_ids[target]
            effects.append(updated)
        self.editor_map = GameMap(current.name, current.width, current.height, coords,
                                  effects, validate=False, connections=sorted(connections),
                                  drift_connections=drift_connections,
                                  start_direction=start_direction)
        self.selected_editor_cell = min(self.selected_editor_cell or 0, len(coords) - 1) if coords else None
        self._render()

    def _on_editor_canvas_click(self, event):
        if self._handle_debug_teleport_click(event):
            return
        if not self.edit_mode or not self.editor_map or not self.editor_grid_geometry:
            return
        edge = self._editor_edge_at(event.x, event.y)
        if edge is not None:
            self._toggle_editor_connection(edge)
            return
        size, ox, oy = self.editor_grid_geometry
        x, y = int((event.x - ox) // size), int((event.y - oy) // size)
        if not (0 <= x < self.editor_map.width and 0 <= y < self.editor_map.height):
            return
        coord = (x, y)
        if coord in self.editor_map.path:
            self.selected_editor_cell = self.editor_map.path.index(coord)
            self._render()
            return
        if len(self.editor_map.path) >= self.editor_map.width * self.editor_map.height:
            return
        self.selected_editor_cell = len(self.editor_map.path)
        self._replace_editor_tiles([*self.editor_map.path, coord])

    def _handle_debug_teleport_click(self, event):
        if (not self.debug_mode or not self.state
                or self.state.get("phase") != "playing" or self.edit_mode):
            return False
        if (self.animating or self.popup_active or self.popup_queue
                or self.shop_popup or self.shop_queue):
            return True
        player = next((p for p in self.state["players"] if p["id"] == self.pid), None)
        if not player or not self.board_geometry:
            return False
        cells, size, ox, oy = self.board_geometry
        cell_x, cell_y = cells[player["cell"]]
        token_x = ox + cell_x * size + size / 2
        token_y = oy + cell_y * size + size / 2
        token_x += (-1 if player["slot"] % 2 == 0 else 1) * size * 0.2
        token_y += (-1 if player["slot"] < 2 else 1) * size * 0.2
        hit_radius = max(14, size * 0.24)
        if (event.x - token_x) ** 2 + (event.y - token_y) ** 2 <= hit_radius ** 2:
            self.debug_teleport_armed = not self.debug_teleport_armed
            if self.debug_teleport_armed:
                self._log("! 내 말을 선택했습니다. 이동할 맵 타일을 클릭하세요.")
            else:
                self._log("! 디버그 이동 선택을 취소했습니다.")
            self._render()
            return True
        if not self.debug_teleport_armed:
            return False

        cell_id = next((index for index, (x, y) in enumerate(cells)
                        if ox + x * size <= event.x < ox + (x + 1) * size
                        and oy + y * size <= event.y < oy + (y + 1) * size), None)
        if cell_id is None:
            return True
        try:
            self.client.debug_teleport(cell_id)
        except OSError as error:
            self._log(f"! 디버그 이동 요청 오류: {error}")
            return True
        self.debug_teleport_armed = False
        self._render()
        return True

    def _editor_edge_at(self, x, y):
        if not self.edit_mode or not self.editor_map or not self.editor_grid_geometry:
            return None
        size, ox, oy = self.editor_grid_geometry
        coords = set(self.editor_map.path)
        tolerance = max(4, min(10, size * 0.24))
        candidates = []
        for cell_x, cell_y in coords:
            coord = (cell_x, cell_y)
            right = (cell_x + 1, cell_y)
            if right in coords:
                distance = abs(x - (ox + (cell_x + 1) * size))
                if distance <= tolerance and oy + cell_y * size <= y <= oy + (cell_y + 1) * size:
                    candidates.append((distance, tuple(sorted((coord, right)))))
            below = (cell_x, cell_y + 1)
            if below in coords:
                distance = abs(y - (oy + (cell_y + 1) * size))
                if distance <= tolerance and ox + cell_x * size <= x <= ox + (cell_x + 1) * size:
                    candidates.append((distance, tuple(sorted((coord, below)))))
        return min(candidates, default=(None, None))[1]

    def _on_editor_canvas_motion(self, event):
        edge = self._editor_edge_at(event.x, event.y)
        if edge != self.hover_editor_edge:
            self.hover_editor_edge = edge
            self._draw_editor_edge_hover()

    def _on_editor_canvas_leave(self, _event):
        self.hover_editor_edge = None
        self.canvas.delete("editor-edge-hover")

    def _toggle_editor_connection(self, edge):
        current = self.editor_map
        connections = set(current.connection_pairs)
        drift_connections = set(current.drift_connection_pairs)
        start_direction = current.start_direction
        source_index = self.selected_editor_cell
        source = (current.path[source_index]
                  if source_index is not None and 0 <= source_index < len(current.path)
                  else None)
        drift_selected = (source is not None and any(
            effect["cell"] == source_index and effect["type"] == "drift"
            and "to" not in effect
            for effect in current.effects))
        if drift_selected and source in edge:
            target = edge[1] if edge[0] == source else edge[0]
            directed_edge = (source, target)
            if directed_edge in drift_connections:
                drift_connections.remove(directed_edge)
                if source_index == 0 and start_direction == target:
                    start_direction = None
            else:
                drift_connections = {drift_edge for drift_edge in drift_connections
                                     if drift_edge[0] != source}
                drift_connections.add(directed_edge)
                connections.discard(edge)
                if source_index == 0:
                    start_direction = target
                elif (start_direction is not None and directed_edge[0] != current.path[0]
                      and tuple(sorted((current.path[0], start_direction))) == edge):
                    start_direction = None
        elif source_index == 0 and source in edge:
            target = edge[1] if edge[0] == source else edge[0]
            if edge not in connections:
                connections.add(edge)
                drift_connections.discard((target, source))
            start_direction = target
        else:
            if edge in connections:
                connections.remove(edge)
                if (start_direction is not None
                        and tuple(sorted((current.path[0], start_direction))) == edge):
                    start_direction = None
            else:
                connections.add(edge)
                drift_connections = {drift_edge for drift_edge in drift_connections
                                     if tuple(sorted(drift_edge)) != edge}
        self.editor_map = GameMap(current.name, current.width, current.height, current.path,
                                  current.effects, validate=False,
                                  connections=sorted(connections),
                                  drift_connections=sorted(drift_connections),
                                  start_direction=start_direction)
        self._render()

    def _draw_editor_edge_hover(self):
        self.canvas.delete("editor-edge-hover")
        if (not self.edit_mode or not self.editor_map or not self.hover_editor_edge
                or not self.editor_grid_geometry):
            return
        size, ox, oy = self.editor_grid_geometry
        (ax, ay), (bx, by) = self.hover_editor_edge
        if abs(ax - bx) == 1:
            x = ox + max(ax, bx) * size
            y0 = oy + ay * size
            points = ((x - 3, y0 + 2, x - 3, y0 + size - 2),
                      (x + 3, y0 + 2, x + 3, y0 + size - 2))
        else:
            y = oy + max(ay, by) * size
            x0 = ox + ax * size
            points = ((x0 + 2, y - 3, x0 + size - 2, y - 3),
                      (x0 + 2, y + 3, x0 + size - 2, y + 3))
        for line in points:
            self.canvas.create_line(*line, fill="#00d9ff", width=max(4, size // 12),
                                    tags=("editor-edge-hover",))

    def _set_editor_start(self, cell, choice):
        if not self.editor_map:
            return
        if choice != "출발 타일" or not 0 <= cell < len(self.editor_map.path):
            return
        coords = self.editor_map.path
        self.selected_editor_cell = 0
        if cell != 0:
            self._replace_editor_tiles([coords[cell], *coords[:cell], *coords[cell + 1:]])
        else:
            self._render()

    def _delete_editor_tile(self, cell):
        if not self.editor_map or not 0 <= cell < len(self.editor_map.path):
            return
        if len(self.editor_map.path) <= 1:
            return
        coords = self.editor_map.path[:cell] + self.editor_map.path[cell + 1:]
        self._replace_editor_tiles(coords)

    def _start(self):
        self._host_call(self.server.start_game)

    # ---- 수신 처리 ----
    def _choose_color(self, slot):
        try:
            self.client.choose_color(slot)
        except OSError:
            pass

    def _choose_branch(self, dialog, direction):
        self.branch_prompt_key = None
        self.branch_dialog = None
        dialog.destroy()
        try:
            self.client.choose_branch(direction)
        except OSError:
            pass

    def _show_branch_prompt(self, s):
        if (self.popup_active or self.popup_queue or self.shop_popup
                or s.get("pending_shop_choice")):
            return
        request = s.get("branch_request")
        if not request or request["pid"] != self.pid:
            self.branch_prompt_key = None
            return
        key = (s["roll_seq"], s.get("move_seq", 0), request["cell"])
        if key == self.branch_prompt_key:
            return
        self.branch_prompt_key = key
        dialog = tk.Toplevel(self)
        self.branch_dialog = dialog
        dialog.title("이동 경로 선택")
        dialog.transient(self.winfo_toplevel())
        dialog.resizable(False, False)
        ttk.Label(dialog, text="분기점입니다. 어느 방향으로 이동할까요?").pack(padx=16, pady=(14, 8))
        row = ttk.Frame(dialog)
        row.pack(padx=12, pady=(0, 12))
        for direction, label in (("up", "위"), ("right", "오른쪽"),
                     ("down", "아래"), ("left", "왼쪽")):
            if direction in request["choices"]:
                ttk.Button(row, text=label,
                           command=lambda d=direction: self._choose_branch(dialog, d)).pack(side="left", padx=4)
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        dialog.grab_set()

    def _roll(self):
        self.roll_btn.config(state="disabled")   # 중복 클릭 방지 (다음 state 로 갱신됨)
        try:
            self.client.roll()
        except OSError:
            pass

    def _poll(self):
        try:
            if not self._process_inbox():
                return
        except Exception:
            errorlog.record("메시지 처리 오류")
            self.animating = False
            self._log("! 화면 갱신 중 오류가 발생했습니다. error.log 를 확인해 주세요.")
        self.after(100, self._poll)

    def _process_inbox(self):
        """대기 중인 서버 메시지를 처리한다. 연결이 끊겨 화면을 떠나면 False."""
        while not self.animating and not self.client.inbox.empty():
            msg = self.client.inbox.get()
            kind = msg.get("type")
            if kind == "welcome":
                self.pid = msg["pid"]
            elif kind == "state":
                lr = msg["last_roll"]
                if (msg["start_rolls"] and self.shown_start_seq is not None
                        and msg["start_seq"] != self.shown_start_seq):
                    self._start_order_animation(msg)
                elif lr and self.shown_seq is not None and msg["roll_seq"] != self.shown_seq:
                    self._start_roll_animation(msg)
                elif msg.get("move_path") and msg.get("move_seq", 0) != self.shown_move_seq:
                    self._start_move_animation(msg)
                else:
                    self._apply_state(msg)
            elif kind == "log":
                self.pending_logs.append(msg["text"])
            elif kind == "error":
                self._log("! " + msg["text"])
                if self.shop_popup:
                    self.shop_purchase_pending = False
                    self._refresh_shop_popup()
                if self.state:
                    self._render()       # 버튼 상태 복구
            elif kind == "closed":
                messagebox.showinfo("연결 종료", "서버와의 연결이 끊어졌습니다.")
                self.app.show_launcher()
                return False
        return True

    def _apply_state(self, s):
        self.state = s
        if self.shop_popup_token is not None:
            player = next((p for p in s["players"] if p["id"] == self.pid), None)
            active_tokens = {visit["token"] for visit in player.get("shop_visits", [])} if player else set()
            if self.shop_popup_token not in active_tokens:
                self._close_shop_popup(send_close=False, resume=False)
            else:
                self.shop_purchase_pending = False
                self._refresh_shop_popup()
        if (self.shop_effect_dialog and self.shop_effect_dialog.winfo_exists()
                and (not s.get("pending_shop_choice")
                     or s["pending_shop_choice"]["id"] != self.shop_effect_dialog_id)):
            self.shop_effect_dialog.destroy()
            self.shop_effect_dialog = None
            self.shop_effect_dialog_id = None
        if self.item_popup and not self._can_select_item_card():
            self._close_item_card_popup(self.item_popup, resume=False)
        self._last_override = {}
        self.shown_seq = s["roll_seq"]
        self.shown_move_seq = s.get("move_seq", self.shown_move_seq)
        self.shown_start_seq = s["start_seq"]
        self._queue_state_popups(s)
        for line in self.pending_logs:
            self._log(line)
        self.pending_logs.clear()
        self._draw_card_slots(s)
        self._render()
        if self.item_card_queue:
            self.animating = True
            self._show_next_item_card_animation()
        else:
            self._show_next_popup()
            self._show_branch_prompt(s)

    def _item_animation_source(self, card_id):
        if card_id not in self.item_animation_sources:
            if self.item_animation_uses_pillow is None:
                try:
                    from PIL import Image
                    self.item_animation_uses_pillow = True
                except ImportError:
                    self.item_animation_uses_pillow = False
            front_path = os.path.join(IMAGES_DIR, f"item_card_{card_id:02d}.png")
            back_path = os.path.join(IMAGES_DIR, "item_card_back.png")
            try:
                if self.item_animation_uses_pillow:
                    from PIL import Image
                    with Image.open(front_path) as front_file:
                        front = front_file.convert("RGBA")
                    with Image.open(back_path) as back_file:
                        back = back_file.convert("RGBA")
                else:
                    front = tk.PhotoImage(file=front_path, master=self)
                    back = tk.PhotoImage(file=back_path, master=self)
                self.item_animation_sources[card_id] = (front, back)
            except (OSError, tk.TclError) as error:
                self._log(f"! 아이템 카드 애니메이션 이미지를 불러오지 못했습니다: {error}")
                self.item_animation_sources[card_id] = None
        return self.item_animation_sources[card_id]

    def _item_card_frame_image(self, source, card_height, progress, angle):
        cosine = math.cos(angle)
        face = source[0] if cosine >= 0 else source[1]
        scale = 0.2 + 0.8 * progress
        width_factor = max(0.035, abs(cosine))
        if self.item_animation_uses_pillow:
            from PIL import Image, ImageTk
            width = max(1, round(source[0].width * card_height / source[0].height
                                 * scale * width_factor))
            height = max(1, round(card_height * scale))
            frame = face.resize((width, height), Image.LANCZOS)
            return ImageTk.PhotoImage(frame, master=self)
        width = max(1, round(source[0].width() * card_height / source[0].height()
                             * scale * width_factor))
        height = max(1, round(card_height * scale))
        divisor_x = max(1, math.ceil(face.width() / width))
        divisor_y = max(1, math.ceil(face.height() / height))
        return face.subsample(divisor_x, divisor_y)

    def _item_card_source_center(self, state, cell):
        map_data = state["map"]
        path = map_data["path"]
        cells = map_data.get("cells") or path + map_data.get("branch_cells", [])
        if not isinstance(cell, int) or not (0 <= cell < len(cells)):
            return self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width < 2:
            canvas_width = CANVAS
        if canvas_height < 2:
            canvas_height = CANVAS
        size = int(min(110 * min(canvas_width, canvas_height) / CANVAS,
                       (min(canvas_width, canvas_height) - 20)
                       // max(map_data["width"], map_data["height"])))
        ox = (canvas_width - size * map_data["width"]) // 2
        oy = (canvas_height - size * map_data["height"]) // 2
        x, y = cells[cell]
        return ox + x * size + size / 2, oy + y * size + size / 2

    def _show_next_item_card_animation(self):
        if not self.item_card_queue:
            self.animating = False
            self._show_next_popup()
            if not self.popup_active and not self.popup_queue and self.state:
                self._show_branch_prompt(self.state)
            return
        event, state = self.item_card_queue.pop(0)
        card_id = event.get("card_id")
        source = self._item_animation_source(card_id)
        if source is None:
            self.after_idle(self._show_next_item_card_animation)
            return
        start = self._item_card_source_center(state, event.get("cell"))
        width = self.canvas.winfo_width() if self.canvas.winfo_width() > 1 else CANVAS
        height = self.canvas.winfo_height() if self.canvas.winfo_height() > 1 else CANVAS
        target = (width / 2, height / 2)
        source_width = source[0].width if self.item_animation_uses_pillow else source[0].width()
        source_height = source[0].height if self.item_animation_uses_pillow else source[0].height()
        card_height = round(source_height * ITEM_CARD_DISPLAY_WIDTH / source_width)
        self.canvas.delete("item-card-animation")
        self.item_card_animation_id = self.canvas.create_image(
            *start, anchor="center", tags=("item-card-animation",))
        self._animate_item_card(source, start, target, card_height, 0)

    def _animate_item_card(self, source, start, target, card_height, frame):
        progress = min(1.0, frame / ITEM_CARD_FLIGHT_FRAMES)
        eased = progress * progress * (3 - 2 * progress)
        angle = progress * math.tau * 2
        image = self._item_card_frame_image(source, card_height, progress, angle)
        self.item_card_animation_image = image
        x = start[0] + (target[0] - start[0]) * eased
        y = start[1] + (target[1] - start[1]) * eased
        if not self.canvas.type(self.item_card_animation_id):
            self.item_card_animation_id = self.canvas.create_image(
                x, y, image=image, anchor="center", tags=("item-card-animation",))
        else:
            self.canvas.coords(self.item_card_animation_id, x, y)
            self.canvas.itemconfigure(self.item_card_animation_id, image=image)
        self.canvas.tag_raise("item-card-animation")
        if frame < ITEM_CARD_FLIGHT_FRAMES:
            self.after(ITEM_CARD_FRAME_MS, self._animate_item_card,
                       source, start, target, card_height, frame + 1)
        else:
            self.item_card_hold_bind_id = self.canvas.bind(
                "<Button-1>", self._dismiss_item_card_animation, add="+")
            self.item_card_hold_after = self.after(
                ITEM_CARD_HOLD_MS, self._finish_item_card_animation)

    def _dismiss_item_card_animation(self, _event):
        if self.item_card_hold_after:
            self.after_cancel(self.item_card_hold_after)
            self.item_card_hold_after = None
        self._finish_item_card_animation()

    def _finish_item_card_animation(self):
        self.item_card_hold_after = None
        if self.item_card_hold_bind_id:
            self.canvas.unbind("<Button-1>", self.item_card_hold_bind_id)
            self.item_card_hold_bind_id = None
        self.canvas.delete("item-card-animation")
        self.item_card_animation_id = None
        self.item_card_animation_image = None
        self._show_next_item_card_animation()

    def _queue_state_popups(self, s):
        players = {p["id"]: p for p in s["players"]}
        for event in s.get("effect_events", []):
            sequence = event.get("seq", 0)
            if sequence <= self.last_popup_effect_seq:
                continue
            self.last_popup_effect_seq = sequence
            if event.get("kind") == "item_card_drawn":
                if event.get("pid") == self.pid:
                    self.item_card_queue.append((event, s))
                continue
            if event.get("kind") == "shop_visit":
                if event.get("pid") == self.pid:
                    self.shop_queue.append(event)
                continue
            player = players.get(event["pid"])
            if player:
                name = "나" if player["id"] == self.pid else player["name"]
                text = (f"{player['name']}가 드리프트 성공!"
                        if event.get("text") == "드리프트 성공!"
                        else f"{name} : {event['text']}")
                self.popup_queue.append((text, COLORS[player["slot"]]))

        winner_id = s.get("winner")
        victory_key = (s.get("start_seq"), winner_id)
        if (s.get("phase") == "finished" and winner_id in players
                and victory_key != self.victory_popup_key):
            winner = players[winner_id]
            self.popup_queue.append((f"{winner['name']}가 승리했습니다!",
                                     VICTORY_GOLD, "victory"))
            self.victory_popup_key = victory_key

        turn = s.get("turn")
        turn_key = (s.get("start_seq"), turn)
        if turn is None or turn_key == self.turn_popup_key:
            return
        player = players.get(turn)
        if player:
            text = "내차례" if turn == self.pid else f"{player['name']}의 차례"
            self.popup_queue.append((text, COLORS[player["slot"]]))
            self.turn_popup_key = turn_key

    def _show_next_popup(self):
        if self.popup_active:
            return
        if not self.popup_queue:
            self._show_next_shop_popup()
            if not self.shop_popup:
                self._show_shop_card_choice()
            return
        popup = self.popup_queue.pop(0)
        text, color = popup[:2]
        self.popup_mode = popup[2] if len(popup) > 2 else None
        self.popup_active = True
        self.popup_text = text
        self.popup_color = color
        self._draw_popup(text, color)
        if self.popup_mode == "victory":
            self.popup_after = self.after(
                VICTORY_FLASH_INTERVAL_MS, self._flash_victory_popup, 1)
            return
        self.popup_after = self.after(POPUP_HOLD_MS, self._fade_popup, 0)

    def _show_shop_card_choice(self):
        if (not self.state or self.animating or self.popup_active or self.popup_queue
                or self.shop_popup or self.item_popup or self.branch_dialog):
            return
        choice = self.state.get("pending_shop_choice")
        if not choice or choice.get("pid") != self.pid:
            return
        if (self.shop_effect_dialog and self.shop_effect_dialog.winfo_exists()
                and self.shop_effect_dialog_id == choice["id"]):
            self.shop_effect_dialog.lift()
            return
        dialog = tk.Toplevel(self)
        self.shop_effect_dialog = dialog
        self.shop_effect_dialog_id = choice["id"]
        dialog.transient(self.winfo_toplevel())
        dialog.resizable(False, False)
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        if choice["kind"] == "optional_reroll_one_die":
            dialog.title("백기사")
            ttk.Label(dialog, text="다시 굴릴 주사위를 선택하세요.").pack(
                padx=16, pady=(14, 8))
            die_index = tk.IntVar(master=dialog, value=0)
            for index, value in enumerate(choice["values"]):
                ttk.Radiobutton(
                    dialog, text=f"주사위 {index + 1}: {value}",
                    variable=die_index, value=index).pack(anchor="w", padx=16)
            buttons = ttk.Frame(dialog)
            buttons.pack(anchor="e", padx=12, pady=12)
            ttk.Button(
                buttons, text="다시 굴리지 않기",
                command=lambda: self._submit_shop_card_choice(
                    dialog, choice["id"], "keep")).pack(side="right", padx=(6, 0))
            ttk.Button(
                buttons, text="선택한 주사위 다시 굴리기",
                command=lambda: self._submit_shop_card_choice(
                    dialog, choice["id"], "reroll", die_index.get())).pack(side="right")
        elif choice["kind"] == "optional_move_adjustment":
            dialog.title("렉키")
            ttk.Label(dialog, text="기본 이동을 1칸 줄일까요?").pack(
                padx=16, pady=(14, 8))
            ttk.Label(dialog, text=f"예정 이동: {choice['total']}칸").pack(
                padx=16, pady=(0, 8))
            buttons = ttk.Frame(dialog)
            buttons.pack(anchor="e", padx=12, pady=12)
            ttk.Button(
                buttons, text="그대로 이동",
                command=lambda: self._submit_shop_card_choice(
                    dialog, choice["id"], "normal")).pack(side="right", padx=(6, 0))
            ttk.Button(
                buttons, text="1칸 적게 이동",
                command=lambda: self._submit_shop_card_choice(
                    dialog, choice["id"], "less")).pack(side="right")
        else:
            dialog.destroy()
            self.shop_effect_dialog = None
            self.shop_effect_dialog_id = None
            return
        dialog.grab_set()

    def _submit_shop_card_choice(self, dialog, choice_id, action, die_index=None):
        try:
            self.client.resolve_shop_card_choice(choice_id, action, die_index)
        except OSError as error:
            messagebox.showerror("상점 카드 효과 오류", str(error), parent=dialog)

    def _flash_victory_popup(self, phase):
        if phase >= VICTORY_FLASHES * 2:
            self.canvas.delete("popup")
            self.popup_items = ()
            self.popup_active = False
            self.popup_mode = None
            if self.popup_queue:
                self._show_next_popup()
            else:
                self._render()
                self._show_next_popup()
                if self.state:
                    self._show_branch_prompt(self.state)
            return

        _, _, text_id = self.popup_items
        color = POPUP_BACKGROUND if phase % 2 else VICTORY_GOLD
        self.canvas.itemconfigure(text_id, fill=color)
        delay = (VICTORY_ANIMATION_MS - VICTORY_FLASH_INTERVAL_MS * (VICTORY_FLASHES * 2 - 1)
                 if phase == VICTORY_FLASHES * 2 - 1 else VICTORY_FLASH_INTERVAL_MS)
        self.popup_after = self.after(delay, self._flash_victory_popup, phase + 1)

    def _draw_popup(self, text, color):
        canvas = self.canvas
        canvas.delete("popup")
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width < 2:
            canvas_width = CANVAS
        if canvas_height < 2:
            canvas_height = CANVAS
        max_width = max(200, min(round(560 * self.k), canvas_width - 40))
        pad = round(32 * self.k)
        font = tkfont.Font(self, font=("", -round(22 * self.k), "bold"))
        center_x, center_y = canvas_width / 2, canvas_height / 2
        text_id = canvas.create_text(center_x, center_y, text=text, fill=color, font=font,
                                     width=max_width - 2 * pad, justify="center", tags=("popup",))
        bounds = canvas.bbox(text_id)
        text_height = bounds[3] - bounds[1] if bounds else font.metrics("linespace")
        box_height = max(round(100 * self.k), text_height + 2 * pad)
        canvas.delete(text_id)
        x1, y1 = center_x - max_width / 2, center_y - box_height / 2
        radius = round(18 * self.k)
        outer = self._rounded_popup_points(x1 + 2, y1 + 2, x1 + max_width - 2,
                                          y1 + box_height - 2, radius)
        inner = self._rounded_popup_points(x1 + 8, y1 + 8, x1 + max_width - 8,
                                          y1 + box_height - 8, max(6, radius - 6))
        outer_id = canvas.create_polygon(*outer,
                                         fill=POPUP_BACKGROUND, outline=color,
                                         width=max(2, round(4 * self.k)), tags=("popup",))
        inner_id = canvas.create_polygon(*inner,
                                         fill="", outline=color, width=max(1, round(2 * self.k)),
                                         tags=("popup",))
        text_id = canvas.create_text(center_x, center_y, text=text,
                                     fill=color, font=font, width=max_width - 2 * pad,
                                     justify="center", tags=("popup",))
        canvas.tag_raise(inner_id, outer_id)
        canvas.tag_raise(text_id, inner_id)
        self.popup_items = (outer_id, inner_id, text_id)

    @staticmethod
    def _rounded_popup_points(x1, y1, x2, y2, radius):
        points = []
        corners = ((x2 - radius, y1 + radius, -90),
                   (x2 - radius, y2 - radius, 0),
                   (x1 + radius, y2 - radius, 90),
                   (x1 + radius, y1 + radius, 180))
        for cx, cy, start in corners:
            for step in range(7):
                angle = math.radians(start + step * 15)
                points.extend((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
        return points

    def _fade_popup(self, step):
        if step >= POPUP_FADE_STEPS:
            self.canvas.delete("popup")
            self.popup_items = ()
            self.popup_active = False
            self.popup_mode = None
            if self.popup_queue:
                self._show_next_popup()
            else:
                self._render()
                self._show_next_popup()
                if self.state:
                    self._show_branch_prompt(self.state)
            return

        ratio = step / POPUP_FADE_STEPS
        faded = self._blend_popup_color(self.popup_color, BOARD_BACKGROUND, ratio)
        outer_id, inner_id, text_id = self.popup_items
        self.canvas.itemconfigure(outer_id, outline=faded)
        self.canvas.itemconfigure(inner_id, outline=faded)
        self.canvas.itemconfigure(text_id, fill=faded)
        self.popup_after = self.after(POPUP_FADE_INTERVAL_MS, self._fade_popup, step + 1)

    @staticmethod
    def _blend_popup_color(source, target, ratio):
        channels = [int(source[i:i + 2], 16) for i in (1, 3, 5)]
        target_channels = [int(target[i:i + 2], 16) for i in (1, 3, 5)]
        return "#%02x%02x%02x" % tuple(
            round(a + (b - a) * ratio) for a, b in zip(channels, target_channels))

    # ---- 선 정하기 연출 ----
    def _start_order_animation(self, s):
        self.animating = True
        if self.server:
            self.start_btn.config(state="disabled")
        self.roll_btn.config(state="disabled")
        self.dice_canvas.delete("all")
        self._order_round(s, 0)

    def _order_round(self, s, idx):
        rounds = s["start_rolls"]
        names = {p["id"]: p for p in s["players"]}
        if idx >= len(rounds):
            first = names[s["turn"]]
            self.status.config(text=f"{first['name']} 님 선공!")
            self.after(ORDER_FINAL_MS, self._finish_animation, s)
            return
        self.status.config(text="선 정하기: 주사위를 굴립니다..." if idx == 0
                           else "동점! 동점자끼리 다시 굴립니다...")
        self._order_frame(s, idx, 0)

    def _order_frame(self, s, idx, frame):
        rnd = s["start_rolls"][idx]
        names = {p["id"]: p for p in s["players"]}
        colors = [COLORS[names[r["pid"]]["slot"]] for r in rnd]
        labels = [names[r["pid"]]["name"] for r in rnd]
        if frame < ANIM_FRAMES:
            faces = [random.randint(1, 3) for _ in rnd]
            self._draw_dice(faces, colors, shake=True, labels=labels)
            self.after(ANIM_BASE_MS + frame * ANIM_SLOW_MS, self._order_frame, s, idx, frame + 1)
        else:
            self._draw_dice([r["value"] for r in rnd], colors, labels=labels)
            self.after(ORDER_HOLD_MS, self._order_round, s, idx + 1)

    def _finish_animation(self, s):
        self.animating = False
        self._apply_state(s)

    # ---- 주사위 애니메이션 ----
    def _start_roll_animation(self, s):
        self.animating = True
        roller = next((p for p in s["players"] if p["id"] == s["last_roll"]["pid"]), None)
        color = COLORS[roller["slot"]] if roller else "#7f8c8d"
        self._anim_step(s, color, 0)

    def _anim_step(self, s, color, frame):
        values = s["last_roll"]["values"]
        if frame < ANIM_FRAMES:
            faces = [random.randint(1, 3) for _ in values]
            self._draw_dice(faces, color, shake=True)
            self.after(ANIM_BASE_MS + frame * ANIM_SLOW_MS, self._anim_step, s, color, frame + 1)
        elif frame == ANIM_FRAMES:
            self._draw_dice(values, color, show_total=True)
            self.after(ANIM_HOLD_MS, self._anim_step, s, color, frame + 1)
        else:
            self._finish_roll(s)

    # ---- 말 이동 애니메이션 ----
    def _finish_roll(self, s):
        """주사위 연출이 끝난 뒤, 굴린 말을 한 칸씩 이동시키고 새 상태를 반영한다."""
        pid = s["last_roll"]["pid"]
        path = s.get("move_path", [])
        if not path:
            self._finish_animation(s)
            return
        self._move_step(s, pid, path, 0)

    def _start_move_animation(self, s):
        self.animating = True
        self._move_step(s, s["move_pid"], s["move_path"], 0)

    def _move_step(self, s, pid, path, index):
        self._draw_board(s, override={pid: path[index]})
        if index + 1 >= len(path):
            self.after(MOVE_STEP_MS, self._finish_animation, s)
        else:
            self.after(MOVE_STEP_MS, self._move_step, s, pid, path, index + 1)

    def _draw_dice(self, values, colors, shake=False, show_total=False, labels=None):
        c = self.dice_canvas
        c.delete("all")
        k = self.k
        dice_w, dice_h, die, gap = DICE_W * k, DICE_H * k, DIE_SIZE * k, DIE_GAP * k
        n = len(values)
        if isinstance(colors, str):
            colors = [colors] * n
        x0 = (dice_w - (n * die + (n - 1) * gap)) / 2
        for i, v in enumerate(values):
            x = x0 + i * (die + gap)
            y = 8 * k
            if shake:
                x += random.randint(-3, 3) * k
                y += random.randint(-5, 5) * k
            self._draw_die(x, y, v, colors[i])
            if labels:
                name = labels[i] if len(labels[i]) <= 5 else labels[i][:4] + "…"
                c.create_text(x0 + i * (die + gap) + die / 2, dice_h - 22 * k,
                              text=name, fill=colors[i], font=self._font(9, True))
        if show_total and n > 1:
            c.create_text(dice_w / 2, dice_h - 14 * k, text=f"합계 {sum(values)}", font=self._font(12, True))

    def _draw_die(self, x, y, value, color):
        c = self.dice_canvas
        k = self.k
        s, r = DIE_SIZE * k, 10 * k
        # smooth 다각형: 모서리 점을 겹쳐 넣어 둥근 사각형을 만든다
        rp = [x + r, y, x + s - r, y, x + s, y, x + s, y + r, x + s, y + s - r, x + s, y + s,
              x + s - r, y + s, x + r, y + s, x, y + s, x, y + s - r, x, y + r, x, y]
        c.create_polygon(rp, smooth=True, fill=_lighten(color), outline=color, width=max(1, round(3 * k)))
        margin = s * 0.26
        step = (s - 2 * margin) / 2
        pr = s * 0.075 + 1
        for col, row in PIPS[value]:
            cx = x + margin + col * step
            cy = y + margin + row * step
            c.create_oval(cx - pr, cy - pr, cx + pr, cy + pr, fill="#2c3e50", outline="")

    def _log(self, text):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    # ---- 그리기 ----
    def _render(self):
        s = self.state
        if self.edit_mode and self.editor_map:
            s = dict(s)
            s["map"] = self.editor_map.to_dict()
        players = {p["id"]: p for p in s["players"]}
        self.info.config(text=f"{s['map']['name']} / 승리 {s['laps']}바퀴")

        if self.edit_mode:
            self.status.config(text="맵 수정 중")
        elif s["phase"] == "lobby":
            self.status.config(text=f"대기 중... ({len(players)}/{MAX_PLAYERS}명)")
        elif s["phase"] == "playing":
            self.status.config(text=f"{players[s['turn']]['name']} 님의 차례")
        else:
            self.status.config(text=f"{players[s['winner']]['name']} 님 승리!")

        for w in self.players_box.winfo_children():
            w.destroy()
        label_font = tkfont.Font(font=self._font(11, True))
        label_width = round((RIGHT_PANEL_BASE_WIDTH - 37) * self.k)
        for p in s["players"]:
            mark = "▶ " if p["id"] == s["turn"] else "   "
            text = f"{mark}{p['name']}"
            lines = []
            line = ""
            for char in text:
                if line and label_font.measure(line + char) > label_width:
                    lines.append(line)
                    line = char
                else:
                    line += char
            if line:
                lines.append(line)
            tk.Label(self.players_box, fg=COLORS[p["slot"]], font=self._font(11, True), anchor="w",
                     text="\n".join(lines), wraplength=label_width).pack(anchor="w")

        self._render_color_menu(s, players)

        lr = s["last_roll"]
        if lr:
            roller = players.get(lr["pid"])
            self._draw_dice(lr["values"], COLORS[roller["slot"]] if roller else "#7f8c8d", show_total=True)
        else:
            self.dice_canvas.delete("all")
        mine = (s["phase"] == "playing" and s["turn"] == self.pid
            and s.get("branch_request") is None
            and s.get("pending_shop_choice") is None
            and not self.popup_active and not self.popup_queue
            and not self.shop_popup and not self.shop_queue)
        count = players[self.pid]["dice"] if self.pid in players else 0
        self.roll_btn.config(text=f"주사위 굴리기 ({count}개)" if mine else "주사위 굴리기",
                             state="normal" if mine else "disabled")
        if self.server:
            can_edit = s["phase"] == "lobby"
            self.start_btn.config(state="normal" if can_edit and not self.edit_mode else "disabled")
            self.map_select_btn.config(state="normal" if can_edit and not self.edit_mode else "disabled")
            self.edit_map_btn.config(text="수정 종료" if self.edit_mode else "맵 수정",
                                     state="normal" if can_edit else "disabled")
            self.save_map_btn.config(state="normal" if can_edit else "disabled")
        self._draw_gauge(s)
        self._draw_board(s)

    def _render_color_menu(self, s, players):
        """대기실에서 색상 선택 버튼을 보여준다. 다른 플레이어가 고른 색상은 비활성화."""
        # 자식이 없어진 Frame 은 이전 크기를 그대로 요청하므로, 매번 새로 만든다
        self.color_box.destroy()
        self.color_box = ttk.Frame(self.color_wrap)
        self.color_box.grid(row=0, column=0, sticky="nw")
        if self.pid not in players:
            return
        player = players[self.pid]
        if s["phase"] == "lobby":
            mine = player["slot"]
            taken = {p["slot"] for p in s["players"] if p["id"] != self.pid}
            ttk.Label(self.color_box, text="내 캐릭터 선택").pack(anchor="w", pady=(6, 2))
            row = ttk.Frame(self.color_box)
            row.pack(anchor="w")
            for slot, color in enumerate(COLORS):
                if slot == mine:
                    text, state, relief = "✔", "normal", "sunken"
                elif slot in taken:
                    text, state, relief = "✕", "disabled", "flat"
                else:
                    text, state, relief = "", "normal", "raised"
                photo = self._character_image(slot, round(CHARACTER_BUTTON_H * self.k))
                options = {
                    "bg": color, "activebackground": color, "fg": "#ffffff",
                    "disabledforeground": "#ffffff", "relief": relief, "state": state,
                    "padx": 3, "pady": 3,
                    "command": lambda sl=slot: self._choose_color(sl),
                }
                if photo:
                    options.update(image=photo, text=text, compound="center")
                else:
                    options.update(text=text or "색상", width=4, height=2)
                tk.Button(row, **options).pack(side="left", padx=2)
            return

        status_font = ("", -round(20 * self.k), "bold")
        ttk.Label(self.color_box,
                  text=f"{player['lap']}/{s['laps']} Laps",
                  font=status_font).pack(
                      anchor="w", pady=(6, 2))
        ttk.Label(self.color_box, text=f"루찌: {player['luci']}", font=status_font).pack(anchor="w")

    def _character_image(self, slot, height):
        key = (slot, height)
        if key not in self.character_images:
            path = os.path.join(IMAGES_DIR, CHARACTER_FILES[slot])
            try:
                from PIL import Image, ImageTk
                image = Image.open(path).convert("RGBA")
                width = round(image.width * height / image.height)
                image = image.resize((width, height), Image.LANCZOS)
                photo = ImageTk.PhotoImage(image, master=self)
            except ImportError:
                try:
                    source = tk.PhotoImage(file=path, master=self)
                    divisor = max(1, round(source.height() / height))
                    photo = source.subsample(divisor)
                except (OSError, tk.TclError):
                    photo = None
            except (OSError, tk.TclError):
                photo = None
            self.character_images[key] = photo
        return self.character_images[key]

    def _trap_image(self, trap_type, size):
        key = (trap_type, size)
        if key not in self.trap_images:
            filename = TRAP_IMAGE_FILES.get(trap_type)
            if filename is None:
                return None
            path = os.path.join(IMAGES_DIR, filename)
            try:
                try:
                    from PIL import Image, ImageTk
                    image = Image.open(path).convert("RGBA")
                    image.thumbnail((size, size), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(image, master=self)
                except ImportError:
                    source = tk.PhotoImage(file=path, master=self)
                    divisor = max(1, math.ceil(max(source.width(), source.height()) / size))
                    photo = source.subsample(divisor)
            except (OSError, tk.TclError):
                photo = None
            self.trap_images[key] = photo
        return self.trap_images[key]

    def _status_effect_image(self, effect, size):
        key = (effect, size)
        if key not in self.status_images:
            filename = STATUS_IMAGE_FILES.get(effect)
            if filename is None:
                return None
            path = os.path.join(IMAGES_DIR, filename)
            try:
                try:
                    from PIL import Image, ImageTk
                    image = Image.open(path).convert("RGBA")
                    image.thumbnail((size, size), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(image, master=self)
                except ImportError:
                    source = tk.PhotoImage(file=path, master=self)
                    divisor = max(1, math.ceil(max(source.width(), source.height()) / size))
                    photo = source.subsample(divisor)
            except (OSError, tk.TclError) as error:
                self._log(f"! 상태 효과 아이콘을 불러오지 못했습니다 ({filename}): {error}")
                photo = None
            self.status_images[key] = photo
        return self.status_images[key]

    def _draw_gauge(self, s):
        """기어 게이지 배경 위에 내 플레이어의 ▲ 마커를 해당 기어 숫자 아래에 겹쳐 그린다."""
        player = next((p for p in s["players"] if p["id"] == self.pid), None)
        name = "up" if player and player.get("gear_gauge_upgraded") else "basic"
        if name not in self.gauge_images:
            self.gauge_images[name] = _load_gauge_image(GAUGES[name]["file"], round(GAUGE_TARGET_W * self.k))
        photo, scale = self.gauge_images[name]
        c = self.gauge_canvas
        cfg = GAUGES[name]
        if name != self.gauge_name:
            self.gauge_name = name
            if photo:
                c.config(width=photo.width(), height=photo.height())
        c.delete("all")
        if photo:
            c.create_image(0, 0, image=photo, anchor="nw")
        cx, cy = cfg["center"]
        if player:
            c.create_text(cx * scale, cy * scale, text=f"{player['gear']}단",
                          fill=COLORS[player["slot"]],
                          font=("", max(14, round(40 * scale)), "bold"))
        size = MARKER_SIZE * scale
        by_gear = {}
        for p in s["players"]:
            if p["id"] == self.pid:          # 이 클라이언트를 실행 중인 플레이어만 표시
                by_gear.setdefault(p["gear"], []).append(p)
        for gear, group in by_gear.items():
            nx, ny = cfg["numbers"][min(gear, len(cfg["numbers"])) - 1]
            d = math.hypot(nx - cx, ny - cy)
            ux, uy = (nx - cx) / d, (ny - cy) / d          # 중심 -> 숫자 방향 (바깥쪽)
            tx, ty = -uy, ux                                # 접선 방향
            mx, my = (cx + ux * cfg["radius"]) * scale, (cy + uy * cfg["radius"]) * scale
            for i, p in enumerate(sorted(group, key=lambda q: q["slot"])):
                off = (i - (len(group) - 1) / 2) * size * 1.1   # 같은 기어면 나란히
                px, py = mx + tx * off, my + ty * off
                tip = (px + ux * size * 0.6, py + uy * size * 0.6)
                base = (px - ux * size * 0.4, py - uy * size * 0.4)
                pts = [*tip, base[0] + tx * size * 0.5, base[1] + ty * size * 0.5,
                       base[0] - tx * size * 0.5, base[1] - ty * size * 0.5]
                turn = p["id"] == s["turn"]
                c.create_polygon(pts, fill=COLORS[p["slot"]], outline="#ffffff" if turn else "#101010",
                                 width=2 if turn else 1)

    def _item_card_image(self, card_id, size):
        key = (card_id, size)
        if key not in self.item_card_images:
            path = os.path.join(IMAGES_DIR, f"item_card_{card_id:02d}.png")
            try:
                try:
                    from PIL import Image, ImageTk
                    with Image.open(path) as image_file:
                        image = image_file.convert("RGBA")
                    image = image.resize(
                        (round(size * 680 / 1000), size), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(image, master=self)
                except ImportError:
                    source = tk.PhotoImage(file=path, master=self)
                    divisor = max(1, round(source.height() / size))
                    photo = source.subsample(divisor, divisor)
                self.item_card_images[key] = photo
            except (OSError, tk.TclError):
                self.item_card_images[key] = None
        return self.item_card_images[key]

    def _shop_card_image(self, card_id, height):
        key = (card_id, height)
        if key not in self.shop_card_images:
            path = os.path.join(IMAGES_DIR, f"shop_card_{card_id:02d}.png")
            try:
                try:
                    from PIL import Image, ImageTk
                    with Image.open(path) as image_file:
                        image = image_file.convert("RGBA")
                    image = image.resize(
                        (round(height * 400 / 560), height), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(image, master=self)
                except ImportError:
                    source = tk.PhotoImage(file=path, master=self)
                    divisor = max(1, round(source.height() / height))
                    photo = source.subsample(divisor, divisor)
                self.shop_card_images[key] = photo
            except (OSError, tk.TclError) as error:
                self._log(f"! 상점 카드 이미지를 불러오지 못했습니다: {error}")
                self.shop_card_images[key] = None
        return self.shop_card_images[key]

    def _draw_card_slots(self, state=None):
        canvas = self.card_slots_canvas
        canvas.delete("all")
        width = canvas.winfo_width()
        if width < 2:
            width = CANVAS
        scale = self.k
        card_height = round(CARD_SLOT_HEIGHT * scale)
        shop_width = round(card_height * 400 / 560)
        item_width = round(card_height * 680 / 1000)
        item_gap = round(CARD_SLOT_GAP * scale)
        item_group_width = item_width * 3 + item_gap * 2
        group_gap = round(CARD_GROUP_GAP * scale)
        total_width = shop_width + group_gap + item_group_width
        start_x = (width - total_width) / 2
        label_y = round(CARD_PANEL_PADDING * scale + CARD_SLOT_LABEL_HEIGHT * scale / 2)
        card_y = round((CARD_PANEL_PADDING + CARD_SLOT_LABEL_HEIGHT) * scale)
        shop_x = start_x
        item_x = shop_x + shop_width + group_gap
        player = next((p for p in (state or {}).get("players", [])
                       if p["id"] == self.pid), None)
        items = player["items"] if player else []
        shop_cards = player.get("shop_cards", []) if player else []
        panel_font = self._font(10, True)
        shop_label = f"상점 카드 ({len(shop_cards)})" if shop_cards else "상점 카드"
        canvas.create_text(shop_x + shop_width / 2, label_y, text=shop_label,
                           fill="#ffffff", font=panel_font, tags=("card-slot-label",))
        capacity = player.get("item_capacity", 2) if player else 2
        item_label = f"아이템 카드 ({len(items)}/{capacity})"
        canvas.create_text(item_x + item_group_width / 2, label_y, text=item_label,
                           fill="#ffffff", font=panel_font, tags=("card-slot-label",))
        item_slots = [(item_x + index * (item_width + item_gap), item_width)
                      for index in range(3)]
        slots = [(shop_x, shop_width)] + item_slots
        radius = round(12 * scale)
        for x, slot_width in slots:
            points = self._rounded_popup_points(x, card_y, x + slot_width,
                                                card_y + card_height, radius)
            canvas.create_polygon(*points, fill="#ffffff", outline="#000000",
                                  width=max(2, round(3 * scale)), tags=("card-slot",))
        if shop_cards:
            image = self._shop_card_image(shop_cards[-1], card_height)
            if image:
                canvas.create_image(shop_x + shop_width / 2, card_y + card_height / 2,
                                    image=image, anchor="center", tags=("shop-card",))
        self.item_card_hitboxes = []
        visible_items = items[-3:]
        first_index = len(items) - len(visible_items)
        for offset, (card_id, (x, slot_width)) in enumerate(zip(visible_items, item_slots)):
            card_index = first_index + offset
            hovered = card_index == self.hovered_item_index
            image = self._item_card_image(card_id, card_height)
            if image:
                canvas.create_image(x + slot_width / 2, card_y + card_height / 2,
                                    image=image, anchor="center", tags=("item-card",))
            if hovered:
                points = self._rounded_popup_points(x, card_y, x + slot_width,
                                                    card_y + card_height, radius)
                canvas.create_polygon(*points, fill="", outline="#00ffff",
                                      width=max(5, round(6 * scale)),
                                      tags=("item-card-hover",))
            self.item_card_hitboxes.append(
                (card_index, card_id, x, card_y, x + slot_width, card_y + card_height))

    def _can_select_item_card(self):
        return (self.state is not None
                and self.state.get("phase") == "playing"
                and (self.debug_mode or self.state.get("turn") == self.pid)
                and self.state.get("pending_shop_choice") is None
                and self.state.get("branch_request") is None
                and not self.shop_popup and not self.shop_queue)

    def _on_card_slots_motion(self, event):
        hovered = (next((index for index, _, x1, y1, x2, y2 in self.item_card_hitboxes
                         if x1 <= event.x <= x2 and y1 <= event.y <= y2), None)
                   if self._can_select_item_card() else None)
        if hovered != self.hovered_item_index:
            self.hovered_item_index = hovered
            self._draw_card_slots(self.state)

    def _on_card_slots_leave(self, _event):
        if self.hovered_item_index is not None:
            self.hovered_item_index = None
            self._draw_card_slots(self.state)

    def _on_card_slots_click(self, event):
        if self.animating or not self._can_select_item_card():
            return
        hit = next((entry for entry in self.item_card_hitboxes
                    if entry[2] <= event.x <= entry[4] and entry[3] <= event.y <= entry[5]), None)
        if hit:
            self._open_item_card_popup(hit[1])

    def _show_next_shop_popup(self):
        if (self.shop_popup or self.item_popup or self.popup_active or self.popup_queue
                or self.animating):
            return
        while self.shop_queue:
            event = self.shop_queue.pop(0)
            if event.get("pid") != self.pid:
                continue
            player = next((p for p in self.state["players"] if p["id"] == self.pid), None)
            active_tokens = {visit["token"] for visit in player.get("shop_visits", [])} if player else set()
            if event.get("shop_token") not in active_tokens:
                continue
            self._open_shop_popup(event)
            return

    def _open_shop_popup(self, event):
        player = next((p for p in self.state["players"] if p["id"] == self.pid), None)
        if not player:
            return
        popup = tk.Toplevel(self)
        self.shop_popup = popup
        self.shop_popup_token = event["shop_token"]
        self.shop_available_cards = set(event.get("available_cards", []))
        self.shop_selected_card_id = None
        self.shop_upgrade_selected = False
        self.shop_purchase_pending = False
        self.shop_card_buttons = {}
        popup.title("상점")
        popup.transient(self.winfo_toplevel())
        popup.resizable(False, False)
        popup.protocol("WM_DELETE_WINDOW", self._close_shop_popup)

        header = ttk.Frame(popup, padding=(12, 10, 12, 6))
        header.pack(fill="x")
        amount_font = ("TkDefaultFont", max(12, round(14 * self.k)), "italic")
        self.shop_balance_label = tk.Label(header, fg="#222222", font=amount_font)
        self.shop_balance_label.pack(side="left")
        self.shop_remaining_label = tk.Label(
            header, fg="#d00000", font=amount_font)
        self.shop_remaining_label.pack(side="left", padx=(10, 0))

        upgrade_row = ttk.Frame(header)
        upgrade_row.pack(side="right")
        self.shop_upgrade_button = tk.Button(
            upgrade_row, text="", width=2, height=1, borderwidth=2,
            command=self._toggle_shop_upgrade,
        )
        self.shop_upgrade_button.pack(side="left", padx=(0, 6))
        ttk.Label(upgrade_row, text="기어 게이지 업그레이드 (5루찌)").pack(side="left")

        body = ttk.Frame(popup, padding=(12, 0, 12, 8))
        body.pack(fill="both", expand=True)
        cards_frame = ttk.LabelFrame(body, text="상점 카드", padding=6)
        cards_frame.pack(side="left", anchor="n")
        for column in range(5):
            cards_frame.columnconfigure(column, weight=1)
        for card_id in range(1, SHOP_CARD_COUNT + 1):
            row, column = divmod(card_id - 1, 5)
            cell = ttk.Frame(cards_frame, padding=2)
            cell.grid(row=row, column=column, padx=2, pady=2)
            image = self._shop_card_image(card_id, SHOP_CARD_THUMB_HEIGHT)
            available = (card_id in self.shop_available_cards
                         and card_id in SHOP_CARDS_BY_ID)
            button = tk.Button(
                cell, image=image, text="" if image else f"카드 {card_id}",
                compound="top", relief="raised", borderwidth=2,
                state="normal" if available else "disabled",
                command=lambda selected_id=card_id:
                self._select_shop_card(selected_id),
            )
            button.pack()
            button.bind("<Enter>", lambda _event, selected_id=card_id:
                        self._show_shop_card_preview(selected_id))
            button.bind("<Leave>", self._clear_shop_card_preview)
            self.shop_card_buttons[card_id] = button

            if card_id not in SHOP_CARDS_BY_ID:
                status = "판매 안 함"
            elif card_id not in self.shop_available_cards:
                status = "판매 안 함"
            elif self._shop_stock(card_id) <= 0:
                status = "품절"
            else:
                status = ""
            ttk.Label(cell, text=status, foreground="#a00000").pack()

        preview_frame = ttk.LabelFrame(body, text="카드 확대", padding=8)
        preview_frame.pack(side="left", padx=(12, 0), anchor="n")
        self.shop_preview_label = ttk.Label(
            preview_frame, text="카드에 마우스를 올리면 확대됩니다.",
            anchor="center", justify="center")
        self.shop_preview_label.pack()
        self.shop_description_label = ttk.Label(
            preview_frame, text="", wraplength=210, justify="left")
        self.shop_description_label.pack(anchor="w", pady=(6, 0))

        footer = ttk.Frame(popup, padding=(12, 0, 12, 12))
        footer.pack(fill="x")
        self.shop_buy_button = ttk.Button(
            footer, text="구매", command=self._request_shop_purchase)
        self.shop_buy_button.pack(side="right")
        ttk.Button(
            footer, text="닫기", command=self._close_shop_popup,
        ).pack(side="right", padx=(0, 6))
        self._refresh_shop_popup()
        popup.update_idletasks()
        popup.grab_set()

    def _shop_stock(self, card_id):
        stock = self.state.get("shop_stock", {})
        return stock.get(card_id, stock.get(str(card_id), 0))

    def _select_shop_card(self, card_id):
        if self.shop_purchase_pending:
            return
        if card_id not in self.shop_available_cards or card_id not in SHOP_CARDS_BY_ID:
            return
        if self._shop_stock(card_id) <= 0:
            return
        self.shop_selected_card_id = card_id
        self._refresh_shop_popup()

    def _toggle_shop_upgrade(self):
        player = next((p for p in self.state["players"] if p["id"] == self.pid), None)
        if (self.shop_purchase_pending or not player
                or player.get("gear_gauge_upgraded")):
            return
        self.shop_upgrade_selected = not self.shop_upgrade_selected
        self._refresh_shop_popup()

    def _show_shop_card_preview(self, card_id):
        if not self.shop_preview_label:
            return
        image = self._shop_card_image(card_id, SHOP_CARD_PREVIEW_HEIGHT)
        card = SHOP_CARDS_BY_ID.get(card_id)
        self.shop_preview_image = image
        self.shop_preview_label.configure(image=image, text="" if image else "이미지 없음")
        self.shop_description_label.configure(
            text=(card["description"] if card else "현재 구매할 수 없는 카드입니다."))

    def _clear_shop_card_preview(self, _event=None):
        if self.shop_preview_label:
            self.shop_preview_image = None
            self.shop_preview_label.configure(image="", text="카드에 마우스를 올리면 확대됩니다.")
            self.shop_description_label.configure(text="")

    def _refresh_shop_popup(self):
        if not self.shop_popup or not self.shop_popup.winfo_exists():
            return
        player = next((p for p in self.state["players"] if p["id"] == self.pid), None)
        if not player:
            return
        upgraded = player.get("gear_gauge_upgraded", False)
        if upgraded:
            self.shop_upgrade_selected = False
        card_id = self.shop_selected_card_id
        card_cost = SHOP_CARDS_BY_ID[card_id]["cost_luci"] if card_id in SHOP_CARDS_BY_ID else 0
        upgrade_cost = 5 if self.shop_upgrade_selected and not upgraded else 0
        total_cost = card_cost + upgrade_cost
        remaining = player["luci"] - total_cost
        self.shop_balance_label.configure(text=f"보유 루찌: {player['luci']} 루찌")
        self.shop_remaining_label.configure(text=f"선택 후: {remaining} 루찌")

        for card_id, button in self.shop_card_buttons.items():
            available = (card_id in self.shop_available_cards
                         and card_id in SHOP_CARDS_BY_ID
                         and self._shop_stock(card_id) > 0)
            button.configure(
                relief="sunken" if card_id == self.shop_selected_card_id else "raised",
                state="normal" if available and not self.shop_purchase_pending else "disabled",
            )
        self.shop_upgrade_button.configure(
            text="✓" if upgraded or self.shop_upgrade_selected else "",
            relief="sunken" if upgraded or self.shop_upgrade_selected else "raised",
            state="disabled" if upgraded or self.shop_purchase_pending else "normal",
        )
        card_selected = card_id is not None and card_id in self.shop_available_cards
        upgrade_selected = self.shop_upgrade_selected and not upgraded
        can_buy = ((card_selected or upgrade_selected)
                   and (card_id is None or self._shop_stock(card_id) > 0)
                   and remaining >= 0 and not self.shop_purchase_pending)
        self.shop_buy_button.configure(
            state="normal" if can_buy else "disabled")

    def _request_shop_purchase(self):
        if not self.shop_popup_token or self.shop_purchase_pending:
            return
        player = next((p for p in self.state["players"] if p["id"] == self.pid), None)
        if not player:
            return
        upgrade = self.shop_upgrade_selected and not player.get("gear_gauge_upgraded", False)
        try:
            self.client.purchase_shop(
                self.shop_popup_token, self.shop_selected_card_id, upgrade)
        except OSError as error:
            messagebox.showerror("상점 구매 요청 오류", str(error), parent=self.shop_popup)
            return
        self.shop_purchase_pending = True
        self._refresh_shop_popup()

    def _close_shop_popup(self, send_close=True, resume=True):
        token = self.shop_popup_token
        if send_close and token is not None:
            try:
                self.client.close_shop(token)
            except OSError as error:
                messagebox.showerror("상점 닫기 오류", str(error), parent=self.shop_popup)
                return
        popup = self.shop_popup
        self.shop_popup = None
        self.shop_popup_token = None
        self.shop_available_cards = set()
        self.shop_card_buttons = {}
        self.shop_preview_image = None
        self.shop_preview_label = None
        self.shop_description_label = None
        self.shop_balance_label = None
        self.shop_remaining_label = None
        self.shop_upgrade_button = None
        self.shop_buy_button = None
        self.shop_selected_card_id = None
        self.shop_upgrade_selected = False
        self.shop_purchase_pending = False
        if popup and popup.winfo_exists():
            popup.grab_release()
            popup.destroy()
        if resume:
            self._render()
            self._show_next_popup()
            if self.state:
                self._show_branch_prompt(self.state)

    def _open_item_card_popup(self, card_id):
        if not self._can_select_item_card():
            return
        player = next((p for p in self.state["players"] if p["id"] == self.pid), None)
        opponents = [p for p in self.state["players"]
                     if p["id"] != self.pid and p["connected"]]
        if not player:
            return
        selectable_card_ids = ([card["id"] for card in ITEM_CARDS]
                               if self.debug_mode else player["items"])
        if card_id not in selectable_card_ids:
            return

        image = self._item_card_image(card_id, ITEM_CARD_DISPLAY_HEIGHT)
        if image is None:
            messagebox.showerror("카드 표시 오류", "카드 이미지를 불러오지 못했습니다.",
                                 parent=self.item_popup or self.winfo_toplevel())
            return

        if self.item_popup and self.item_popup.winfo_exists():
            popup = self.item_popup
            if self.item_popup_card_id == card_id:
                popup.lift()
                return
            for child in popup.winfo_children():
                child.destroy()
        else:
            popup = tk.Toplevel(self)
            self.item_popup = popup
            popup.title("아이템 카드 사용")
            popup.transient(self.winfo_toplevel())
            popup.resizable(False, False)
            popup.protocol("WM_DELETE_WINDOW", lambda: self._close_item_card_popup(popup))

        self.item_popup_card_id = card_id
        self.item_popup_image = image

        popup.columnconfigure(0, weight=0)
        if self.debug_mode:
            picker = ttk.LabelFrame(popup, text="전체 카드 - 선택")
            picker.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 0))
            for selectable_card_id in selectable_card_ids:
                thumbnail = self._item_card_image(selectable_card_id, 64)
                card_label = tk.Label(
                    picker,
                    image=thumbnail,
                    text="" if thumbnail else f"카드 {selectable_card_id}",
                    compound="top",
                    relief="solid",
                    borderwidth=1,
                    highlightthickness=2 if selectable_card_id == card_id else 0,
                    highlightbackground="#00a6a6",
                    cursor="hand2",
                )
                card_label.pack(side="left", padx=4, pady=4)
                card_label.bind(
                    "<Button-1>",
                    lambda _event, selected_id=selectable_card_id:
                    self._open_item_card_popup(selected_id),
                )
            content_row = 1
        else:
            content_row = 0
        popup.rowconfigure(content_row, weight=0)
        content = ttk.Frame(popup, padding=12)
        content.grid(row=content_row, column=0, sticky="nsew")
        content.columnconfigure(0, weight=0)
        content.columnconfigure(1, weight=0)
        ttk.Label(content, image=image).grid(row=0, column=0, sticky="nw", padx=(0, 12))

        controls = ttk.Frame(content)
        controls.grid(row=0, column=1, sticky="new")
        effect = ITEM_CARDS_BY_ID.get(card_id, {}).get("effect", {})
        target_type = effect.get("target")
        requires_target = target_type in {"selected_player", "selected_player_ahead"}
        multi_target = (card_id == 8 and any(
            SHOP_CARDS_BY_ID.get(shop_card_id, {}).get("effect", {}).get("type")
            == "multi_target_item_attack"
            for shop_card_id in player.get("shop_cards", [])))
        if target_type == "selected_player":
            target_players = [p for p in self.state["players"] if p["connected"]]
        elif target_type == "selected_player_ahead":
            target_players = [p for p in opponents
                              if p["progress"] > player["progress"]]
        else:
            target_players = opponents
        target_label = ("미사일 대상 1~2명 선택" if multi_target
                        else "플레이어 선택" if target_type == "selected_player"
                        else "상대 플레이어 선택" if requires_target
                        else "상대 플레이어 선택 불필요")
        targets = ttk.LabelFrame(controls, text=target_label, padding=8)
        targets.pack(fill="x")
        target_pid = tk.IntVar(master=popup,
                               value=target_players[0]["id"] if target_players else -1)
        target_pids = {}
        for opponent in target_players:
            photo = self._character_image(opponent["slot"], round(76 * self.k))
            if multi_target:
                variable = tk.BooleanVar(master=popup, value=False)
                target_pids[opponent["id"]] = variable
                options = {
                    "text": opponent["name"], "variable": variable,
                    "compound": "top", "padx": 8, "pady": 6,
                    "bg": "#f0f0f0", "activebackground": "#d9f2ff",
                    "selectcolor": "#b8e8ff",
                }
                if photo:
                    options["image"] = photo
                tk.Checkbutton(targets, **options).pack(side="left", padx=3)
            else:
                options = {
                    "text": opponent["name"], "value": opponent["id"],
                    "variable": target_pid, "compound": "top",
                    "indicatoron": False, "padx": 8, "pady": 6,
                    "bg": "#f0f0f0", "activebackground": "#d9f2ff",
                    "selectcolor": "#b8e8ff", "relief": "raised",
                    "state": "normal" if requires_target else "disabled",
                }
                if photo:
                    options["image"] = photo
                tk.Radiobutton(targets, **options).pack(side="left", padx=3)

        super_booster = None
        if card_id == 3 and 4 in player.get("shop_cards", []):
            super_booster = tk.BooleanVar(master=popup, value=False)
            ttk.Checkbutton(
                controls, text="슈퍼부스터 효과로 사용",
                variable=super_booster).pack(anchor="w", pady=(8, 0))

        confirmation_text = (
            "미사일 공격 후 성공한 대상 수만큼 이동합니다."
            if multi_target else
            "선택한 플레이어에게 카드를 사용하시겠습니까?"
            if requires_target else
            "슈퍼부스터 효과를 선택해 사용할 수 있습니다."
            if super_booster else
            "카드를 사용하시겠습니까?")
        ttk.Label(controls, text=confirmation_text,
                  wraplength=300, justify="left").pack(anchor="w", pady=(18, 10))
        buttons = ttk.Frame(controls)
        buttons.pack(anchor="e")
        ttk.Button(buttons, text="취소",
                   command=lambda: self._close_item_card_popup(popup)).pack(side="right", padx=(6, 0))
        confirm = ttk.Button(buttons, text="확인",
                             command=lambda: self._request_item_card_use(
                                 popup, card_id,
                                 target_pid if requires_target and not multi_target else None,
                                 target_pids if multi_target else None,
                                 super_booster))
        confirm.pack(side="right")
        if requires_target and not target_players:
            confirm.state(["disabled"])
        popup.update_idletasks()
        window_width = content.winfo_reqwidth() + 24
        window_height = content.winfo_reqheight() + 24
        if self.debug_mode:
            window_width = max(window_width, picker.winfo_reqwidth() + 24)
            window_height += picker.winfo_reqheight() + 12
        screen_width, screen_height = popup.winfo_screenwidth(), popup.winfo_screenheight()
        x = max(0, (screen_width - window_width) // 2)
        y = max(0, (screen_height - window_height) // 2)
        popup.geometry(f"{window_width}x{window_height}+{x}+{y}")
        if not popup.grab_current():
            popup.grab_set()

    def _close_item_card_popup(self, popup, resume=True):
        if popup.winfo_exists():
            popup.destroy()
        self.item_popup = None
        self.item_popup_image = None
        self.item_popup_card_id = None
        if resume:
            self._show_next_popup()
            if self.state:
                self._show_branch_prompt(self.state)

    def _request_item_card_use(self, popup, card_id, target_pid,
                               target_pids=None, use_super_booster=None):
        if not self._can_select_item_card():
            self._close_item_card_popup(popup)
            self._log("! 자신의 차례에만 아이템 카드를 선택할 수 있습니다.")
            return
        try:
            selected_targets = ([pid for pid, variable in target_pids.items()
                                 if variable.get()] if target_pids is not None else None)
            if selected_targets is not None and not 1 <= len(selected_targets) <= 2:
                messagebox.showerror(
                    "대상 선택 오류", "미사일 대상을 한 명 또는 두 명 선택해 주세요.",
                    parent=popup)
                return
            self.client.use_item(
                card_id, target_pid.get() if target_pid else None,
                selected_targets,
                use_super_booster.get() if use_super_booster else False)
        except OSError as error:
            messagebox.showerror("카드 사용 요청 오류", str(error), parent=popup)
            return
        self._close_item_card_popup(popup)

    def _draw_board(self, s, override=None):
        """override: {player id: 칸 인덱스} — 해당 플레이어 말의 위치를 일시적으로 덮어쓴다(이동 애니메이션)."""
        override = override or {}
        self._last_override = override
        c = self.canvas
        self._clear_editor_widgets()
        c.delete("all")
        cw = c.winfo_width() if c.winfo_width() > 1 else CANVAS
        ch = c.winfo_height() if c.winfo_height() > 1 else CANVAS
        m = s["map"]
        path = m["path"]
        cells = m.get("cells") or path + m.get("branch_cells", [])
        avail = min(cw, ch)
        size = min(110 * avail / CANVAS, (avail - 20) // max(m["width"], m["height"]))
        size = int(size)
        ox = (cw - size * m["width"]) // 2
        oy = (ch - size * m["height"]) // 2
        self.board_geometry = (cells, size, ox, oy)
        self.editor_grid_geometry = (size, ox, oy) if self.edit_mode else None

        if self.board_background_image:
            image_width = self.board_background_image.width()
            image_height = self.board_background_image.height()
            for y in range(0, ch, image_height):
                for x in range(0, cw, image_width):
                    c.create_image(x, y, image=self.board_background_image,
                                   anchor="nw", tags=("board-background",))

        if self.edit_mode:
            for y in range(m["height"]):
                for x in range(m["width"]):
                    x0, y0 = ox + x * size, oy + y * size
                    c.create_rectangle(x0, y0, x0 + size, y0 + size,
                                       fill="", outline="#687783", dash=(2, 3), tags=("editor-grid",))

        def center(i):
            x, y = cells[i]
            return ox + x * size + size / 2, oy + y * size + size / 2

        effects = {}
        for e in m.get("effects", []):
            effects.setdefault(e["cell"], []).append(e)
        for i, (x, y) in enumerate(cells):
            x0, y0 = ox + x * size, oy + y * size
            fill = "#101010"
            text_color = "#ffffff"
            c.create_rectangle(x0 + 2, y0 + 2, x0 + size - 2, y0 + size - 2,
                               fill=fill, outline="#080808")
            if i == 0 and size >= 50:
                c.create_text(x0 + 6, y0 + 4, text="START", anchor="nw", fill=text_color,
                              font=("", 10 if self.edit_mode else max(7, size // 8), "bold"),
                              tags=("tile-start-label",))
            if i in effects and size >= 40:
                txt = "\n".join(effect_label(e) for e in effects[i])
                c.create_text(x0 + size / 2, y0 + size - 6, text=txt, anchor="s", fill=text_color,
                              width=size - 8, justify="center",
                              font=("", 10 if self.edit_mode else max(7, size // 10), "bold"))
        traps_by_cell = {}
        for trap in s.get("traps", []):
            if 0 <= trap.get("cell", -1) < len(cells) and trap.get("type") in TRAP_IMAGE_FILES:
                traps_by_cell.setdefault(trap["cell"], set()).add(trap["type"])
        for cell, trap_types in traps_by_cell.items():
            cx, cy = center(cell)
            trap_size = max(16, round(size * 0.36))
            for index, trap_type in enumerate(sorted(trap_types)):
                photo = self._trap_image(trap_type, trap_size)
                if photo:
                    offset = (index - (len(trap_types) - 1) / 2) * trap_size * 0.7
                    c.create_image(cx + offset, cy, image=photo, anchor="center",
                                   tags=("tile-trap",))
        coord_set = {tuple(coord) for coord in cells}
        if "connections" in m:
            connections = {tuple(sorted((tuple(first), tuple(second))))
                           for first, second in m["connections"]}
        else:
            connections = {tuple(sorted((coord, neighbor)))
                           for coord in coord_set
                           for neighbor in ((coord[0] + 1, coord[1]), (coord[0], coord[1] + 1))
                           if neighbor in coord_set}
        connections.update(tuple(sorted((tuple(source), tuple(target))))
                           for source, target in m.get("drift_connections", []))
        drift_connections = [
            (tuple(source), tuple(target)) for source, target in m.get("drift_connections", [])]
        for first, second in connections:
            x1, y1 = first
            x2, y2 = second
            if x1 != x2:
                boundary = ox + max(x1, x2) * size
                y0 = oy + y1 * size
                bounds = (boundary - 2, y0 + 2, boundary + 2, y0 + size - 2)
            else:
                boundary = oy + max(y1, y2) * size
                x0 = ox + x1 * size
                bounds = (x0 + 2, boundary - 2, x0 + size - 2, boundary + 2)
            c.create_rectangle(*bounds, fill="#101010", outline="#101010",
                               tags=("tile-connection",))
        arrow_size = max(7, min(14, size // 5))
        for (source_x, source_y), (target_x, target_y) in drift_connections:
            if target_x > source_x:
                px = ox + (source_x + 1) * size
                py = oy + source_y * size + size / 2
                points = (px + arrow_size / 2, py,
                          px - arrow_size / 2, py - arrow_size / 2,
                          px - arrow_size / 2, py + arrow_size / 2)
            elif target_x < source_x:
                px = ox + source_x * size
                py = oy + source_y * size + size / 2
                points = (px - arrow_size / 2, py,
                          px + arrow_size / 2, py - arrow_size / 2,
                          px + arrow_size / 2, py + arrow_size / 2)
            elif target_y > source_y:
                px = ox + source_x * size + size / 2
                py = oy + (source_y + 1) * size
                points = (px, py + arrow_size / 2,
                          px - arrow_size / 2, py - arrow_size / 2,
                          px + arrow_size / 2, py - arrow_size / 2)
            else:
                px = ox + source_x * size + size / 2
                py = oy + source_y * size
                points = (px, py - arrow_size / 2,
                          px - arrow_size / 2, py + arrow_size / 2,
                          px + arrow_size / 2, py + arrow_size / 2)
            c.create_polygon(*points, fill="#00d9ff", outline="#ffffff", width=1,
                             tags=("drift-direction",))
        curb_width = max(4, min(9, size // 18))
        stripe_count = max(4, min(12, size // 8))
        for x, y in coord_set:
            for side, (dx, dy) in (("top", (0, -1)), ("right", (1, 0)),
                                   ("bottom", (0, 1)), ("left", (-1, 0))):
                neighbor = (x + dx, y + dy)
                edge = tuple(sorted(((x, y), neighbor)))
                if edge in connections or (neighbor in coord_set and (x, y) > neighbor):
                    continue
                x0, y0 = ox + x * size, oy + y * size
                for stripe in range(stripe_count):
                    color = "#f7f7f7" if stripe % 2 == 0 else "#d63031"
                    start = stripe * size / stripe_count
                    end = (stripe + 1) * size / stripe_count
                    if side == "top":
                        bounds = (x0 + start, y0 - curb_width / 2,
                                  x0 + end, y0 + curb_width / 2)
                    elif side == "bottom":
                        bounds = (x0 + start, y0 + size - curb_width / 2,
                                  x0 + end, y0 + size + curb_width / 2)
                    elif side == "left":
                        bounds = (x0 - curb_width / 2, y0 + start,
                                  x0 + curb_width / 2, y0 + end)
                    else:
                        bounds = (x0 + size - curb_width / 2, y0 + start,
                                  x0 + size + curb_width / 2, y0 + end)
                    c.create_rectangle(*bounds, fill=color, outline=color, tags=("curb",))

        if self.edit_mode:
            start_x, start_y = path[0]
            start_direction = m.get("start_direction")
            if start_direction is None:
                start_neighbors = set()
                for first, second in connections:
                    if tuple(first) == tuple(path[0]):
                        start_neighbors.add(tuple(second))
                    elif tuple(second) == tuple(path[0]):
                        start_neighbors.add(tuple(first))
                drift_neighbors = {tuple(target) for source, target in drift_connections
                                   if tuple(source) == tuple(path[0])}
                start_neighbors.update(drift_neighbors)
                delta_direction = {(1, 0): "right", (0, 1): "down",
                                   (-1, 0): "left", (0, -1): "up"}
                direction_candidates = {
                    delta_direction[(x - start_x, y - start_y)]: (x, y)
                    for x, y in start_neighbors
                    if (x - start_x, y - start_y) in delta_direction
                }
                start_direction = next((direction_candidates[d] for d in
                                        ("right", "down", "left", "up")
                                        if d in direction_candidates), None)
            if start_direction is None:
                target_x = target_y = start_x
            else:
                target_x, target_y = start_direction
            if start_direction is not None:
                if target_x > start_x:
                    px, py = ox + (start_x + 1) * size - 2, oy + start_y * size + size / 2
                    arrow_points = (px - 7, py - 6, px + 1, py, px - 7, py + 6)
                elif target_x < start_x:
                    px, py = ox + start_x * size + 2, oy + start_y * size + size / 2
                    arrow_points = (px + 7, py - 6, px - 1, py, px + 7, py + 6)
                elif target_y > start_y:
                    px, py = ox + start_x * size + size / 2, oy + (start_y + 1) * size - 2
                    arrow_points = (px - 6, py - 7, px, py + 1, px + 6, py - 7)
                else:
                    px, py = ox + start_x * size + size / 2, oy + start_y * size + 2
                    arrow_points = (px - 6, py + 7, px, py - 1, px + 6, py + 7)
                c.create_polygon(*arrow_points, fill="#00d9ff", outline="#ffffff", width=1,
                                 tags=("start-direction",))

        r = max(4, size * 0.17)
        for p in s["players"]:
            cx, cy = center(override.get(p["id"], p["cell"]))
            dx = (-1 if p["slot"] % 2 == 0 else 1) * size * 0.2
            dy = (-1 if p["slot"] < 2 else 1) * size * 0.2
            photo = self._character_image(p["slot"], max(18, round(size * 0.4)))
            outline = ("#00ffff" if self.debug_teleport_armed and p["id"] == self.pid
                       else "#000" if p["id"] != s["turn"] else "#ffffff")
            if photo:
                half_w, half_h = photo.width() / 2 + 2, photo.height() / 2 + 2
                c.create_oval(cx + dx - half_w, cy + dy - half_h,
                              cx + dx + half_w, cy + dy + half_h,
                              fill="", outline=outline, width=3 if outline == "#ffffff" else 1)
                c.create_image(cx + dx, cy + dy, image=photo, anchor="center")
            else:
                c.create_oval(cx + dx - r, cy + dy - r, cx + dx + r, cy + dy + r,
                              fill=COLORS[p["slot"]], outline=outline,
                              width=3 if outline == "#ffffff" else 1)
        if self.edit_mode:
            self._draw_editor_controls(s, path, size, ox, oy)
            self._draw_editor_edge_hover()
        self._draw_status_effects(s, c, cw)
        if self.popup_active:
            self._draw_popup(self.popup_text, self.popup_color)

    def _draw_status_effects(self, state, canvas, canvas_width):
        player = next((p for p in state["players"] if p["id"] == self.pid), None)
        if not player:
            return
        effects = [effect for effect in player.get("status_effects", [])
                   if effect in STATUS_IMAGE_FILES]
        if not effects:
            return
        icon_size = max(18, round(26 * self.k))
        gap = 4
        total_width = len(effects) * icon_size + (len(effects) - 1) * gap
        x = max(8, canvas_width - total_width - 8)
        for effect in effects:
            image = self._status_effect_image(effect, icon_size)
            if image:
                canvas.create_image(x, 8, image=image, anchor="nw",
                                    tags=("status-effect",))
            else:
                canvas.create_text(x + icon_size / 2, 8 + icon_size / 2,
                                   text="!", fill="#c0392b",
                                   tags=("status-effect",))
            x += icon_size + gap
    def _draw_editor_controls(self, s, path, size, ox, oy):
        choices = ("없음", *EDITOR_EFFECTS.keys())
        for index, (x, y) in enumerate(path):
            x0, y0 = ox + x * size, oy + y * size
            control_width = max(28, size - 6)
            type_values = EDITOR_TILE_KINDS
            kind = ttk.Combobox(self.canvas, state="readonly", values=type_values,
                                width=max(4, min(10, (size - 26) // 7)), font=("", 10))
            kind.set("출발 타일" if index == 0 else "일반 타일")
            kind.bind("<<ComboboxSelected>>",
                      lambda _event, cell=index, widget=kind:
                      self._set_editor_start(cell, widget.get()))
            self.canvas.create_window(x0 + size / 2, y0 + size * 0.25, window=kind,
                                      width=control_width, height=max(16, round(size * 0.24)),
                                      tags=("editor",))
            self.editor_widgets.append(kind)

            combo = ttk.Combobox(self.canvas, state="readonly", values=choices,
                                 width=max(3, min(12, (size - 12) // 8)), font=("", 10))
            current = self._editor_effect_choice(index)
            combo.configure(values=choices + ((current,) if current not in choices else ()))
            combo.set(current)
            combo.bind("<<ComboboxSelected>>",
                       lambda _event, cell=index, widget=combo:
                       self._set_editor_effect(cell, widget.get()))
            self.canvas.create_window(x0 + size / 2, y0 + size * 0.67, window=combo,
                                      width=control_width, height=max(16, round(size * 0.24)),
                                      tags=("editor",))
            self.editor_widgets.append(combo)
            delete = tk.Button(self.canvas, text="X", fg="#c62828", activeforeground="#b71c1c",
                               padx=0, pady=0, bd=0, font=("", 10, "bold"),
                               command=lambda cell=index: self._delete_editor_tile(cell))
            self.canvas.create_window(x0 + size - 2, y0 + 2, window=delete,
                                      anchor="ne", width=max(16, round(size * 0.2)),
                                      height=max(16, round(size * 0.2)), tags=("editor",))
            self.editor_widgets.append(delete)


class App(tk.Tk):
    def report_callback_exception(self, exc, val, tb):
        # 창 없는 실행 파일에서는 오류가 보이지 않으므로 파일에 남기고, 멈춘 연출 상태를 풀어 준다.
        errorlog.record("Tk 콜백 오류", (exc, val, tb))
        if isinstance(self.frame, GameFrame):
            self.frame.animating = False

    def __init__(self, debug_mode=False):
        super().__init__()
        self.debug_mode = debug_mode
        self.title("카트라이더 보드게임")
        self.resizable(False, False)
        self.client = self.server = self.frame = None
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_launcher()

    def _swap(self, frame):
        if self.frame:
            self.frame.destroy()
        self.frame = frame
        frame.pack(fill="both", expand=True)

    def _shutdown_net(self):
        if self.client:
            self.client.close()
        if self.server:
            self.server.stop()
        self.client = self.server = None

    def show_launcher(self):
        self._shutdown_net()
        set_font_scale(1.0)
        self.state("normal")
        self.minsize(1, 1)
        self.geometry("")           # 게임 화면에서 키운 크기를 버리고 내용 크기로 되돌린다
        self.resizable(False, False)
        self._swap(LauncherFrame(self))

    def start_game(self, client, server):
        self.client, self.server = client, server
        frame = GameFrame(self, client, server)
        self._swap(frame)
        self.resizable(True, True)
        self.update_idletasks()
        self.minsize(*frame.set_base())    # 처음 크기가 곧 최소 크기

    def on_close(self):
        self._shutdown_net()
        self.destroy()


def run(debug_mode=False):
    App(debug_mode=debug_mode).mainloop()
