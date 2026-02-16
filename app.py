import streamlit as st
import copy
from itertools import combinations
from math import comb

# =========================
# 基本設定
# =========================
ROWS = 6
COLS = 8

NORMAL_COLORS = ["赤", "青", "緑", "黄", "紫"]
ALL_COLORS = ["赤", "青", "緑", "黄", "紫", "ハート", "空"]

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
# 便利関数
# =========================
def in_bounds(r, c):
    return 0 <= r < ROWS and 0 <= c < COLS


def copy_field(field):
    return [row[:] for row in field]


# =========================
# 高速：連結数カウント（局所判定用）
# =========================
def count_connected(field, sr, sc):
    """
    (sr,sc) の色と同じ色が何個連結しているか（4方向）
    """
    color = field[sr][sc]
    if color == "空":
        return 0

    stack = [(sr, sc)]
    visited = set([(sr, sc)])
    cnt = 0

    while stack:
        r, c = stack.pop()
        cnt += 1
        for dr, dc in DIR4:
            nr, nc = r + dr, c + dc
            if in_bounds(nr, nc) and (nr, nc) not in visited:
                if field[nr][nc] == color:
                    visited.add((nr, nc))
                    stack.append((nr, nc))

    return cnt


def local_has_erase_after_paint(base_field, r, c, paint_color):
    """
    1マス塗った瞬間に
    paint_color が4つ以上繋がるならアウト
    """
    if base_field[r][c] == "空":
        return False
    if base_field[r][c] == paint_color:
        return False

    tmp = copy_field(base_field)
    tmp[r][c] = paint_color

    # ★塗ったマスの連結だけ見れば十分
    return count_connected(tmp, r, c) >= 4


def local_has_erase(field):
    """
    盤面全体の「消えるものがあるか」判定（遅い）
    → 今回は原則使わない
    """
    for r in range(ROWS):
        for c in range(COLS):
            if field[r][c] in NORMAL_COLORS:
                if count_connected(field, r, c) >= 4:
                    return True
    return False


# =========================
# 消去処理（本番シミュ用）
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

            stack = [(r, c)]
            visited[r][c] = True
            comp = [(r, c)]

            while stack:
                cr, cc = stack.pop()
                for dr, dc in DIR4:
                    nr, nc = cr + dr, cc + dc
                    if in_bounds(nr, nc) and not visited[nr][nc]:
                        if field[nr][nc] == color:
                            visited[nr][nc] = True
                            stack.append((nr, nc))
                            comp.append((nr, nc))

            groups.append((color, comp))

    return groups


def erase_step(field):
    """
    1回消す + 落下
    return:
      score_erased: 得点に入る消去数（通常色のみ）
      simul_erased: 同時消し数（ハート含む）
      ok: 消えたかどうか
    """
    groups = find_groups(field)
    erase = set()

    # 通常色
    for color, cells in groups:
        if color in NORMAL_COLORS and len(cells) >= 4:
            erase |= set(cells)

    # ハート巻き込み
    heart = set()
    for r in range(ROWS):
        for c in range(COLS):
            if field[r][c] == "ハート":
                for dr, dc in DIR4:
                    nr, nc = r + dr, c + dc
                    if in_bounds(nr, nc) and (nr, nc) in erase:
                        heart.add((r, c))
    erase |= heart

    if not erase:
        return 0, 0, False

    score_erased = 0
    for r, c in erase:
        if field[r][c] in NORMAL_COLORS:
            score_erased += 1
        field[r][c] = "空"

    # 落下
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
        score, simul, ok = erase_step(field)
        if not ok:
            break

        chains += 1
        total_score += score
        max_simul = max(max_simul, simul)

    return chains, total_score, max_simul


# =========================
# ネクスト落下（A方式）
# =========================
def drop_next(field, nexts):
    for c, color in enumerate(nexts):
        for r in range(ROWS):
            if field[r][c] == "空":
                field[r][c] = color
                break


# =========================
# 候補生成
# =========================
def get_raw_paint_candidates(base_field, paint_color):
    cands = []
    for r in range(ROWS):
        for c in range(COLS):
            v = base_field[r][c]
            if v == "空":
                continue
            if v == paint_color:
                continue
            cands.append((r, c))
    return cands


def get_pruned_paint_candidates(base_field, paint_color):
    """
    あなたの枝切り案：
    1マス塗った瞬間に4つ成立するなら候補から除外
    """
    raw = get_raw_paint_candidates(base_field, paint_color)
    pruned = []

    for (r, c) in raw:
        if local_has_erase_after_paint(base_field, r, c, paint_color):
            continue
        pruned.append((r, c))

    return pruned


def build_start_candidates(field_after_next):
    """
    起点候補を局所で作る：
    起点を1個消した瞬間に「4つが成立しそう」な場所だけを候補にする
    """

    starts = set()

    for r in range(ROWS):
        for c in range(COLS):
            if field_after_next[r][c] == "空":
                continue

            # 起点を消した場合に影響があるのは
            # その周囲の色が繋がるかどうか
            # → 周囲を軽くチェック

            for dr, dc in DIR4:
                nr, nc = r + dr, c + dc
                if not in_bounds(nr, nc):
                    continue
                if field_after_next[nr][nc] == "空":
                    continue

                # 起点を消すと (nr,nc) が空に接する
                # その色がすでに3以上つながってるなら
                # 4成立の可能性がある
                if field_after_next[nr][nc] in NORMAL_COLORS:
                    if count_connected(field_after_next, nr, nc) >= 3:
                        starts.add((r, c))
                        break

    # もしゼロになったら保険で全マス
    if not starts:
        for r in range(ROWS):
            for c in range(COLS):
                if field_after_next[r][c] != "空":
                    starts.add((r, c))

    return list(starts)


# =========================
# Streamlit UI
# =========================
st.set_page_config(layout="wide")
st.title("ぷよクエ盤面エディタ + 爆速探索（塗り替え→消えない→起点1個消し）")

# -------------------------
# 状態
# -------------------------
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

if "next" not in st.session_state:
    st.session_state.next = ["赤"] * 8


def push_history():
    st.session_state.history.append(copy.deepcopy(st.session_state.field))
    if len(st.session_state.history) > 50:
        st.session_state.history.pop(0)


def undo():
    if st.session_state.history:
        st.session_state.field = st.session_state.history.pop()


# -------------------------
# パレット
# -------------------------
st.header("色パレット（クリックで選択 → 盤面をクリックで塗る）")

cols = st.columns(len(ALL_COLORS))
for i, color in enumerate(ALL_COLORS):
    with cols[i]:
        if st.button(EMOJI[color], key=f"pal_{color}"):
            st.session_state.current_color = color

st.markdown(f"### 選択中： {EMOJI[st.session_state.current_color]} {st.session_state.current_color}")

# -------------------------
# 操作
# -------------------------
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

# -------------------------
# 保存
# -------------------------
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

# -------------------------
# 盤面
# -------------------------
st.header("盤面（8×6）")

for r in range(ROWS):
    cols = st.columns(COLS)
    for c in range(COLS):
        with cols[c]:
            label = EMOJI[st.session_state.field[r][c]]
            if st.button(label, key=f"cell_{r}_{c}"):
                push_history()
                st.session_state.field[r][c] = st.session_state.current_color

st.markdown("### 編集中盤面")
for r in range(ROWS):
    st.write(" ".join(EMOJI[st.session_state.field[r][c]] for c in range(COLS)))

# -------------------------
# 確定盤面
# -------------------------
if st.session_state.fixed_field is not None:
    st.markdown("## 📌 確定盤面")
    for r in range(ROWS):
        st.write(" ".join(EMOJI[st.session_state.fixed_field[r][c]] for c in range(COLS)))

# -------------------------
# ネクスト
# -------------------------
st.header("ネクスト（8個）")

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
st.header("解析（爆速）")

paint_color = st.selectbox("塗り替え色", ["赤", "青", "緑", "黄", "紫", "ハート"])
paint_count = st.number_input("塗り替え数（最大12）", 0, 12, 0)

if paint_count > 12:
    st.error("最大12まで")
    st.stop()

progress_bar = st.progress(0)
status_text = st.empty()


def run_search(base_field, nexts, paint_color, paint_count):
    # -------------------------
    # 1) 塗り替え候補を枝切り
    # -------------------------
    paint_cands = get_pruned_paint_candidates(base_field, paint_color)

    status_text.markdown(
        f"塗り替え候補マス数: **{len(paint_cands)}** / 48"
    )

    # -------------------------
    # 2) 探索数計算
    # -------------------------
    min_k = max(0, paint_count - 4)

    total_patterns = 0
    for k in range(min_k, paint_count + 1):
        if k <= len(paint_cands):
            total_patterns += comb(len(paint_cands), k)

    done = 0
    last_pct = -1

    best = []

    # -------------------------
    # 3) 全探索
    # -------------------------
    for k in range(min_k, paint_count + 1):
        if k > len(paint_cands):
            continue

        for combi in combinations(paint_cands, k):

            field = copy_field(base_field)

            # 塗り替え
            for r, c in combi:
                field[r][c] = paint_color

            # 塗り替え直後に消えるなら廃案
            if local_has_erase(field):
                done += 1
                continue

            # ネクスト落下
            field2 = copy.deepcopy(field)
            drop_next(field2, nexts)

            # ネクスト落下で消えるなら廃案
            if local_has_erase(field2):
                done += 1
                continue

            # -------------------------
            # 起点候補を局所生成
            # -------------------------
            start_cands = build_start_candidates(field2)

            for sr, sc in start_cands:
                if field2[sr][sc] == "空":
                    continue

                test = copy.deepcopy(field2)

                # 起点消し（得点0）
                test[sr][sc] = "空"

                # 落下
                for c in range(COLS):
                    stack = []
                    for r in range(ROWS-1, -1, -1):
                        if test[r][c] != "空":
                            stack.append(test[r][c])
                    for r in range(ROWS-1, -1, -1):
                        test[r][c] = stack.pop(0) if stack else "空"

                chains, score, maxsim = simulate_chain(test)

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

            # -------------------------
            # 進捗
            # -------------------------
            done += 1
            pct = int(done / total_patterns * 100) if total_patterns else 100

            if pct != last_pct:
                progress_bar.progress(pct)
                bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                status_text.markdown(
                    f"""
**進捗:** {pct}%  
**試行中:** {done:,} / {total_patterns:,}

{bar}

塗り替え候補マス数: **{len(paint_cands)}** / 48  
起点候補（平均）は探索中に変動するよ
"""
                )
                last_pct = pct

    return best, paint_cands


if st.button("解析開始"):
    if st.session_state.fixed_field is None:
        st.error("先に 📌盤面確定 を押してね！")
        st.stop()

    base_field = copy_field(st.session_state.fixed_field)
    nexts = st.session_state.next

    with st.spinner("探索中…（爆速化してるけど少し待ってね）"):
        results, paint_cands = run_search(base_field, nexts, paint_color, paint_count)

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

            view = copy_field(base_field)

            # 塗り替え
            for rr, cc in r["paint"]:
                view[rr][cc] = paint_color

            # ネクスト落下
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
