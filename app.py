from itertools import combinations
from math import comb
import copy
import time
import streamlit as st

# =========================================================
# 基本設定
# =========================================================
ROWS = 6
COLS = 8
DIR4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]

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

MARK_PAINT = "🖌️"   # 塗り替えマーク（表示用）
MARK_START = "✂️"   # 起点マーク（表示用）

# =========================================================
# 連結探索（指定色の連結サイズを数える）
# =========================================================
def count_component(field, sr, sc, color, blocked=None):
    if blocked is None:
        blocked = set()
    if not (0 <= sr < ROWS and 0 <= sc < COLS):
        return 0
    if (sr, sc) in blocked:
        return 0
    if field[sr][sc] != color:
        return 0

    stack = [(sr, sc)]
    seen = {(sr, sc)}
    while stack:
        r, c = stack.pop()
        for dr, dc in DIR4:
            nr, nc = r + dr, c + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS:
                if (nr, nc) in blocked:
                    continue
                if (nr, nc) not in seen and field[nr][nc] == color:
                    seen.add((nr, nc))
                    stack.append((nr, nc))
    return len(seen)

# =========================================================
# 「盤面全体で消えるものがあるか」
# =========================================================
def has_any_erase_global(field):
    visited = [[False] * COLS for _ in range(ROWS)]
    erase = set()

    for r in range(ROWS):
        for c in range(COLS):
            if visited[r][c]:
                continue
            v = field[r][c]
            if v in ("空", "ハート"):
                visited[r][c] = True
                continue

            stack = [(r, c)]
            visited[r][c] = True
            comp = [(r, c)]
            while stack:
                cr, cc = stack.pop()
                for dr, dc in DIR4:
                    nr, nc = cr + dr, cc + dc
                    if 0 <= nr < ROWS and 0 <= nc < COLS:
                        if not visited[nr][nc] and field[nr][nc] == v:
                            visited[nr][nc] = True
                            stack.append((nr, nc))
                            comp.append((nr, nc))

            if len(comp) >= 4:
                erase |= set(comp)

    if not erase:
        return False

    # ハート巻き込み
    for r in range(ROWS):
        for c in range(COLS):
            if field[r][c] == "ハート":
                for dr, dc in DIR4:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < ROWS and 0 <= nc < COLS:
                        if (nr, nc) in erase:
                            return True
    return True

# =========================================================
# 「塗り替え直後に消える」判定を局所だけで行う（高速）
# =========================================================
def local_has_erase_after_recolor(field, changed_cells):
    focus = set()
    for (r, c) in changed_cells:
        focus.add((r, c))
        for dr, dc in DIR4:
            nr, nc = r + dr, c + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS:
                focus.add((nr, nc))

    checked = set()
    for (r, c) in focus:
        v = field[r][c]
        if v in ("空", "ハート"):
            continue
        if (r, c, v) in checked:
            continue
        size = count_component(field, r, c, v)
        if size >= 4:
            return True
        checked.add((r, c, v))

    # ハート巻き込み（念のため）
    for (r, c) in focus:
        if field[r][c] != "ハート":
            continue
        for dr, dc in DIR4:
            nr, nc = r + dr, c + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS:
                v = field[nr][nc]
                if v in ("空", "ハート"):
                    continue
                if count_component(field, nr, nc, v) >= 4:
                    return True
    return False

# =========================================================
# 消去1ステップ（消える前の色も返す）
# =========================================================
def erase_step_with_colors(field):
    visited = [[False] * COLS for _ in range(ROWS)]
    erase = set()

    for r in range(ROWS):
        for c in range(COLS):
            if visited[r][c]:
                continue
            v = field[r][c]
            if v in ("空", "ハート"):
                visited[r][c] = True
                continue

            stack = [(r, c)]
            visited[r][c] = True
            comp = [(r, c)]
            while stack:
                cr, cc = stack.pop()
                for dr, dc in DIR4:
                    nr, nc = cr + dr, cc + dc
                    if 0 <= nr < ROWS and 0 <= nc < COLS:
                        if not visited[nr][nc] and field[nr][nc] == v:
                            visited[nr][nc] = True
                            stack.append((nr, nc))
                            comp.append((nr, nc))

            if len(comp) >= 4:
                erase |= set(comp)

    # ハート巻き込み
    if erase:
        heart_add = set()
        for r in range(ROWS):
            for c in range(COLS):
                if field[r][c] == "ハート":
                    for dr, dc in DIR4:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < ROWS and 0 <= nc < COLS:
                            if (nr, nc) in erase:
                                heart_add.add((r, c))
        erase |= heart_add

    if not erase:
        return set(), {}, False

    before = {(r, c): field[r][c] for (r, c) in erase}

    for (r, c) in erase:
        field[r][c] = "空"

    # 落下
    for c in range(COLS):
        stack = []
        for r in range(ROWS - 1, -1, -1):
            if field[r][c] != "空":
                stack.append(field[r][c])

        idx = 0
        for r in range(ROWS - 1, -1, -1):
            if idx < len(stack):
                field[r][c] = stack[idx]
                idx += 1
            else:
                field[r][c] = "空"

    return erase, before, True

# =========================================================
# 起点消し→連鎖→得点
# =========================================================
def simulate_with_start_scoring(field, nexts, recolored_cells_set, start_pos):
    f = copy.deepcopy(field)

    # ネクスト落下
    for c, color in enumerate(nexts):
        for r in range(ROWS):
            if f[r][c] == "空":
                f[r][c] = color
                break

    sr, sc = start_pos
    if f[sr][sc] == "空":
        return 0, 0, 0, False

    # 起点消し（得点0）
    f[sr][sc] = "空"

    # 起点消し後 落下
    for c in range(COLS):
        stack = []
        for r in range(ROWS - 1, -1, -1):
            if f[r][c] != "空":
                stack.append(f[r][c])
        idx = 0
        for r in range(ROWS - 1, -1, -1):
            if idx < len(stack):
                f[r][c] = stack[idx]
                idx += 1
            else:
                f[r][c] = "空"

    chains = 0
    score = 0
    maxsim = 0

    while True:
        erased_set, before_colors, ok = erase_step_with_colors(f)
        if not ok:
            break

        chains += 1
        maxsim = max(maxsim, len(erased_set))

        # 得点：通常色のみ
        for (r, c) in erased_set:
            col = before_colors[(r, c)]
            if col == "ハート":
                continue
            if (r, c) == (sr, sc):
                continue
            if (r, c) in recolored_cells_set:
                continue
            score += 1

    return chains, score, maxsim, True

# =========================================================
# 起点候補の絞り込み（高速）
# =========================================================
def is_good_start_candidate(field, pos):
    r, c = pos
    if field[r][c] == "空":
        return False

    blocked = {pos}
    for dr, dc in DIR4:
        nr, nc = r + dr, c + dc
        if 0 <= nr < ROWS and 0 <= nc < COLS:
            v = field[nr][nc]
            if v in ("空", "ハート"):
                continue
            if count_component(field, nr, nc, v, blocked=blocked) >= 4:
                return True
    return False

def compute_start_candidates(field):
    cands = []
    for r in range(ROWS):
        for c in range(COLS):
            if is_good_start_candidate(field, (r, c)):
                cands.append((r, c))
    return cands

# =========================================================
# 塗り替え候補の列挙（単発で即消えるマスを除外）
# =========================================================
def compute_recolor_candidates(base_field, paint_color):
    cands = []
    for r in range(ROWS):
        for c in range(COLS):
            v = base_field[r][c]
            if v == "空":
                continue
            if v == paint_color:
                continue

            tmp = [row[:] for row in base_field]
            tmp[r][c] = paint_color

            if local_has_erase_after_recolor(tmp, {(r, c)}):
                continue

            cands.append((r, c))
    return cands

# =========================================================
# Streamlit UI
# =========================================================
st.set_page_config(layout="wide")
st.title("ぷよクエ 盤面エディタ＆探索（キーぷよ無し版）")

# ---------------------
# 状態
# ---------------------
if "field" not in st.session_state:
    st.session_state.field = [["空"] * COLS for _ in range(ROWS)]
if "history" not in st.session_state:
    st.session_state.history = []
if "current_color" not in st.session_state:
    st.session_state.current_color = "赤"
if "fixed_field" not in st.session_state:
    st.session_state.fixed_field = None
if "save_slots" not in st.session_state:
    st.session_state.save_slots = [None, None, None]
if "next" not in st.session_state:
    st.session_state.next = ["赤"] * COLS

def push_history():
    st.session_state.history.append(copy.deepcopy(st.session_state.field))
    if len(st.session_state.history) > 50:
        st.session_state.history.pop(0)

def undo():
    if st.session_state.history:
        st.session_state.field = st.session_state.history.pop()

# ---------------------
# パレット
# ---------------------
st.header("色パレット")
pal_cols = st.columns(len(COLORS))
for i, color in enumerate(COLORS):
    with pal_cols[i]:
        if st.button(EMOJI[color], key=f"pal_{color}"):
            st.session_state.current_color = color

st.markdown(f"### 選択中： {EMOJI[st.session_state.current_color]} {st.session_state.current_color}")

# ---------------------
# 操作
# ---------------------
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

# ---------------------
# 保存
# ---------------------
st.header("保存")
for i in range(3):
    c1, c2 = st.columns(2)
    with c1:
        if st.button(f"保存{i+1}", key=f"save_{i}"):
            st.session_state.save_slots[i] = copy.deepcopy(st.session_state.field)
    with c2:
        if st.button(f"読込{i+1}", key=f"load_{i}"):
            if st.session_state.save_slots[i] is not None:
                push_history()
                st.session_state.field = copy.deepcopy(st.session_state.save_slots[i])

# ---------------------
# 盤面編集
# ---------------------
st.header("盤面（クリックで塗る）")
for r in range(ROWS):
    row_cols = st.columns(COLS)
    for c in range(COLS):
        with row_cols[c]:
            label = EMOJI[st.session_state.field[r][c]]
            if st.button(label, key=f"cell_{r}_{c}"):
                push_history()
                st.session_state.field[r][c] = st.session_state.current_color

st.markdown("### 編集中盤面")
for r in range(ROWS):
    st.write(" ".join(EMOJI[st.session_state.field[r][c]] for c in range(COLS)))

# ---------------------
# 確定盤面
# ---------------------
if st.session_state.fixed_field is not None:
    st.markdown("## 📌 確定盤面")
    for r in range(ROWS):
        st.write(" ".join(EMOJI[st.session_state.fixed_field[r][c]] for c in range(COLS)))

# ---------------------
# ネクスト
# ---------------------
st.header("ネクスト（手入力）")
ncols = st.columns(COLS)
for i in range(COLS):
    with ncols[i]:
        st.session_state.next[i] = st.selectbox(
            f"n{i+1}",
            NORMAL_COLORS,
            index=NORMAL_COLORS.index(st.session_state.next[i]),
            key=f"next_{i}",
            label_visibility="collapsed",
        )
st.write(" ".join(EMOJI[c] for c in st.session_state.next))

# =========================================================
# 探索UI
# =========================================================
st.markdown("---")
st.header("探索（塗り替え → 塗り替え直後は消えない → 起点1個消して連鎖）")

paint_color = st.selectbox("塗り替え色（この色にする）", NORMAL_COLORS + ["ハート"])
paint_count = st.number_input("塗り替え数（最大12）", min_value=0, max_value=12, value=12)

min_k = max(0, int(paint_count) - 4)
st.caption(f"枝切りA案: 塗り替え数は {min_k} ～ {paint_count} で探索")

progress_bar = st.progress(0)
status_text = st.empty()

# ---------------------
# 探索本体
# ---------------------
def run_search(base_field, nexts, paint_color, paint_count, min_k):
    if has_any_erase_global(base_field):
        return [], {
            "reason": "確定盤面の時点で4つ以上が成立して消える状態です（塗り替え前に消える）",
            "recolor_candidates": None,
            "start_candidates": None,
        }

    recolor_cands = compute_recolor_candidates(base_field, paint_color)
    base_start_cands = compute_start_candidates(base_field)

    info = {
        "reason": None,
        "recolor_candidates": len(recolor_cands),
        "start_candidates": len(base_start_cands),
    }

    if len(recolor_cands) == 0:
        info["reason"] = "塗り替え候補が0マスでした"
        return [], info

    total_patterns = 0
    for k in range(min_k, paint_count + 1):
        if k <= len(recolor_cands):
            total_patterns += comb(len(recolor_cands), k)

    if total_patterns == 0:
        info["reason"] = "探索パターン数が0になりました"
        return [], info

    est_total_trials = total_patterns * max(1, len(base_start_cands))

    best = []
    done_patterns = 0
    done_trials = 0

    last_update = 0.0
    last_pct = -1
    t0 = time.time()

    for k in range(min_k, paint_count + 1):
        if k > len(recolor_cands):
            continue

        for combi in combinations(recolor_cands, k):
            field = [row[:] for row in base_field]
            changed = set(combi)

            for (r, c) in combi:
                field[r][c] = paint_color

            # 必須：塗り替え直後に消えない
            if local_has_erase_after_recolor(field, changed):
                done_patterns += 1
                continue

            # 起点候補：ベース＋塗り替え近傍で増える分
            start_cands = list(base_start_cands)
            near = set()
            for (r, c) in changed:
                near.add((r, c))
                for dr, dc in DIR4:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < ROWS and 0 <= nc < COLS:
                        near.add((nr, nc))

            base_set = set(base_start_cands)
            for pos in near:
                if pos in base_set:
                    continue
                if is_good_start_candidate(field, pos):
                    start_cands.append(pos)

            recolored_set = set(changed)

            best_local = None

            for sp in start_cands:
                done_trials += 1
                chains, score, maxsim, ok = simulate_with_start_scoring(
                    field, nexts, recolored_set, sp
                )
                if not ok:
                    continue

                # 条件：連鎖が1以上
                if chains >= 1:
                    cand = {
                        "chains": chains,
                        "score": score,
                        "maxsim": maxsim,
                        "recolor": tuple(sorted(changed)),
                        "start": sp,
                    }
                    if (best_local is None) or (cand["score"], cand["chains"], cand["maxsim"]) > (
                        best_local["score"], best_local["chains"], best_local["maxsim"]
                    ):
                        best_local = cand

            if best_local is not None:
                best.append(best_local)
                best = sorted(best, key=lambda x: (x["score"], x["chains"], x["maxsim"]), reverse=True)[:3]

            done_patterns += 1

            # 進捗（0.5秒ごと）
            now = time.time()
            pct = int(done_patterns / total_patterns * 100)
            if now - last_update >= 0.5 and pct != last_pct:
                progress_bar.progress(min(100, pct))
                status_text.markdown(
                    f"**進捗:** {pct}%\n\n"
                    f"**パターン:** {done_patterns:,} / {total_patterns:,}\n\n"
                    f"**試行中(概算):** {done_trials:,} / {est_total_trials:,}\n"
                    f"**経過:** {int(now - t0)}s\n"
                )
                last_update = now
                last_pct = pct

    progress_bar.progress(100)

    if not best:
        info["reason"] = "条件を満たす結果が見つからなかった（塗り替え直後に消えない＆起点から連鎖が起きない）"

    return best, info

# =========================================================
# 実行ボタン
# =========================================================
if st.button("解析開始"):
    if st.session_state.fixed_field is None:
        st.error("先に「📌 盤面確定」を押してね")
        st.stop()

    base_field = [row[:] for row in st.session_state.fixed_field]
    nexts = list(st.session_state.next)

    with st.spinner("探索中…"):
        results, info = run_search(base_field, nexts, paint_color, int(paint_count), min_k)

    st.success("完了")

    st.markdown(
        f"### 塗り替え候補マス数: **{info['recolor_candidates']}** / 48\n"
        f"### 起点候補マス数（確定盤面ベース）: **{info['start_candidates']}** / 48"
    )

    if info.get("reason"):
        st.warning(info["reason"])

    if not results:
        st.write("見つからず")
    else:
        st.markdown("## 上位候補（最大3件）")
        for i, r in enumerate(results, start=1):
            st.markdown(f"### {i}位")
            st.write(f"得点: {r['score']} / 連鎖: {r['chains']} / 同時最大: {r['maxsim']}")
            st.write(f"起点（消すマス）: {r['start']}  ※起点は得点0")
            st.write(f"塗り替えマス数: {len(r['recolor'])}  ※塗り替えは得点0")
            st.write(f"塗り替え座標: {r['recolor']}")

            shown = [row[:] for row in base_field]
            recolor_set = set(r["recolor"])
            sr, sc = r["start"]

            for rr in range(ROWS):
                out = []
                for cc in range(COLS):
                    cell = shown[rr][cc]
                    if (rr, cc) == (sr, sc):
                        out.append(MARK_START)
                    elif (rr, cc) in recolor_set:
                        out.append(MARK_PAINT)
                    else:
                        out.append(EMOJI[cell])
                st.write(" ".join(out))
            st.markdown("---")
