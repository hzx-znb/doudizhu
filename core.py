# -*- coding: utf-8 -*-
"""
斗地主 · 游戏逻辑核心（与界面无关，纯 Python，不依赖 pygame / kivy）

由 doudizhu_pydroid3_V1_5.py 拆分而来：规则配置、牌型判定、AI、牌局状态机。
界面层（main.py）只负责显示和触控，所有规则都在这里。
"""

import random
import itertools


# ------------------------- 规则配置 -------------------------
# 人数: 用牌数, 地主数, 农民数, 每个农民最终手牌, 每个地主基础手牌,
#       底牌数, 底牌分配方式, 先出方式
PLAYER_RULES = {
    3: {"decks": 1, "landlords": 1, "farmers": 2, "farmer_cards": 17, "landlord_base": 17, "bottom": 3, "bottom_mode": "all_primary", "first": "landlord", "bidding_mode": "standard_17"},
    4: {"decks": 2, "landlords": 1, "farmers": 3, "farmer_cards": 25, "landlord_base": 25, "bottom": 8, "bottom_mode": "all_primary", "first": "landlord", "bidding_mode": "preview_5"},
    5: {"decks": 2, "landlords": 2, "farmers": 3, "farmer_cards": 20, "landlord_base": 20, "bottom": 8, "bottom_mode": "split_landlords", "first": "primary", "bidding_mode": "preview_5"},
    6: {"decks": 3, "landlords": 2, "farmers": 4, "farmer_cards": 24, "landlord_base": 30, "bottom": 6, "bottom_mode": "split_landlords", "first": "primary", "bidding_mode": "preview_5"},
    7: {"decks": 3, "landlords": 3, "farmers": 4, "farmer_cards": 21, "landlord_base": 22, "bottom": 12, "bottom_mode": "split_landlords", "first": "primary", "bidding_mode": "preview_5"},
    8: {"decks": 3, "landlords": 3, "farmers": 5, "farmer_cards": 18, "landlord_base": 24, "bottom": 0, "bottom_mode": "none", "first": "primary", "bidding_mode": "preview_5"},
    9: {"decks": 3, "landlords": 4, "farmers": 5, "farmer_cards": 16, "landlord_base": 20, "bottom": 2, "bottom_mode": "primary", "first": "primary", "bidding_mode": "preview_5"},
    10: {"decks": 4, "landlords": 4, "farmers": 6, "farmer_cards": 20, "landlord_base": 24, "bottom": 0, "bottom_mode": "none", "first": "primary", "bidding_mode": "preview_5"},
}

SUITS = ["♠", "♥", "♣", "♦"]
RANKS = ["3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2"]
VALUE = {r: i + 3 for i, r in enumerate(RANKS)}
VALUE.update({"小王": 16, "大王": 17})

TYPE_NAMES = {
    "single":"单牌", "pair":"对子", "triple":"三张", "triple_single":"三带一",
    "triple_pair":"三带二", "straight":"顺子", "pair_straight":"连对",
    "plane":"飞机", "plane_single":"飞机带单", "plane_pair":"飞机带对",
    "four_two_single":"四带二", "four_two_pair":"四带两对",
    "bomb":"炸弹", "rocket":"火箭",
}

# ------------------------- 牌 -------------------------
def make_deck(decks=1):
    deck = []
    uid = 0
    for d in range(decks):
        for suit in SUITS:
            for rank in RANKS:
                deck.append({"rank": rank, "suit": suit, "uid": uid})
                uid += 1
        deck.append({"rank": "小王", "suit": "", "uid": uid}); uid += 1
        deck.append({"rank": "大王", "suit": "", "uid": uid}); uid += 1
    return deck

def card_from_uid(uid):
    """根据唯一UID重新得到标准牌面。
    UID是整局牌的唯一身份，不依赖运行过程中可能被误改的rank/suit字段。
    """
    uid = int(uid)
    local = uid % 54
    if local < 52:
        suit_i, rank_i = divmod(local, 13)
        return {"rank": RANKS[rank_i], "suit": SUITS[suit_i], "uid": uid}
    return {"rank": "小王" if local == 52 else "大王", "suit": "", "uid": uid}

def canonical_card(c):
    """UID 是实体牌的唯一身份；牌面始终由 UID 决定。"""
    uid = int(c["uid"])
    local = uid % 54
    if local < 52:
        suit_i, rank_i = divmod(local, 13)
        return {"rank": RANKS[rank_i], "suit": SUITS[suit_i], "uid": uid}
    return {"rank": "小王" if local == 52 else "大王", "suit": "", "uid": uid}

def canonicalize_hand(hand):
    # 仅生成用于计算的只读副本；绝不写回 self.hands。
    return [canonical_card(c) for c in hand]

def card_value(c):
    """返回实体牌的点数。所有逻辑均以标准牌面为准，不修改原牌对象。"""
    cc = canonical_card(c)
    return VALUE[cc["rank"]]


def sort_cards(cards):
    """只返回排序后的新列表，不改变调用方手牌对象或牌的归属。"""
    return sorted(
        (canonical_card(c) for c in cards),
        key=lambda c: (card_value(c), SUITS.index(c["suit"]) if c["suit"] in SUITS else 4, c["uid"])
    )


def count_ranks(cards):
    d = {}
    for c in cards:
        d[c["rank"]] = d.get(c["rank"], 0) + 1
    return d

def consecutive(vals):
    vals = sorted(vals)
    return len(vals) == len(set(vals)) and all(vals[i] + 1 == vals[i+1] for i in range(len(vals)-1))

def normal_sequence(vals):
    return all(v <= VALUE["A"] for v in vals) and consecutive(vals)

# ------------------------- 牌型分析 -------------------------
def analyze(cards):
    if not cards:
        return None
    cards = sort_cards(cards)
    n = len(cards)
    cnt = count_ranks(cards)
    values = sorted(VALUE[r] for r in cnt)

    if n == 1:
        return {"type":"single","main":card_value(cards[0]),"length":1}
    if n == 2:
        rs = [c["rank"] for c in cards]
        if rs[0] == rs[1]:
            return {"type":"pair","main":VALUE[rs[0]],"length":1}
        if set(rs) == {"小王","大王"}:
            return {"type":"rocket","main":100,"length":1}
        return None
    if n == 3 and len(cnt) == 1:
        return {"type":"triple","main":values[0],"length":1}
    if n == 4 and len(cnt) == 1:
        return {"type":"bomb","main":values[0],"length":1}

    # 三带一
    if n == 4 and sorted(cnt.values()) == [1,3]:
        r = next(r for r,v in cnt.items() if v == 3)
        return {"type":"triple_single","main":VALUE[r],"length":1}

    # 三带二
    if n == 5 and sorted(cnt.values()) == [2,3]:
        r = next(r for r,v in cnt.items() if v == 3)
        return {"type":"triple_pair","main":VALUE[r],"length":1}

    # 顺子
    if n >= 5 and len(cnt) == n and normal_sequence(values):
        return {"type":"straight","main":values[-1],"length":n}

    # 连对
    if n >= 6 and n % 2 == 0 and all(v == 2 for v in cnt.values()):
        if normal_sequence(values):
            return {"type":"pair_straight","main":values[-1],"length":len(values)}

    # 飞机系列：至少2个连续三张；2、王不能作为飞机核心
    triples = sorted([VALUE[r] for r,v in cnt.items() if v >= 3 and VALUE[r] <= VALUE["A"]])
    for start in range(len(triples)):
        for end in range(start+2, len(triples)+1):
            seq = triples[start:end]
            if not consecutive(seq):
                continue
            k = len(seq)
            # 核心三张数量至少3k，剩余必须正好是k张单/2k张且牌型能解释
            if n not in (3*k, 4*k, 5*k):
                continue
            # 确认每个核心点数至少3张
            if not all(cnt[next(r for r in cnt if VALUE[r] == v)] >= 3 for v in seq):
                continue
            # 不能因为另一个三张点数混进来而产生歧义；合法组合仍按剩余牌判断
            core_ranks = [next(r for r in cnt if VALUE[r] == v) for v in seq]
            core_ids = set()
            for r in core_ranks:
                # 取三张UID作为核心
                cs = [c for c in cards if c["rank"] == r][:3]
                core_ids.update(c["uid"] for c in cs)
            remain = [c for c in cards if c["uid"] not in core_ids]
            if n == 3*k and not remain:
                return {"type":"plane","main":seq[-1],"length":k}
            if n == 4*k and len(remain) == k:
                return {"type":"plane_single","main":seq[-1],"length":k}
            if n == 5*k and len(remain) == 2*k:
                rc = count_ranks(remain)
                if all(v == 2 for v in rc.values()):
                    return {"type":"plane_pair","main":seq[-1],"length":k}

    # 四带二
    fours = [r for r,v in cnt.items() if v == 4]
    if n == 6 and len(fours) == 1:
        return {"type":"four_two_single","main":VALUE[fours[0]],"length":1}
    if n == 8 and len(fours) == 1:
        pairs = [v for v in cnt.values() if v == 2]
        if len(pairs) == 2:
            return {"type":"four_two_pair","main":VALUE[fours[0]],"length":1}
    return None

def can_beat(new_info, old_info):
    if new_info is None:
        return False
    if old_info is None:
        return True
    if new_info["type"] == "rocket":
        return True
    if old_info["type"] == "rocket":
        return False
    if new_info["type"] == "bomb" and old_info["type"] != "bomb":
        return True
    if old_info["type"] == "bomb" and new_info["type"] != "bomb":
        return False
    return (new_info["type"] == old_info["type"] and
            new_info["length"] == old_info["length"] and
            new_info["main"] > old_info["main"])

# ------------------------- AI -------------------------
def group_by_rank(hand):
    d = {}
    for c in sort_cards(hand):
        d.setdefault(c["rank"], []).append(c)
    return d

def add_candidate(dic, cards):
    info = analyze(cards)
    if info is None:
        return
    key = (info["type"], info["main"], info["length"], tuple(sorted(c["uid"] for c in cards)))
    dic[key] = sort_cards(cards)

def generate_candidates(hand, limit=1800):
    hand = sort_cards(hand)
    groups = group_by_rank(hand)
    ranks = sorted(groups, key=lambda r: VALUE[r])
    out = {}

    for r in ranks:
        cs = groups[r]
        add_candidate(out, cs[:1])
        if len(cs) >= 2: add_candidate(out, cs[:2])
        if len(cs) >= 3: add_candidate(out, cs[:3])
        if len(cs) == 4: add_candidate(out, cs[:4])

    normal = [r for r in ranks if VALUE[r] <= VALUE["A"]]
    for i in range(len(normal)):
        for j in range(i+5, len(normal)+1):
            part = normal[i:j]
            if consecutive([VALUE[r] for r in part]):
                add_candidate(out, [groups[r][0] for r in part])

    pair_ranks = [r for r in normal if len(groups[r]) >= 2]
    for i in range(len(pair_ranks)):
        for j in range(i+3, len(pair_ranks)+1):
            part = pair_ranks[i:j]
            if consecutive([VALUE[r] for r in part]):
                add_candidate(out, sum(([groups[r][0], groups[r][1]] for r in part), []))

    triples = [r for r in ranks if len(groups[r]) >= 3]
    for tr in triples:
        for r in ranks:
            if r == tr: continue
            add_candidate(out, groups[tr][:3] + groups[r][:1])
            if len(groups[r]) >= 2:
                add_candidate(out, groups[tr][:3] + groups[r][:2])

    tv = sorted(set(VALUE[r] for r in triples if VALUE[r] <= VALUE["A"]))
    for i in range(len(tv)):
        for j in range(i+2, len(tv)+1):
            seq = tv[i:j]
            if not consecutive(seq): continue
            core_ranks = [next(r for r in triples if VALUE[r] == v) for v in seq]
            core = []
            ids = set()
            for r in core_ranks:
                core += groups[r][:3]
                ids.update(c["uid"] for c in groups[r][:3])
            add_candidate(out, core)
            remain = [c for c in hand if c["uid"] not in ids]
            k = len(seq)
            # 低组合优先，限制组合数
            for wing in itertools.islice(itertools.combinations(remain, k), 0, 80):
                add_candidate(out, core + list(wing))
            pair_opts = []
            for r in ranks:
                left = [c for c in remain if c["rank"] == r]
                if len(left) >= 2:
                    pair_opts.append(left[:2])
            for pair_sel in itertools.islice(itertools.combinations(pair_opts, k), 0, 80):
                wings = []
                for pair in pair_sel: wings.extend(pair)
                add_candidate(out, core + wings)
            if len(out) >= limit: return list(out.values())

    for r in ranks:
        if len(groups[r]) == 4:
            four = groups[r]
            remain = [c for c in hand if c["uid"] not in {x["uid"] for x in four}]
            for pair in itertools.islice(itertools.combinations(remain, 2), 0, 80):
                add_candidate(out, four + list(pair))
            prs = [x for x in ranks if x != r and len(groups[x]) >= 2]
            for a,b in itertools.islice(itertools.combinations(prs, 2), 0, 30):
                add_candidate(out, four + groups[a][:2] + groups[b][:2])
            if len(out) >= limit: break
    return list(out.values())

def public_state(g):
    """AI只收到公开信息；绝不包含任何其他玩家的牌面。"""
    return {
        "difficulty": g.difficulty,
        "current": g.current,
        "landlords": tuple(g.landlords),
        "primary": g.primary,
        "last_info": dict(g.last_info) if g.last_info else None,
        "last_player": g.last_player,
        "hand_counts": tuple(len(h) for h in g.hands),
        "players": g.num_players,
        "bid_values": tuple(g.bid_values),
        "highest_bid": g.highest_bid(),
        "my_team": ("landlord" if g.current in g.landlords else "farmer"),
    }

def same_team_public(public, a, b):
    landlords = set(public.get("landlords", ()))
    return (a in landlords) == (b in landlords)

# 叫分评估。
# 原版把 max(点数) + 炸弹*9 + 王*7 + ... 的总和拿去对 66/72/84… 之类的阈值，
# 但一手 17 张牌这个总和平均只有 ~37，5 张竞叫牌最多也只有 ~45，
# 阈值根本够不着，于是普通/困难 AI 几乎永远选“不叫”。
# 这里改成：先算“牌力值”，再用按实际发牌分布标定过的阈值换算叫分。
BID_THRESHOLDS = {
    # 手牌张数 >= 12（3人17张正式手牌）：(叫1分, 叫2分, 叫3分) 的最低牌力
    "full":    (9.5, 12.5, 15.0),
    # 4~10人的5张竞叫牌
    "preview": (2.0, 3.5, 5.0),
}
# 给牌力加随机扰动，让低难度 AI 更“凭感觉”，困难 AI 稳定按牌力叫。
BID_NOISE = {
    "full":    {"简单": 2.5, "普通": 1.0, "困难": 0.0},
    "preview": {"简单": 1.2, "普通": 0.5, "困难": 0.0},
}

def bid_hand_value(hand):
    """粗略估计一手牌的叫地主价值：王、2、炸弹是主要来源。"""
    cnt = count_ranks(hand)
    big = cnt.get("大王", 0)
    small = cnt.get("小王", 0)
    v = big * 4 + small * 3 + 2 * min(big, small)   # 双王有火箭加成
    v += cnt.get("2", 0) * 2 + cnt.get("A", 0) * 1.0 + cnt.get("K", 0) * 0.5
    for r, n in cnt.items():
        if r in ("小王", "大王"):
            continue
        if n == 4:
            v += 6      # 炸弹
        elif n == 3:
            v += 1.5
        elif n == 2:
            v += 0.5
    return v

def ai_bid(hand, public):
    """AI竞叫只读取自己的竞叫牌 + 已公开的最高叫分。
    4~10人的5张竞叫牌在地主确定后直接并入正式手牌；3人的17张竞叫牌本身就是正式手牌。
    """
    kind = "full" if len(hand) >= 12 else "preview"
    t1, t2, t3 = BID_THRESHOLDS[kind]
    d = public["difficulty"]
    power = bid_hand_value(hand) + random.gauss(0, BID_NOISE[kind].get(d, 0.0))

    if power >= t3:
        desired = 3
    elif power >= t2:
        desired = 2
    elif power >= t1:
        desired = 1
    else:
        desired = 0

    # 叫分必须严格高于当前最高叫分，否则只能不叫。
    highest = public.get("highest_bid", 0)
    if desired <= highest:
        return 0
    return desired

def candidate_cost(cards):
    info = analyze(cards)
    if not info: return 99999
    s = sum(card_value(c) for c in cards)/max(1,len(cards))
    if info["type"] == "bomb": s += 25
    if info["type"] == "rocket": s += 60
    return s

def choose_ai_play(hand, public):
    """阵营感知AI：
    - AI只能读取自己的hand；
    - 通过public中的landlords/hand_counts/last_play判断盟友和敌人；
    - 通常不压盟友；
    - 只有在明显有利于本阵营（例如自己能直接走完、敌方接近出完、
      或自己能用低代价强制接管牌权）时，才允许压盟友。
    """
    candidates = generate_candidates(hand)
    if not candidates:
        return []
    last = public["last_info"]
    last_player = public["last_player"]
    me = public["current"]
    landlords = set(public.get("landlords", ()))

    if last is None or last_player == me:
        playable = candidates
    else:
        playable = [c for c in candidates if can_beat(analyze(c), last)]
        if not playable:
            return []

        # 盟友出牌：默认让盟友继续，避免“自己人互相抢牌权”。
        if same_team_public(public, me, last_player):
            # 例外1：自己这一手可以直接出完，团队已经进入终局阶段。
            winning = [c for c in playable if len(c) == len(hand)]
            if winning:
                playable = winning
            else:
                # 例外2：敌人只剩1~2张，而盟友的牌权无法可靠压制。
                enemies_low = any(
                    p != me and not same_team_public(public, me, p) and n <= 2
                    for p,n in enumerate(public["hand_counts"])
                )
                # 只有在能一次出较多牌、且敌人非常危险时，才考虑压盟友。
                if not enemies_low:
                    return []
                efficient = [c for c in playable if len(c) >= 3]
                if efficient:
                    playable = efficient
                else:
                    return []

    d = public["difficulty"]
    if d == "简单":
        return random.choice(playable)

    if d == "普通":
        # 优先一次消耗较多牌；不轻易动用炸弹。
        nonbomb = [c for c in playable if analyze(c)["type"] not in ("bomb","rocket")]
        pool = nonbomb if nonbomb else playable
        pool.sort(key=lambda c: (-len(c), candidate_cost(c)))
        return random.choice(pool[:min(8,len(pool))])

    # 困难：只用公开剩余牌数 + 阵营关系进行决策。
    def score(c):
        info = analyze(c)
        s = -len(c)*8 + sum(card_value(x) for x in c)*0.12
        if info["type"] == "bomb": s += 18
        if info["type"] == "rocket": s += 40

        # 敌方接近出完：提高压制优先级。
        for p,n in enumerate(public["hand_counts"]):
            if p != me and not same_team_public(public, me, p) and n <= 3:
                s -= 28

        # 盟友牌少时，尽量不要抢盟友牌权。
        if last_player is not None and last_player != me and same_team_public(public, me, last_player):
            s += 45

        # 自己接近出完时，优先能一次清掉大量牌的组合。
        if len(hand) <= 8:
            s -= len(c)*5

        return s

    playable.sort(key=score)
    return playable[0]

# ------------------------- 游戏 -------------------------
class Game:
    def __init__(self, num_players, difficulty, settings):
        self.num_players = num_players
        self.rule = PLAYER_RULES[num_players]
        self.difficulty = difficulty
        self.settings = settings
        self.new_round()

    def new_round(self):
        # 竞叫阶段与正式手牌衔接：
        # 3人：17张就是正式手牌，叫分时不会换牌；地主确定后仅增加3张底牌。
        # 4~10人：先固定发5张竞叫牌；竞叫结束后这5张牌直接保留，
        # 只从剩余牌堆继续补牌到人数规则要求的基础手牌数量。
        # 不回收、不替换、不重洗已经发到玩家手里的牌。正式发牌完成后建立不可变手牌锁。
        self.phase = "bid"
        self.deck = make_deck(self.rule["decks"])

        # 本局不可变牌库：每个UID对应固定的点数和花色。
        # UID一旦发给玩家，后续只能正常从该玩家手牌中移除，不能换牌。
        self.card_registry = {
            c["uid"]: (c["rank"], c["suit"], c["uid"])
            for c in self.deck
        }
        random.shuffle(self.deck)

        self.hands = [[] for _ in range(self.num_players)]
        self.initial_hands = [[] for _ in range(self.num_players)]
        self.bid_hands = [[] for _ in range(self.num_players)]

        if self.rule["bidding_mode"] == "standard_17":
            for p in range(self.num_players):
                for _ in range(17):
                    self.hands[p].append(self.deck.pop())
            self.bid_hands = [sort_cards(h) for h in self.hands]
        else:
            # 4~10人：先发5张竞叫牌。竞叫结束后这些牌直接成为正式手牌的一部分。
            for p in range(self.num_players):
                for _ in range(5):
                    self.bid_hands[p].append(self.deck.pop())
                self.bid_hands[p] = sort_cards(self.bid_hands[p])

        self.bid_values = [None] * self.num_players
        self.bid_order = []
        self.current = random.randrange(self.num_players)
        self.primary = None
        self.landlords = []
        self.bottom = []
        self.played_uids = set()
        self.last_play = []
        self.last_info = None
        self.last_player = None
        self.pass_count = 0
        self.winner = None
        self.selected = set()
        self.message = f"玩家{self.current+1}开始叫分"
        self.ai_timer = 0
        self.animation = None
        self.animation_queue = []
        self.round_no = getattr(self, "round_no", 0) + 1
        self.dealt_snapshot = None
        self.dealt_owner = None
        self.hand_lock = False

    def normalize_all_hands(self):
        """将所有手牌对象恢复为UID对应的标准实体牌面。
        这里只允许把同一UID还原成它原本的牌面，不会生成新牌、换牌或改变归属。
        """
        for p in range(self.num_players):
            self.hands[p] = [self.restore_card_identity(c) for c in self.hands[p]]
        self.deck = [self.restore_card_identity(c) for c in self.deck]
        self.bottom = [self.restore_card_identity(c) for c in self.bottom]

    def restore_card_identity(self, c):
        uid = int(c["uid"])
        if uid not in self.card_registry:
            raise RuntimeError(f"发现不存在于本局牌库的UID: {uid}")
        rank, suit, fixed_uid = self.card_registry[uid]
        return {"rank": rank, "suit": suit, "uid": fixed_uid}

    def audit_card_state(self):
        """统一审计3~10人模式的实体牌。
        UID决定真实牌面；hand/deck/played 三处合计必须恰好覆盖整副牌。
        """
        expected_total = self.rule["decks"] * 54
        locations = {}
        all_cards = []

        for p, hand in enumerate(self.hands):
            for c in hand:
                uid = int(c["uid"])
                if uid not in self.card_registry:
                    raise RuntimeError(f"玩家{p+1}持有非法UID {uid}")
                locations.setdefault(uid, []).append(f"hand:{p}")
                fixed = canonical_card(c)
                # 手中的对象即使被意外改过，计算/显示都以UID为准；
                # 这里不把修正后的副本写回手牌，避免再次引入换牌。
                if c.get("rank") != fixed["rank"] or c.get("suit") != fixed["suit"]:
                    raise RuntimeError(f"UID={uid}的牌面字段被篡改")
                all_cards.append(uid)

        for c in self.deck:
            uid = int(c["uid"])
            if uid not in self.card_registry:
                raise RuntimeError(f"牌堆存在非法UID {uid}")
            locations.setdefault(uid, []).append("deck")
            all_cards.append(uid)

        # 已经正常打出的牌由 played_uids 记录。
        for uid in getattr(self, "played_uids", set()):
            uid = int(uid)
            if uid not in self.card_registry:
                raise RuntimeError(f"已出牌记录存在非法UID {uid}")
            locations.setdefault(uid, []).append("played")

        if len(all_cards) != len(set(all_cards)):
            raise RuntimeError("检测到手牌/牌堆中存在重复实体牌")

        if any(len(v) != 1 for v in locations.values()):
            raise RuntimeError("检测到同一实体牌同时存在于多个位置")

        if len(locations) != expected_total:
            raise RuntimeError(
                f"牌库覆盖异常：当前记录{len(locations)}张，应该是{expected_total}张"
            )
        return True

    def restart(self):
        self.new_round()
        self.message = "本局无人叫地主，重新发牌"

    def highest_bid(self):
        vals = [v for v in self.bid_values if v is not None and v > 0]
        return max(vals, default=0)

    def do_bid(self, player, point):
        if self.phase != "bid" or player != self.current:
            return False
        if point < 0 or point > 3:
            return False

        # 叫分必须严格高于当前最高分；不叫可以随时选择。
        current_high = self.highest_bid()
        if point != 0 and point <= current_high:
            self.message = f"当前最高叫分为{current_high}分，必须叫更高的分"
            return False

        self.bid_values[player] = point
        if player not in self.bid_order:
            self.bid_order.append(player)
        self.message = f"玩家{player+1}：{'不叫' if point==0 else str(point)+'分'}"

        if all(v is not None for v in self.bid_values):
            if self.highest_bid() == 0:
                self.restart()
                return True

            n = self.rule["landlords"]
            # 多地主：按最高叫分排序，若同分则按实际叫分先后决定名额。
            order_pos = {p:i for i,p in enumerate(self.bid_order)}
            ranked = sorted(
                range(self.num_players),
                key=lambda p: (-self.bid_values[p], order_pos.get(p, self.num_players))
            )
            self.landlords = sorted(ranked[:n])
            self.primary = min(
                self.landlords,
                key=lambda p: (-self.bid_values[p], order_pos.get(p, self.num_players))
            )
            self.message = (
                f"地主确定：{','.join('玩家'+str(p+1) for p in self.landlords)}；"
                f"主地主：玩家{self.primary+1}"
            )
            self.finish_deal()
            return True

        # 关键修复：叫完后必须把控制权交给下一位玩家，否则会永久停在“等待AI叫分”。
        self.current = (player + 1) % self.num_players
        return True

    def finish_deal(self):
        """地主确定后完成正式发牌。

        4~10人模式的5张竞叫牌不会被回收，也不会重新洗牌。
        它们直接成为对应玩家的正式手牌，然后只从“剩余牌堆”继续补足规则要求的基础手牌数量。
        因此一张牌一旦发到某个玩家手里，就永远属于该玩家，直到该玩家正常出掉它。

        3人模式同样保持原有17张正式手牌，只在地主确定后增加底牌。
        所有正式手牌补齐后，建立 dealt_snapshot/dealt_owner 锁，后续禁止任何换牌、偷牌、重抽或跨玩家转移。
        """
        if self.hand_lock:
            return

        if self.rule["bidding_mode"] == "standard_17":
            # 三人斗地主：叫分前已经发出的17张就是正式手牌，绝不回收或重洗。
            self.hands = [list(h) for h in self.bid_hands]
        else:
            # 4~10人：竞叫牌直接保留为正式手牌。
            # 不能把它们放回牌堆，否则会破坏“发到手里后固定”的规则。
            self.hands = [list(h) for h in self.bid_hands]

            # 基础手牌数量（不含底牌）。竞叫牌已经占5张，下面只补剩余数量。
            base = self.rule["farmer_cards"]
            preview_count = 5
            if base < preview_count:
                raise RuntimeError("规则配置错误：基础手牌数小于竞叫牌数量")

            for p in range(self.num_players):
                need = base - len(self.hands[p])
                if need < 0:
                    raise RuntimeError("正式发牌错误：竞叫牌超过基础手牌数量")
                for _ in range(need):
                    if not self.deck:
                        raise RuntimeError("正式发牌错误：剩余牌堆不足")
                    self.hands[p].append(self.deck.pop())

            # 某些多人规则中地主的基础手牌比农民更多。
            extra = self.rule["landlord_base"] - base
            if extra < 0:
                raise RuntimeError("规则配置错误：地主基础牌数小于农民基础牌数")
            for p in self.landlords:
                for _ in range(extra):
                    if not self.deck:
                        raise RuntimeError("正式发牌错误：地主额外牌不足")
                    self.hands[p].append(self.deck.pop())

        # 底牌是在正式发牌之后从剩余牌堆取出，并按照人数规则固定归属。
        bottom_n = self.rule["bottom"]
        if len(self.deck) < bottom_n:
            raise RuntimeError("底牌发放错误：牌堆不足")
        self.bottom = [self.deck.pop() for _ in range(bottom_n)] if bottom_n else []
        mode = self.rule["bottom_mode"]
        if self.bottom:
            if mode in ("all_primary", "primary"):
                self.hands[self.primary].extend(self.bottom)
            elif mode == "split_landlords":
                for i, c in enumerate(self.bottom):
                    self.hands[self.landlords[i % len(self.landlords)]].append(c)

        # 检查总牌数：底牌已经并入对应地主手牌，因此这里只统计正式手牌。
        total_cards = sum(len(h) for h in self.hands)
        expected = self.rule["decks"] * 54
        if total_cards != expected:
            raise RuntimeError(f"正式发牌错误：当前{total_cards}张，规则应为{expected}张")

        # 正式牌局开始前只排序，不重新生成牌。
        self.normalize_all_hands()
        for p in range(self.num_players):
            self.hands[p] = sort_cards(self.hands[p])
            if not self.settings.get("ascending", True):
                self.hands[p].reverse()
            self.initial_hands[p] = [c["uid"] for c in self.hands[p]]

        self.audit_card_state()

        # ===================== 正式手牌不可变锁 =====================
        self.dealt_snapshot = {
            p: frozenset(c["uid"] for c in self.hands[p])
            for p in range(self.num_players)
        }
        self.dealt_owner = {
            c["uid"]: p
            for p in range(self.num_players)
            for c in self.hands[p]
        }
        self.hand_lock = True

        # 锁定时做一次全场UID校验；之后每次出牌前还会再次校验。
        if not self.validate_hand_integrity():
            raise RuntimeError("正式手牌锁定失败：UID归属异常")

        # 竞叫牌已经并入正式手牌；清空仅作为竞叫阶段的辅助引用，
        # 实际牌对象已经保存在 self.hands 中，并受到 dealt_snapshot/dealt_owner 保护。
        self.bid_hands = [[] for _ in range(self.num_players)]

        self.current = self.primary
        self.phase = "play"
        self.selected.clear()
        self.last_play = []
        self.last_info = None
        self.last_player = None
        self.pass_count = 0
        self.message = f"主地主玩家{self.primary+1}先出牌"

    def validate_hand_integrity(self):
        """严格验证：正式发牌后，每张仍在手里的牌必须属于原始 UID 且不能跨玩家。"""
        if not self.hand_lock or self.dealt_snapshot is None or self.dealt_owner is None:
            return True
        seen = set()
        for p in range(self.num_players):
            allowed = self.dealt_snapshot[p]
            for c in self.hands[p]:
                uid = c["uid"]
                if uid not in allowed:
                    self.message = f"检测到玩家{p+1}非法新增/替换手牌，操作已拒绝"
                    return False
                if self.dealt_owner.get(uid) != p:
                    self.message = f"检测到玩家{p+1}非法转移手牌，操作已拒绝"
                    return False
                if uid in seen:
                    self.message = "检测到同一张牌被多个玩家持有，操作已拒绝"
                    return False
                seen.add(uid)
        return True

    def same_team(self,a,b):
        return (a in self.landlords) == (b in self.landlords)

    def pass_play(self, player):
        if self.phase != "play" or player != self.current or self.animation:
            return
        if self.last_info is None or self.last_player == player:
            self.message = "你拥有重新领出权，不能不出"
            return
        self.pass_count += 1
        self.message = f"玩家{player+1} 不出"
        self.current = (player+1)%self.num_players
        if self.pass_count >= self.num_players-1:
            self.current = self.last_player
            self.last_play = []
            self.last_info = None
            self.last_player = None
            self.pass_count = 0
            self.message = f"玩家{self.current+1}重新领出"

    def play(self, player, cards):
        if self.phase != "play" or player != self.current or self.animation:
            return False
        info = analyze(cards)
        if not info:
            self.message = "这组牌型不合法"
            return False
        if self.last_info and self.last_player != player and not can_beat(info, self.last_info):
            self.message = "这组牌压不过上一手"
            return False
        ids = {c["uid"] for c in cards}
        if not ids.issubset({c["uid"] for c in self.hands[player]}):
            return False

        # 出牌前只做UID归属审计。AI和真人都只能打出自己已经持有的UID。
        if not self.validate_hand_integrity():
            return False
        self.audit_card_state()
        if not ids.issubset(self.dealt_snapshot[player]):
            self.message = "这张牌不属于本玩家本轮正式手牌"
            return False

        self.hands[player] = [c for c in self.hands[player] if c["uid"] not in ids]
        self.played_uids.update(ids)
        self.last_play = sort_cards(cards)
        self.last_info = info
        self.last_player = player
        self.pass_count = 0
        self.selected.clear()
        self.message = f"玩家{player+1} 出 {TYPE_NAMES[info['type']]}"

        # 出牌动画：牌从手牌区/玩家区域向中央出牌区移动
        self.animation = {
            "player": player,
            "t": 0.0,
            "duration": 0.38,
            "cards": self.last_play[:],
        }

        self.audit_card_state()

        if not self.hands[player]:
            self.winner = player
            self.phase_after_animation = "over"
        else:
            self.phase_after_animation = "play"
        return True

    def update(self,dt):
        if self.animation:
            self.animation["t"] += dt
            if self.animation["t"] >= self.animation["duration"]:
                self.animation = None
                if self.phase_after_animation == "over":
                    self.phase = "over"
                    self.message = "地主阵营获胜！" if self.winner in self.landlords else "农民阵营获胜！"
                else:
                    self.current = (self.current+1)%self.num_players



# ------------------------- 提示 -------------------------
def hint_for_player(g):
    """给真人玩家（0号位）挑一手提示牌，结果写入 g.selected / g.message。"""
    if g.current != 0:
        return
    candidates = generate_candidates(g.hands[0], limit=2500)
    if g.last_info is None or g.last_player == 0:
        choices = candidates
    else:
        choices = [c for c in candidates if can_beat(analyze(c), g.last_info)]
    if not choices:
        g.message = "没有能压过上一手的牌，可以选择不出"
        g.selected.clear()
        return
    # 优先小组合，但尽量一次出多张
    choices.sort(key=lambda c: (-len(c), candidate_cost(c)))
    chosen = choices[0]
    ids = {c["uid"] for c in chosen}
    g.selected = {i for i, c in enumerate(g.hands[0]) if c["uid"] in ids}
    g.message = f"提示：{TYPE_NAMES[analyze(chosen)['type']]}"
