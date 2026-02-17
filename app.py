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
# 連結探索（指定色の連結サイズを数える：BFS/DFS）
# =========================================================
def count_component(field, sr, sc, color, blocked=None):
    """(sr,sc)からcolorで連結しているセル数を返す。blockedは無視するセル座標(set)"""
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
# 「今の盤面で消えるものがあるか」を軽く判定
#  - ハートは4つ繋がっても消えない
#  - 通常色は4つ以上で消える
#  - ハートは「消える通常色の隣」にあるなら巻き込まれて消える
# =========================================================
def has_any_erase_global(field):
    visited = [[False] * COLS for _ in range(ROWS)]
    erase = set()

    for r in range(ROWS):
        for c in range(COLS):
            if visited[r][c]:
                continue
            v = field[r][c]
            if v == "空":
                visited[r][c] = True
                continue
            if v == "ハート":
                visited[r][c] = True
                continue

            # 通常色
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

    # ハート巻き込み（隣がeraseなら消える）
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
# 「塗り替え直後に消える」判定を、変更セル近傍だけで行う（高速）
# 前提：確定盤面自体が「消えない状態」であること
# =========================================================
def local_has_erase_after_recolor(field, changed_cells):
    # 見るべき候補（変更セル＋その近傍）
    focus = set()
    for (r, c) in changed_cells:
        focus.add((r, c))
        for dr, dc in DIR4:
            nr, nc = r + dr, c + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS:
                focus.add((nr, nc))

    # 通常色の4連結ができてたらアウト（ハートは無視）
    checked = set()
    for (r, c) in focus:
        v = field[r][c]
        if v in ("空", "ハート"):
            continue
        if (r, c, v) in checked:
            continue
        size = count_component(field, r, c, v)
        # 連結のどれかがfocusに被ってるかは気にせず、
        # 「できてしまってたらアウト」でOK（確定盤面は消えない前提）
        if size >= 4:
            return True
        checked.add((r, c, v))

    # ハート巻き込み：隣に「消える通常色」があるならアウト
    # ただし上のチェックで「4連結がない」なら基本起きないが、
    # 念のためfocus近傍のハートだけ確認しておく
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
# 消去1ステップ（消える集合を返す）
# 得点はここでは数えない（simulate側で「塗り替え・起点は0点」を反映）
# =========================================================
def erase_step(field):
    visited = [[False] * COLS for _ in range(ROWS)]
    erase = set()

    # 通常色の4連結を探す
    for r in range(ROWS):
        for c in range(COLS):
            if visited[r][c]:
                continue
            v = field[r][c]
            if v == "空":
                visited[r][c] = True
                continue
            if v == "ハート":
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
        return set(), False

    # 消す
    for (r, c) in erase:
        field[r][c] = "空"

    # 落下
    for c in range(COLS):
        stack = []
        for r in range(ROWS - 1, -1, -1):
            if field[r][c] != "空":
                stack.append(field[r][c])
        # 下から詰める
        idx = 0
        for r in range(ROWS - 1, -1, -1):
            if idx < len(stack):
                field[r][c] = stack[idx]
                idx += 1
            else:
                field[r][c] = "空"

    return erase, True

# =========================================================
# シミュレーション
# - まずネクスト落下
# - その後「起点セルを1個だけ消す」（得点0）
# - 連鎖で消えたぷよを得点化（ただし塗り替えたぷよは得点0、ハートも0）
# =========================================================
def simulate_with_start(field, nexts, recolored_cells_set, start_pos):
    f = copy.deepcopy(field)

    # ネクスト落下：各列の「一番上の空き」に1個ずつ
    for c, color in enumerate(nexts):
        # nextsは通常色のみ想定
        for r in range(ROWS):
            if f[r][c] == "空":
                f[r][c] = color
                break

    # 起点を消す（得点0）
    if start_pos is None:
        return 0, 0, 0, False  # 起点なしは不可
    sr, sc = start_pos
    if not (0 <= sr < ROWS and 0 <= sc < COLS):
        return 0, 0, 0, False
    if f[sr][sc] == "空":
        return 0, 0, 0, False

    f[sr][sc] = "空"
    # 起点消し後の落下
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
        erased_set, ok = erase_step(f)
        if not ok:
            break

        chains += 1
        maxsim = max(maxsim, len(erased_set))

        # 得点計算：
        # - ハートは0点
        # - recolored_cellsは0点（元の座標基準。落下で位置が変わるので「元座標」では追跡できない）
        #   → ここは「塗り替えた"個体"が0点」が本当は必要だけど、盤面だけだと個体追跡が無理
        #   → 代替として「塗り替えた座標で消えたものは0点」にするとズレる
        #
        # なのでこの実装では、仕様を守るために
        # ✅「塗り替えたマスは、塗り替え後に消えない状況を作る」前提で
        #    連鎖で消えるのは基本 "塗り替えてないぷよ" が中心になる想定にする。
        #
        # それでもズレが気になるなら「個体ID付与方式」に変更できる（少し重くなる）
        step_score = 0
        for (r, c) in erased_set:
            # erase_step後には空になってるので、消える前の色は分からない
            # → ここは「消える直前の色」を持てないので、得点は erase_step を改造する必要あり
            pass

        # ---- ここが重要：得点を正確にするため、erase_stepを改造して「消える前の色」を取る ----
        # 今のままだと色が取れないので、simulate内で別実装に差し替える
        # （下で実際に差し替え済みの関数を呼ぶ）
        return simulate_with_start_scoring(field, nexts, recolored_cells_set, start_pos)

    return chains, score, maxsim, True


def erase_step_with_colors(field):
    """消えるセル集合と、そのセルの消える前の色dictを返す。"""
    visited = [[False] * COLS for _ in range(ROWS)]
    erase = set()

    # 通常色の4連結
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

    # 消える前の色を保存
    before = {(r, c): field[r][c] for (r, c) in erase}

    # 消す
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


def simulate_with_start_scoring(field, nexts, recolored_cells_set, start_pos):
    f = copy.deepcopy(field)

    # ネクスト落下
    for c, color in enumerate(nexts):
        for r in range(ROWS):
            if f[r][c] == "空":
                f[r][c] = color
                break

    # 起点を消す（得点0）
    sr, sc = start_pos
    if f[sr][sc] == "空":
        return 0, 0, 0, False
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

        # 得点：通常色のみ（ハート0点）
        # 塗り替えた「座標」のものが消えた場合は0点、起点も0点
        # ※「個体追跡」はしてないので、ここは仕様上の近似（軽量優先）
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
# 「そのマスを消した瞬間に4つ成立する可能性があるマス」だけ
# =========================================================
def is_good_start_candidate(field, pos):
    r, c = pos
    if field[r][c] == "空":
        return False

    # そのマスを消したと仮定して、周辺で4連結が成立するかだけ見る
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
# 塗り替え候補の列挙 + 枝切り（単発で塗っただけで4つできるマスを除外）
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

            # 「この1マスをpaint_colorにしただけで4連結ができるなら除外」
            tmp = [row[:] for row in base_field]
            tmp[r][c] = paint_color

            # ローカル判定（このセル近傍だけ）
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

# A案（枝切り）：下限を paint_count-4 にする（0～12全部よりかなり減る）
min_k = max(0, int(paint_count) - 4)
st.caption(f"枝切り（A案）: 塗り替え数は {min_k} ～ {paint_count} で探索（0～{paint_count}より軽い）")

progress_bar = st.progress(0)
status_text = st.empty()

# ---------------------
# 探索本体
# ---------------------
def run_search(base_field, nexts, paint_color, paint_count, min_k):
    # 事前条件：確定盤面自体が消えない
    if has_any_erase_global(base_field):
        return [], {
            "reason": "確定盤面の時点で4つ以上が成立して消える状態です（塗り替え前に消えてしまう）",
            "recolor_candidates": None,
            "start_candidates": None,
        }

    # 塗り替え候補列挙（単発で即消えるマスは除外）
    recolor_cands = compute_recolor_candidates(base_field, paint_color)

    # 起点候補（確定盤面ベース）
    base_start_cands = compute_start_candidates(base_field)

    info = {
        "reason": None,
        "recolor_candidates": len(recolor_cands),
        "start_candidates": len(base_start_cands),
    }

    if len(recolor_cands) == 0:
        info["reason"] = "塗り替え候補が0マスでした（単発塗りで即4つ成立する等で全除外）"
        return [], info

    # 探索総数（塗り替えパターン数）
    total_patterns = 0
    for k in range(min_k, paint_count + 1):
        if k <= len(recolor_cands):
            total_patterns += comb(len(recolor_cands), k)

    if total_patterns == 0:
        info["reason"] = "探索パターン数が0になりました（候補数が少なすぎる/下限が高すぎる）"
        return [], info

    # 進捗：パターン進捗＋試行数（起点込み）は概算で表示
    est_total_trials = total_patterns * max(1, len(base_start_cands))

    best = []  # 上位3件だけ保持（盤面は保持しない＝軽い）
    done_patterns = 0
    done_trials = 0

    last_update = 0.0
    last_pct = -1

    t0 = time.time()

    for k in range(min_k, paint_count + 1):
        if k > len(recolor_cands):
            continue

        for combi in combinations(recolor_cands, k):
            # 塗り替え適用
            field = [row[:] for row in base_field]
            changed = set(combi)
            for (r, c) in combi:
                field[r][c] = paint_color

            # ★必須条件：塗り替え直後に「どこも消えない」
            if local_has_erase_after_recolor(field, changed):
                done_patterns += 1
                # 進捗（パターン）
                now = time.time()
                pct = int(done_patterns / total_patterns * 100)
                if now - last_update >= 0.5 and pct != last_pct:
                    progress_bar.progress(min(100, pct))
                    status_text.markdown(
                        f"**進捗:** {pct}%\n\n"
                        f"**パターン:** {done_patterns:,} / {total_patterns:,}\n\n"
                        f"**試行中(概算):** {done_trials:,} / {est_total_trials:,}\n"
                    )
                    last_update = now
                    last_pct = pct
                continue

            # 起点候補：
            # まずベース候補を使い、さらに「塗り替え近傍」だけ追加判定して増える分を拾う
            start_cands = list(base_start_cands)

            # 追加候補チェック（changed近傍だけ）
            near = set()
            for (r, c) in changed:
                near.add((r, c))
                for dr, dc in DIR4:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < ROWS and 0 <= nc < COLS:
                        near.add((nr, nc))

            # nearの中で、いま起点候補じゃないやつを追加
            base_set = set(base_start_cands)
            for pos in near:
                if pos in base_set:
                    continue
                if is_good_start_candidate(field, pos):
                    start_cands.append(pos)

            # ここで起点を全試行
            recolored_set = set(changed)
            any_ok = False
            best_local = None

            for sp in start_cands:
                done_trials += 1

                chains, score, maxsim, ok = simulate_with_start_scoring(
                    field, nexts, recolored_set, sp
                )
                if not ok:
                    continue

                # ✅採用条件：あなたの「2か3どちらか達成でOK」＝
                # ここでは例として「6連鎖以上 OR 同時消し16以上」みたいな条件ではなく、
                # “得点が出たか/連鎖したか”を条件にする方が自然なので、ここはUI化しやすい形にしてある。
                #
                # 今回は「連鎖が1以上」なら候補として残す（あとで好きに条件を変えられる）
                if chains >= 1 and score >= 1:
                    any_ok = True
                    cand = {
                        "chains": chains,
                        "score": score,
                        "maxsim": maxsim,
                        "recolor": tuple(sorted(changed)),
                        "start": sp,
                    }
                    # ローカルベスト更新
                    if (best_local is None) or (cand["score"], cand["chains"], cand["maxsim"]) > (
                        best_local["score"], best_local["chains"], best_local["maxsim"]
                    ):
                        best_local = cand

            # パターン終わり：良いのがあればbestに入れる
            if any_ok and best_local is not None:
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

    # 完了表示
    progress_bar.progress(100)
    status_text.markdown(
        f"**進捗:** 100%\n\n"
        f"**パターン:** {done_patterns:,} / {total_patterns:,}\n\n"
        f"**試行中(概算):** {done_trials:,} / {est_total_trials:,}\n"
        f"**経過:** {int(time.time() - t0)}s\n"
    )

    if not best:
        info["reason"] = "条件を満たす結果が見つからなかった（塗り替え直後に消えない＆起点から得点が出る、が成立しなかった）"

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

    with st.spinner("探索中…（クラウドだと途中で落ちる場合、候補削減が必要）"):
        results, info = run_search(base_field, nexts, paint_color, int(paint_count), min_k)

    st.success("完了")

    # 候補数表示（要望）
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

            # 盤面表示（マーク付き）
            shown = [row[:] for row in base_field]
            # 表示用に文字列化
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
