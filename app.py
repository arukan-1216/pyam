import streamlit as st
import copy
from itertools import combinations

# =========================
# 基本設定
# =========================
ROWS = 6
COLS = 8

COLORS = ["赤", "青", "緑", "黄", "紫", "ハート", "空"]
NORMAL_COLORS = ["赤", "青", "緑", "黄", "紫"]
EMOJI = {
    "赤": "🟥",
    "青": "🟦",
    "緑": "🟩",
    "黄": "🟨",
    "紫": "🟪",
    "ハート": "💖",
    "空": "⬛",
}

DIR4 = [(1,0), (-1,0), (0,1), (0,-1)]


# =========================
# ぷよ処理
# =========================
def find_groups(field):
    visited = [[False]*COLS for _ in range(ROWS)]
    groups = []

    for r in range(ROWS):
        for c in range(COLS):
            if visited[r][c]:
                continue
            color = field[r][c]
            if color == "空":
                continue

            stack = [(r,c)]
            visited[r][c] = True
            comp = [(r,c)]

            while stack:
                cr, cc = stack.pop()
                for dr, dc in DIR4:
                    nr, nc = cr+dr, cc+dc
                    if 0 <= nr < ROWS and 0 <= nc < COLS:
                        if (not visited[nr][nc]) and field[nr][nc] == color:
                            visited[nr][nc] = True
                            stack.append((nr,nc))
                            comp.append((nr,nc))

            groups.append((color, comp))

    return groups


def erase_step(field):
    """
    1ステップ消去＋落下
    return:
      score_erased: 得点に入る消去数（通常色のみ）
      simul_erased: 同時消し数（ハート含む）
      ok: 消えたかどうか
    """

    groups = find_groups(field)

    erase = set()

    # 通常色（4以上で消える）
    for color, cells in groups:
        if color in NORMAL_COLORS:
            if len(cells) >= 4:
                erase |= set(cells)

    # ハートは単体では消えない
    # ただし消えるぷよに隣接していたら巻き込まれて消える
    heart = set()
    for r in range(ROWS):
        for c in range(COLS):
            if field[r][c] == "ハート":
                for dr, dc in DIR4:
                    nr, nc = r+dr, c+dc
                    if 0 <= nr < ROWS and 0 <= nc < COLS:
                        if (nr, nc) in erase:
                            heart.add((r,c))
    erase |= heart

    if not erase:
        return 0, 0, False

    score_erased = 0
    for r, c in erase:
        if field[r][c] in NORMAL_COLORS:
            score_erased += 1
        field[r][c] = "空"

    # 落下処理
    for c in range(COLS):
        stack = []
        for r in range(ROWS-1, -1, -1):
            if field[r][c] != "空":
                stack.append(field[r][c])

        for r in range(ROWS-1, -1, -1):
            field[r][c] = stack.pop(0) if stack else "空"

    return score_erased, len(erase), True


def simulate_chain(field):
    """
    連鎖を最後まで回す
    return: chains, total_score, max_simul
    """
    chains = 0
    total_score = 0
    max_simul = 0

    while True:
        score_erased, simul_erased, ok = erase_step(field)
        if not ok:
            break

        chains += 1
        total_score += score_erased
        max_simul = max(max_simul, simul_erased)

    return chains, total_score, max_simul


def drop_next(field, nexts):
    """
    ネクスト8個を上から落とす（A方式）
    各列の「一番上の空き」に入れる
    """
    for c, color in enumerate(nexts):
        for r in range(ROWS):
            if field[r][c] == "空":
                field[r][c] = color
                break


def has_any_erase(field):
    """
    塗り替え直後に消えるかチェック
    1回でも消えたら True
    """
    tmp = copy.deepcopy(field)
    score, simul, ok = erase_step(tmp)
    return ok


def apply_paint(field, paint_positions, paint_color):
    """
    指定位置を paint_color にする
    """
    for r, c in paint_positions:
        field[r][c] = paint_color


def get_candidates(field, paint_color):
    """
    塗り替え候補:
      - 空は除外
      - すでに paint_color のマスは除外（不毛なので）
    """
    cands = []
    for r in range(ROWS):
        for c in range(COLS):
            v = field[r][c]
            if v == "空":
                continue
            if v == paint_color:
                continue
            cands.append((r,c))
    return cands


# =========================
# Streamlit UI
# =========================
st.set_page_config(layout="wide")
st.title("ぷよクエ 盤面作成 + 塗り替え全探索（起点1個消し）")

# =====================
# 状態
# =====================
if "field" not in st.session_state:
    st.session_state.field = [["空"] * COLS for _ in range(ROWS)]

if "history" not in st.session_state:
    st.session_state.history = []

if "current_color" not in st.session_state:
    st.session_state.current_color = "赤"

if "save_slots" not in st.session_state:
    st.session_state.save_slots = [None, None, None]

if "fixed_field" not in st.session_state:
    st.session_state.fixed_field = None


def push_history():
    st.session_state.history.append(copy.deepcopy(st.session_state.field))
    if len(st.session_state.history) > 50:
        st.session_state.history.pop(0)


def undo():
    if st.session_state.history:
        st.session_state.field = st.session_state.history.pop()


# =====================
# パレット
# =====================
st.header("色パレット（クリックで選択 → 下の盤面をクリックで塗る）")

cols = st.columns(len(COLORS))
for i, color in enumerate(COLORS):
    with cols[i]:
        if st.button(EMOJI[color], key=f"pal_{color}"):
            st.session_state.current_color = color

st.markdown(f"### 選択中： {EMOJI[st.session_state.current_color]} {st.session_state.current_color}")

# =====================
# 操作
# =====================
st.header("操作")

b1, b2, b3, b4 = st.columns(4)

with b1:
    if st.button("🧹 盤面クリア"):
        push_history()
        st.session_state.field = [["空"] * COLS for _ in range(ROWS)]

with b2:
    if st.button("🎨 全塗り"):
        push_history()
        for r in range(ROWS):
            for c in range(COLS):
                st.session_state.field[r][c] = st.session_state.current_color

with b3:
    if st.button("↩ Undo"):
        undo()

with b4:
    if st.button("📌 盤面確定"):
        st.session_state.fixed_field = copy.deepcopy(st.session_state.field)

# =====================
# 保存
# =====================
st.header("保存（3スロット）")

for i in range(3):
    c1, c2 = st.columns(2)
    with c1:
        if st.button(f"保存{i+1}", key=f"save{i}"):
            st.session_state.save_slots[i] = copy.deepcopy(st.session_state.field)
    with c2:
        if st.button(f"読込{i+1}", key=f"load{i}"):
            if st.session_state.save_slots[i]:
                push_history()
                st.session_state.field = copy.deepcopy(st.session_state.save_slots[i])

# =====================
# 盤面編集
# =====================
st.header("盤面（8×6）")

for r in range(ROWS):
    cols = st.columns(COLS)
    for c in range(COLS):
        with cols[c]:
            label = EMOJI[st.session_state.field[r][c]]
            if st.button(label, key=f"cell_{r}_{c}"):
                push_history()
                st.session_state.field[r][c] = st.session_state.current_color

# =====================
# 編集中盤面表示
# =====================
st.markdown("### 編集中盤面")
for r in range(ROWS):
    st.write(" ".join(EMOJI[st.session_state.field[r][c]] for c in range(COLS)))

# =====================
# 確定盤面表示
# =====================
if st.session_state.fixed_field:
    st.markdown("## 📌 確定盤面")
    for r in range(ROWS):
        st.write(" ".join(EMOJI[st.session_state.fixed_field[r][c]] for c in range(COLS)))

# =====================
# ネクスト
# =====================
st.header("ネクスト（8個）")

if "next" not in st.session_state:
    st.session_state.next = ["赤"] * 8

cols = st.columns(8)
for i in range(8):
    with cols[i]:
        st.session_state.next[i] = st.selectbox(
            f"next{i+1}",
            NORMAL_COLORS,
            index=NORMAL_COLORS.index(st.session_state.next[i]),
            key=f"next_{i}",
            label_visibility="collapsed"
        )

st.write(" ".join(EMOJI[c] for c in st.session_state.next))

# =========================
# 解析UI
# =========================
st.markdown("---")
st.header("解析（塗り替え → 消えない確認 → 起点1個消し → 連鎖得点最大）")

paint_color = st.selectbox("塗り替え色", ["赤","青","緑","黄","紫","ハート"])
paint_count = st.number_input("塗り替え数（最大12）", 0, 12, 0)

if paint_count > 12:
    st.error("最大12まで")
    st.stop()

progress_bar = st.progress(0)
status_text = st.empty()


def run_search(base_field, nexts, paint_color, paint_count):
    """
    1) 塗り替え位置を全探索
    2) 塗り替え直後に消えたら廃案
    3) 起点1個を全探索で消す
    4) 連鎖得点最大を探す
    """
    cands = get_candidates(base_field, paint_color)

    # 探索範囲を少し絞る（0〜12じゃなくて paint_count-4〜paint_count）
    min_k = max(0, paint_count - 4)

    from math import comb
    total_patterns = 0
    for k in range(min_k, paint_count+1):
        if k <= len(cands):
            total_patterns += comb(len(cands), k)

    done = 0
    last_pct = -1

    best = []  # 上位3件

    for k in range(min_k, paint_count+1):
        for combi in combinations(cands, k):

            # ===== 塗り替え盤面を作る =====
            field = [row[:] for row in base_field]
            apply_paint(field, combi, paint_color)

            # ★塗り替え直後に消えるなら廃案
            if has_any_erase(field):
                done += 1
                continue

            # ===== ネクスト落下 =====
            field2 = copy.deepcopy(field)
            drop_next(field2, nexts)

            # ★ネクスト落下で消えるのも廃案（あなたの仕様）
            if has_any_erase(field2):
                done += 1
                continue

            # ===== 起点1個を全探索 =====
            for sr in range(ROWS):
                for sc in range(COLS):

                    if field2[sr][sc] == "空":
                        continue

                    # 起点を消す（得点0）
                    test_field = copy.deepcopy(field2)
                    test_field[sr][sc] = "空"

                    # 起点消し後、落下
                    for c in range(COLS):
                        stack = []
                        for r in range(ROWS-1, -1, -1):
                            if test_field[r][c] != "空":
                                stack.append(test_field[r][c])
                        for r in range(ROWS-1, -1, -1):
                            test_field[r][c] = stack.pop(0) if stack else "空"

                    # 連鎖計算
                    chains, score, maxsim = simulate_chain(test_field)

                    # 条件: chains>=6 OR maxsim>=16
                    if not (chains >= 6 or maxsim >= 16):
                        continue

                    best.append({
                        "score": score,
                        "chains": chains,
                        "maxsim": maxsim,
                        "paint": combi,
                        "start": (sr, sc),
                    })

                    best = sorted(
                        best,
                        key=lambda x: (x["score"], x["chains"], x["maxsim"]),
                        reverse=True
                    )[:3]

            # ===== 進捗 =====
            done += 1
            pct = int(done / total_patterns * 100)

            if pct != last_pct:
                progress_bar.progress(pct)

                bar = "█"*(pct//5) + "░"*(20-pct//5)
                status_text.markdown(f"""
**進捗:** {pct}%  
**試行中:** {done:,} / {total_patterns:,}

{bar}
""")
                last_pct = pct

    return best


if st.button("解析開始"):

    if st.session_state.fixed_field is None:
        st.error("先に 📌盤面確定 を押してね！")
        st.stop()

    base_field = [row[:] for row in st.session_state.fixed_field]
    nexts = st.session_state.next

    with st.spinner("探索中…（重いけど待ってね）"):
        results = run_search(base_field, nexts, paint_color, paint_count)

    st.success("完了！")

    if not results:
        st.warning("条件を満たす結果が見つからなかった！")
    else:
        st.header("🏆 上位3件")

        for rank, r in enumerate(results, start=1):
            st.subheader(f"{rank}位")

            st.write(f"得点（連鎖消去のみ）: **{r['score']}**")
            st.write(f"連鎖: **{r['chains']}**")
            st.write(f"最大同時消し: **{r['maxsim']}**")
            st.write(f"起点: **{r['start']}**")
            st.write(f"塗り替え数: **{len(r['paint'])}**")

            # 盤面表示（塗り替え場所と起点をマーク）
            view = copy.deepcopy(base_field)
            apply_paint(view, r["paint"], paint_color)

            # ネクスト落下も反映した状態を表示
            drop_next(view, nexts)

            st.markdown("### 塗り替え後 + ネクスト落下後（起点は💥）")

            for rr in range(ROWS):
                row = []
                for cc in range(COLS):
                    if (rr, cc) == r["start"]:
                        row.append("💥")
                    else:
                        row.append(EMOJI[view[rr][cc]])
                st.write(" ".join(row))

            st.markdown("---")
