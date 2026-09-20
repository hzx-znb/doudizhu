# -*- coding: utf-8 -*-
"""
斗地主 · Kivy 版（由 Pydroid3/Pygame V1.5 移植）

文件分工
  core.py  规则、牌型、AI、牌局状态机（与界面无关，和原版逻辑一致，叫分 AI 已修复）
  main.py  Kivy 界面：菜单 / 人数 / 难度 / 设置 / 规则 / 叫分 / 牌局 / 结算

界面实现思路
  原版是 pygame 的“每帧重画”。这里保持同样的思路：一个 Widget 按 900 x N 的
  虚拟坐标系把整个界面画出来，再等比缩放到实际屏幕（手机、平板、电脑窗口都能用）。
  按钮在绘制时顺便登记点击区域，所以“画在哪里”和“点哪里”永远是同一个矩形。

中文字体
  Kivy 默认字体不含汉字。查找顺序：
    1. 项目目录 fonts/ 下自带的字体（最稳，推荐，见 README）
    2. Android / Windows / macOS / Linux 的系统中文字体
"""

import os
import time

from kivy.utils import platform

# Pydroid 3 里 Kivy 的 platform 不一定被识别成 android，所以再用 /system/fonts 判断是不是安卓设备
ON_DEVICE = platform in ("android", "ios") or os.path.isdir("/system/fonts")

if not ON_DEVICE:
    # 电脑上调试时，用竖屏窗口模拟手机
    from kivy.config import Config
    Config.set("graphics", "width", "540")
    Config.set("graphics", "height", "1080")
    Config.set("input", "mouse", "mouse,disable_multitouch")

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.core.window import Window
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.uix.widget import Widget

import core
from core import (Game, PLAYER_RULES, TYPE_NAMES, ai_bid, canonical_card,
                  choose_ai_play, hint_for_player, public_state)

VERSION = "V1.6 · Kivy"

# ------------------------- 颜色（沿用原版，0~255） -------------------------
BG = (19, 111, 70)
BG_DARK = (12, 74, 48)
PANEL = (17, 92, 60)
PANEL2 = (22, 102, 68)
WHITE = (248, 248, 244)
BLACK = (25, 25, 25)
RED = (205, 40, 40)
GOLD = (248, 194, 60)
BLUE = (45, 130, 235)
GRAY = (112, 120, 128)
LIGHT = (231, 235, 235)
CARD = (253, 252, 246)
CARD_SHADOW = (170, 170, 165)
CARD_EDGE = (80, 80, 80)


def rgba(c, alpha=1.0):
    return (c[0] / 255.0, c[1] / 255.0, c[2] / 255.0, alpha)


# ------------------------- 字体 -------------------------
def find_font():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    # 先找 fonts/ 子目录，再找 main.py 同级目录（方便在手机网页上传文件时不用建文件夹）
    for d in (os.path.join(here, "fonts"), here):
        if os.path.isdir(d):
            for name in sorted(os.listdir(d)):
                if name.lower().endswith((".ttf", ".otf", ".ttc")):
                    candidates.append(os.path.join(d, name))
    candidates += [
        # Android
        "/system/fonts/NotoSansCJK-Regular.ttc",
        "/system/fonts/NotoSansSC-Regular.otf",
        "/system/fonts/NotoSansSC-Regular.ttf",
        "/system/fonts/NotoSansHans-Regular.otf",
        "/system/fonts/NotoSansCJK-Regular.otf",
        "/system/fonts/DroidSansFallback.ttf",
        "/system/fonts/DroidSansFallbackFull.ttf",
        "/system/fonts/HarmonyOS_Sans_SC_Regular.ttf",
        "/system/fonts/MiSansVF.ttf",
        # Windows
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyh.ttf",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        # Linux
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    # 兜底：扫描 /system/fonts 里名字带中文字体特征的文件（各家安卓 ROM 命名不同）
    try:
        for name in sorted(os.listdir("/system/fonts")):
            low = name.lower()
            if low.endswith((".ttf", ".otf", ".ttc")) and any(
                    k in low for k in ("cjk", "hans", "-sc", "sc-", "fallback", "misans", "harmony")):
                return os.path.join("/system/fonts", name)
    except Exception:
        pass
    return None


RULE_LINES = [
    "3~10人使用的牌数、地主人数、手牌数、底牌和先出方式按主菜单中的人数配置表执行。",
    "牌型：单牌、对子、三张、三带一、三带二、顺子、连对、飞机。",
    "飞机可裸出，也可带等量单牌或等量对子。",
    "四带二可带两张单牌或两对；四张同点数是炸弹；双王是火箭。",
    "顺子至少5张，不能包含2和王；连对至少3对。",
    "任意一名地主先出完，地主阵营获胜；任意一名农民先出完，农民阵营获胜。",
    "AI不会读取其他玩家手牌。AI输入只有自己的手牌和公开牌局信息。",
    "三人模式先发17张正式手牌后叫分，确定地主后把3张底牌固定交给地主。4~10人模式先发5张"
    "竞叫牌，叫分结束后这5张牌直接保留为正式手牌，再从剩余牌堆补足规则要求的数量，不回收、"
    "不替换、不重洗。",
]


class DouDiZhuUI(Widget):
    VW = 900            # 虚拟宽度；虚拟高度按屏幕比例在 1280~2000 之间取

    def __init__(self, **kw):
        super().__init__(**kw)
        self.settings = {"ascending": True, "lift": True}
        self.state = "menu"          # menu / players / difficulty / settings / rules / game
        self.num_players = None
        self.game = None
        self.buttons = []            # 当前画面的可点击区域 (x, y, w, h, action)
        self.dirty = True
        self.font = find_font()
        self._tex = {}
        self._cw = {}
        self._sig = None
        self._back_t = 0.0
        self.vh = 1600
        self.s = 1.0
        self.ox = 0.0
        self.oy = 0.0
        self._update_geometry()
        self.bind(size=self._on_resize, pos=self._on_resize)
        Window.bind(on_keyboard=self.on_key)
        Clock.schedule_interval(self.tick, 1 / 30.0)

    # ===================== 坐标与基本绘制 =====================
    def _update_geometry(self):
        W, H = self.size
        if W <= 0 or H <= 0:
            return
        self.vh = int(max(1280, min(2000, self.VW * H / float(W))))
        self.s = min(W / float(self.VW), H / float(self.vh))
        self.ox = self.x + (W - self.VW * self.s) / 2.0
        self.oy = self.y + (H - self.vh * self.s) / 2.0

    def _on_resize(self, *_):
        self._update_geometry()
        self._tex.clear()
        self._cw.clear()
        self.dirty = True

    def px(self, x):
        return self.ox + x * self.s

    def py(self, y):
        """虚拟坐标 y（向下增长）-> 屏幕 y（向上增长）"""
        return self.oy + (self.vh - y) * self.s

    def to_virtual(self, pos):
        return (pos[0] - self.ox) / self.s, self.vh - (pos[1] - self.oy) / self.s

    def fill(self, col, alpha=1.0):
        Color(*rgba(col, alpha))
        Rectangle(pos=self.pos, size=self.size)

    def rect(self, x, y, w, h, col, r=0, alpha=1.0):
        Color(*rgba(col, alpha))
        pos = (self.px(x), self.py(y + h))
        size = (w * self.s, h * self.s)
        if r:
            RoundedRectangle(pos=pos, size=size, radius=[min(r, w / 2.0, h / 2.0) * self.s])
        else:
            Rectangle(pos=pos, size=size)

    def outline(self, x, y, w, h, col, width=1, r=0):
        Color(*rgba(col))
        lw = max(1.0, width * self.s)
        if r:
            Line(rounded_rectangle=(self.px(x), self.py(y + h), w * self.s, h * self.s,
                                    min(r, w / 2.0, h / 2.0) * self.s), width=lw)
        else:
            Line(rectangle=(self.px(x), self.py(y + h), w * self.s, h * self.s), width=lw)

    def _texture(self, s, px_size):
        key = (s, px_size)
        tex = self._tex.get(key)
        if tex is None:
            if len(self._tex) > 900:
                self._tex.clear()
            kw = {"text": s, "font_size": px_size}
            if self.font:
                kw["font_name"] = self.font
            lab = CoreLabel(**kw)
            lab.refresh()
            tex = lab.texture
            self._tex[key] = tex
        return tex

    def text(self, s, size, x, y, col=WHITE, center=False):
        """size 用虚拟像素；center=True 以 (x,y) 为中心，否则 (x,y) 为左上角。"""
        s = str(s)
        if not s.strip():
            return 0
        px_size = max(8, int(round(size * self.s)))
        tex = self._texture(s, px_size)
        if tex is None:
            return 0
        tw, th = tex.size
        if center:
            rx, ry = self.px(x) - tw / 2.0, self.py(y) - th / 2.0
        else:
            rx, ry = self.px(x), self.py(y) - th
        Color(*rgba(col))
        Rectangle(texture=tex, pos=(round(rx), round(ry)), size=(tw, th))
        return tw / self.s

    def char_w(self, ch, size):
        key = (ch, size)
        w = self._cw.get(key)
        if w is None:
            if ch == " ":
                w = size * 0.3
            else:
                tex = self._texture(ch, max(8, int(round(size * self.s))))
                w = (tex.width / self.s) if tex is not None else size
            self._cw[key] = w
        return w

    def wrap(self, s, size, max_w):
        lines, cur, cw = [], "", 0.0
        for ch in s:
            w = self.char_w(ch, size)
            if cur and cw + w > max_w:
                lines.append(cur)
                cur, cw = ch, w
            else:
                cur += ch
                cw += w
        if cur:
            lines.append(cur)
        return lines

    def button(self, x, y, w, h, label, action=None, enabled=True, selected=False):
        col = GOLD if selected else (BLUE if enabled else GRAY)
        self.rect(x, y, w, h, col, 14)
        self.outline(x, y, w, h, WHITE, 2, 14)
        self.text(label, 36 if len(label) <= 5 else 28, x + w / 2.0, y + h / 2.0,
                  BLACK if enabled else LIGHT, True)
        if action is not None:
            self.buttons.append((x, y, w, h, action))

    def card(self, c, x, y, w, h, selected=False):
        # 显示永远由 UID 还原真实牌面，和原版一致
        c = canonical_card(c)
        sy = y - 34 if selected else y
        self.rect(x + 3, sy + 4, w, h, CARD_SHADOW, 8)
        self.rect(x, sy, w, h, CARD, 8)
        red = c["suit"] in ("♥", "♦") or "王" in c["rank"]
        col = RED if red else BLACK
        self.outline(x, sy, w, h, GOLD if selected else CARD_EDGE, 3 if selected else 1, 8)
        if c["rank"] in ("小王", "大王"):
            self.text(c["rank"], 22, x + w / 2.0, sy + h / 2.0, col, True)
        else:
            self.text(c["rank"], 22, x + 5, sy + 5, col)
            self.text(c["suit"], 36, x + w / 2.0, sy + h / 2.0 + 7, col, True)

    # ===================== 页面切换 =====================
    def goto(self, state):
        self.state = state
        self.dirty = True

    def start_game(self, difficulty):
        self.game = Game(self.num_players, difficulty, self.settings)
        self._sig = None
        self.goto("game")

    # ===================== 菜单类页面 =====================
    def screen_menu(self):
        VW = self.VW
        self.fill(BG_DARK)
        self.text("斗地主", 70, VW / 2.0, 180, GOLD, True)
        self.text("Kivy 版", 28, VW / 2.0, 265, WHITE, True)
        bw = 460
        x = (VW - bw) / 2.0
        self.button(x, 420, bw, 90, "开始游戏", lambda: self.goto("players"))
        self.button(x, 545, bw, 90, "设置", lambda: self.goto("settings"))
        self.button(x, 670, bw, 90, "规则", lambda: self.goto("rules"))
        self.text(VERSION, 22, VW / 2.0, self.vh - 80, LIGHT, True)

    def screen_players(self):
        VW = self.VW
        self.fill(BG_DARK)
        self.text("选择游戏人数", 52, VW / 2.0, 95, GOLD, True)
        self.text("人数决定牌数、地主人数、手牌与底牌分配", 28, VW / 2.0, 155, WHITE, True)
        bw = (VW - 70) // 2
        bh = 138
        for i, n in enumerate(range(3, 11)):
            col, row = i % 2, i // 2
            x = 20 + col * (bw + 30)
            y = 205 + row * 150
            rule = PLAYER_RULES[n]
            self.rect(x, y, bw, bh, PANEL, 14)
            self.outline(x, y, bw, bh, BLUE, 2, 14)
            self.text(f"{n}人", 36, x + 14, y + 12, GOLD)
            self.text(f"{rule['decks']}副牌 · {rule['decks'] * 54}张", 22, x + 14, y + 55)
            self.text(f"{rule['landlords']}地主 vs {rule['farmers']}农民", 22, x + 14, y + 82)
            if rule["bottom"]:
                if rule["bottom_mode"] in ("all_primary", "primary"):
                    btxt = f"底牌{rule['bottom']}张 → 主地主"
                else:
                    btxt = f"底牌{rule['bottom']}张 → 地主平分"
            else:
                btxt = "无底牌"
            self.text(btxt, 22, x + 14, y + 108, LIGHT)
            self.buttons.append((x, y, bw, bh, lambda n=n: self._pick_players(n)))
        self.button(25, self.vh - 125, 180, 75, "返回", lambda: self.goto("menu"))

    def _pick_players(self, n):
        self.num_players = n
        self.goto("difficulty")

    def screen_difficulty(self):
        VW = self.VW
        self.fill(BG_DARK)
        self.text("选择 AI 难度", 52, VW / 2.0, 135, GOLD, True)
        self.text(f"已选择：{self.num_players}人", 36, VW / 2.0, 205, WHITE, True)
        bw = 500
        x = (VW - bw) / 2.0
        for y, d in ((340, "简单"), (480, "普通"), (620, "困难")):
            self.button(x, y, bw, 100, d, lambda d=d: self.start_game(d))
        self.text("简单：随机与基础规则   普通：节省牌力   困难：考虑公开牌数与阵营目标",
                  22, VW / 2.0, 770, LIGHT, True)
        self.button(25, self.vh - 125, 180, 75, "返回", lambda: self.goto("players"))

    def screen_settings(self):
        VW = self.VW
        st = self.settings
        self.fill(BG_DARK)
        self.text("设置", 52, VW / 2.0, 140, GOLD, True)
        bx = VW - 280
        self.text("牌面排序", 36, 60, 340)
        self.button(bx, 325, 220, 75, "升序" if st["ascending"] else "降序",
                    lambda: st.__setitem__("ascending", not st["ascending"]))
        self.text("选中牌上移", 36, 60, 465)
        self.button(bx, 450, 220, 75, "开启" if st["lift"] else "关闭",
                    lambda: st.__setitem__("lift", not st["lift"]), st["lift"])
        self.text("当前版本重点：手机触控、多人规则、牌型、AI信息隔离、出牌动画", 22, 60, 600, LIGHT)
        self.button(25, self.vh - 125, 180, 75, "返回", lambda: self.goto("menu"))

    def screen_rules(self):
        VW = self.VW
        self.fill(BG_DARK)
        self.text("规则", 52, VW / 2.0, 70, GOLD, True)
        y = 150
        for line in RULE_LINES:
            self.text("•", 26, 30, y)
            for seg in self.wrap(line, 26, VW - 84):
                self.text(seg, 26, 54, y)
                y += 38
            y += 24
        self.button(25, self.vh - 125, 180, 75, "返回", lambda: self.goto("menu"))

    # ===================== 手牌布局（与原版一致） =====================
    def hand_positions(self, n, y):
        VW = self.VW
        if n <= 17:
            w, h = 78, 116
            gap = min(62, max(42, (VW - 40 - w) // max(1, n - 1)))
        elif n <= 25:
            w, h = 62, 104
            gap = min(45, max(25, (VW - 36 - w) // max(1, n - 1)))
        else:
            w, h = 54, 94
            gap = min(35, max(19, (VW - 30 - w) // max(1, n - 1)))
        total = w + gap * max(0, n - 1)
        x0 = (VW - total) // 2
        return [(x0 + i * gap, y, w, h) for i in range(n)]

    def player_hand_layout(self, g):
        n = len(g.hands[0])
        if n <= 25:
            return [(i,) + t for i, t in enumerate(self.hand_positions(n, self.vh - 355))]
        split = (n + 1) // 2
        a = self.hand_positions(split, self.vh - 405)
        b = self.hand_positions(n - split, self.vh - 290)
        return ([(i,) + t for i, t in enumerate(a)] +
                [(split + i,) + t for i, t in enumerate(b)])

    def hit_my_hand(self, g, vx, vy):
        """每张牌只有一个点击区域：按相邻牌中心切分，一次点击只会命中一张。"""
        layout = self.player_hand_layout(g)
        if not layout:
            return None
        rows = {}
        for item in layout:
            rows.setdefault(item[2], []).append(item)
        for row_y, items in rows.items():
            top = row_y - 48
            bottom = row_y + max(i[4] for i in items) + 16
            if not (top <= vy <= bottom):
                continue
            items = sorted(items, key=lambda z: z[1])
            centers = [x + w / 2.0 for _, x, _, w, _ in items]
            for j, item in enumerate(items):
                left = -1e9 if j == 0 else (centers[j - 1] + centers[j]) / 2.0
                right = 1e9 if j == len(items) - 1 else (centers[j] + centers[j + 1]) / 2.0
                if left <= vx <= right:
                    return item[0]
        return None

    def draw_my_hand(self, g):
        lift = self.settings.get("lift", True)
        for idx, x, y, w, h in self.player_hand_layout(g):
            self.card(g.hands[0][idx], x, y, w, h, lift and idx in g.selected)

    # ===================== 叫分页面 =====================
    def screen_bid(self, g):
        VW, vh = self.VW, self.vh
        self.fill(BG_DARK)
        self.text(f"{g.num_players}人斗地主", 52, 25, 25)
        rule = g.rule
        self.text(f"{rule['decks']}副牌 · {rule['decks'] * 54}张  |  "
                  f"{rule['landlords']}地主 vs {rule['farmers']}农民", 28, 25, 88)
        self.text("固定发牌：已发到玩家手里的牌不会被收回、替换或重洗", 22, 25, 125, GOLD)

        cols = 2 if g.num_players <= 6 else 3
        cell_w = (VW - 60) // cols
        for i in range(g.num_players):
            row, col = i // cols, i % cols
            x = 20 + col * cell_w
            y = 175 + row * 115
            self.rect(x, y, cell_w - 12, 95, PANEL, 12)
            if i == g.current:
                self.outline(x, y, cell_w - 12, 95, GOLD, 3, 12)
            self.text(f"玩家{i + 1}", 28, x + 12, y + 10)
            bid = g.bid_values[i]
            self.text("未叫" if bid is None else ("不叫" if bid == 0 else f"{bid}分"),
                      22, x + 12, y + 48)
            self.text(f"已发 {len(g.bid_hands[i])} 张", 22, x + cell_w - 125, y + 48, LIGHT)

        self.text("我的固定手牌", 36, 20, vh - 430, GOLD)
        hand = g.bid_hands[0]
        for c, (x, y, w, h) in zip(hand, self.hand_positions(len(hand), vh - 355)):
            self.card(c, x, y, w, h)

        if g.current == 0:
            high = g.highest_bid()
            bw, gap = 145, 20
            x0 = (VW - (4 * bw + 3 * gap)) / 2.0
            for i, (label, point) in enumerate((("1分", 1), ("2分", 2), ("3分", 3), ("不叫", 0))):
                ok = point == 0 or point > high      # 叫分必须高于当前最高分
                self.button(x0 + i * (bw + gap), vh - 130, bw, 78, label,
                            (lambda p=point: g.do_bid(0, p)) if ok else None, ok)
        else:
            self.text("等待AI叫分……", 36, VW / 2.0, vh - 90, GOLD, True)

    # ===================== 牌局页面 =====================
    def grid_cell(self, g, p):
        """其他玩家信息框 (x, y, w, h)"""
        others = g.num_players - 1
        cols = min(5, max(2, others))
        cell_w = (self.VW - 40) // cols
        i = p - 1
        return (20 + (i % cols) * cell_w, 112 + (i // cols) * 100, cell_w - 10, 86)

    def draw_player_grid(self, g):
        for p in range(1, g.num_players):
            x, y, w, h = self.grid_cell(g, p)
            self.rect(x, y, w, h, PANEL2, 10)
            if p == g.primary:
                role = "主地主"
            elif p in g.landlords:
                role = "地主"
            else:
                role = "农民"
            self.text(f"玩家{p + 1}", 28, x + 10, y + 8)
            self.text(role, 22, x + 10, y + 43, GOLD if p in g.landlords else LIGHT)
            self.text(f"{len(g.hands[p])}张", 22, x + w - 62, y + 45)
            if p == g.current:
                self.outline(x, y, w, h, GOLD, 3, 10)

    def draw_bottom(self, g):
        if not g.bottom:
            return
        VW = self.VW
        self.rect(VW - 250, 20, 230, 90, PANEL, 12)
        self.text("底牌", 22, VW - 235, 30)
        if len(g.bottom) > 4:
            self.text(f"共{len(g.bottom)}张", 22, VW - 60, 30, LIGHT)
        for i, c in enumerate(g.bottom[:4]):
            self.card(c, VW - 235 + i * 52, 55, 46, 62)

    def draw_last_play(self, g, extra, cy):
        VW = self.VW
        area_w = VW - 40
        self.rect(20, 350, area_w, 310 + extra, PANEL, 18)
        if not g.last_play:
            self.text("出牌区", 36, VW / 2.0, 380, LIGHT, True)
            self.text(f"等待玩家{g.current + 1}出牌", 28, VW / 2.0, cy + 70, LIGHT, True)
            return
        self.text(f"玩家{g.last_player + 1} · {TYPE_NAMES[g.last_info['type']]}",
                  36, VW / 2.0, 375, GOLD, True)
        cards = g.last_play
        maxw = 70 if len(cards) <= 12 else 48
        gap = min(maxw - 8, max(24, (area_w - maxw) // max(1, len(cards) - 1)))
        total = maxw + gap * max(0, len(cards) - 1)
        x0 = (VW - total) // 2
        h = 105 if len(cards) <= 12 else 88
        for i, c in enumerate(cards):
            self.card(c, x0 + i * gap, cy, maxw, h)

    def player_anchor(self, g, p):
        if p == 0:
            return self.VW // 2, self.vh - 400
        x, y, w, h = self.grid_cell(g, p)
        return x + w // 2, y + h // 2

    def screen_play(self, g, actions=True):
        VW, vh = self.VW, self.vh
        # 信息条紧贴在手牌上方；屏幕越高，出牌区越大（原版是写死的 675）
        extra = max(0, vh - 1239)
        cy = 430 + int(extra * 0.35)           # 出牌区里牌的纵向位置
        self.fill(BG)
        self.rect(0, 0, VW, 100, BG_DARK)
        self.text(f"{g.num_players}人斗地主", 52, 20, 12)
        self.text(g.message, 22, 310, 28)
        self.draw_player_grid(g)
        self.draw_bottom(g)
        self.draw_last_play(g, extra, cy)

        self.rect(20, 675 + extra, VW - 40, 55, PANEL2, 12)
        role = "主地主" if g.primary == 0 else ("地主" if 0 in g.landlords else "农民")
        self.text(f"我：{role}   剩余 {len(g.hands[0])} 张", 28, 32, 687 + extra,
                  GOLD if 0 in g.landlords else WHITE)
        self.text(f"当前：玩家{g.current + 1}", 28, VW - 250, 687 + extra,
                  GOLD if g.current == 0 else LIGHT)
        self.text("我的手牌", 36, 20, 735 + extra)
        self.draw_my_hand(g)

        by = vh - 105
        if not actions:
            pass
        elif g.current == 0:
            live = not g.animation
            bw, gap = 145, 15
            x0 = (VW - (4 * bw + 3 * gap)) / 2.0
            acts = (("出牌", self.human_play), ("不出", lambda: g.pass_play(0)),
                    ("提示", lambda: hint_for_player(g)), ("清空", lambda: g.selected.clear()))
            for i, (label, act) in enumerate(acts):
                self.button(x0 + i * (bw + gap), by, bw, 72, label, act if live else None)
        else:
            self.text("等待其他玩家行动……", 28, 25, by + 22, LIGHT)

        if g.animation:                         # 出牌动画：牌从出牌者飞向出牌区
            a = g.animation
            t = min(1.0, a["t"] / a["duration"])
            sx, sy = self.player_anchor(g, a["player"])
            tx, ty = VW // 2, cy + 40
            e = 1 - (1 - t) * (1 - t)           # ease-out
            ax, ay = sx + (tx - sx) * e, sy + (ty - sy) * e
            cards = a["cards"]
            w, gap = 52, 38
            total = w + gap * max(0, len(cards) - 1)
            x0 = int(ax - total / 2)
            for i, c in enumerate(cards):
                self.card(c, x0 + i * gap, int(ay), w, 82)

    def human_play(self):
        g = self.game
        cards = [g.hands[0][i] for i in sorted(g.selected)]
        g.play(0, cards)

    def screen_over(self, g):
        VW, vh = self.VW, self.vh
        self.screen_play(g, actions=False)      # 结算页底部只留“再来一局/返回主菜单”
        self.fill((0, 0, 0), 160 / 255.0)
        title = "地主阵营获胜" if g.winner in g.landlords else "农民阵营获胜"
        self.text(title, 70, VW / 2.0, vh / 2.0 - 100, GOLD, True)
        self.text(f"玩家{g.winner + 1}率先出完", 36, VW / 2.0, vh / 2.0, WHITE, True)
        x0 = (VW - 530) / 2.0
        self.button(x0, vh - 130, 250, 78, "再来一局", g.new_round)
        self.button(x0 + 280, vh - 130, 250, 78, "返回主菜单", lambda: self.goto("menu"))

    # ===================== 重绘 / 主循环 =====================
    def redraw(self):
        self.canvas.clear()
        self.buttons = []
        with self.canvas:
            st = self.state
            if st == "menu":
                self.screen_menu()
            elif st == "players":
                self.screen_players()
            elif st == "difficulty":
                self.screen_difficulty()
            elif st == "settings":
                self.screen_settings()
            elif st == "rules":
                self.screen_rules()
            elif st == "game" and self.game is not None:
                g = self.game
                if g.phase == "bid":
                    self.screen_bid(g)
                elif g.phase == "play":
                    self.screen_play(g)
                else:
                    self.screen_over(g)

    def _signature(self, g):
        return (g.phase, g.current, g.message, g.round_no, tuple(sorted(g.selected)),
                tuple(len(h) for h in g.hands), tuple(len(h) for h in g.bid_hands),
                tuple(g.bid_values), g.last_player, len(g.last_play),
                self.settings.get("lift", True))

    def tick(self, dt):
        dt = min(dt, 0.1)
        if self.state == "game" and self.game is not None:
            g = self.game
            # AI 叫分
            if g.phase == "bid" and g.current != 0:
                g.ai_timer += dt
                if g.ai_timer >= 0.55:
                    g.ai_timer = 0
                    g.do_bid(g.current, ai_bid(g.bid_hands[g.current], public_state(g)))
            # AI 出牌
            if g.phase == "play" and g.current != 0 and not g.animation:
                g.ai_timer += dt
                if g.ai_timer >= 0.65:
                    g.ai_timer = 0
                    p = g.current
                    cards = choose_ai_play(g.hands[p], public_state(g))
                    if cards:
                        g.play(p, cards)
                    else:
                        g.pass_play(p)
            g.update(dt)
            sig = self._signature(g)
            if sig != self._sig or g.animation:
                self._sig = sig
                self.dirty = True
        if self.dirty:
            self.dirty = False
            self.redraw()

    # ===================== 输入 =====================
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        vx, vy = self.to_virtual(touch.pos)
        for x, y, w, h, action in reversed(self.buttons):
            if x <= vx <= x + w and y <= vy <= y + h:
                self.buttons = []               # 等下一次重绘再登记，避免连点误触旧按钮
                action()
                self.dirty = True
                return True
        g = self.game
        if self.state == "game" and g is not None and g.phase == "play":
            if g.current == 0 and not g.animation:
                idx = self.hit_my_hand(g, vx, vy)
                if idx is not None:
                    if idx in g.selected:
                        g.selected.remove(idx)
                    else:
                        g.selected.add(idx)
                    self.dirty = True
        return True

    def on_key(self, window, key, *args):
        """安卓返回键 / 电脑 Esc：逐级返回；牌局中需要连按两次，防误触。"""
        if key != 27:
            return False
        st = self.state
        if st == "game":
            g = self.game
            if g is None or g.phase == "over" or time.time() - self._back_t < 2.0:
                self.goto("menu")
            else:
                self._back_t = time.time()
                g.message = "再按一次返回键退出本局"
                self.dirty = True
            return True
        if st == "difficulty":
            self.goto("players")
            return True
        if st in ("players", "settings", "rules"):
            self.goto("menu")
            return True
        return False                            # 主菜单：交给系统退出程序


class DouDiZhuApp(App):
    title = "斗地主"

    def build(self):
        Window.clearcolor = rgba(BG_DARK)
        return DouDiZhuUI()

    def on_pause(self):
        return True                             # 安卓切后台时不销毁程序


if __name__ == "__main__":
    DouDiZhuApp().run()
