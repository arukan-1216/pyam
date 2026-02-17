import streamlit as st
import copy
from itertools import combinations
from math import comb

# =========================
# 定数
# =========================
ROWS = 6
COLS = 8

DIR4 = [(1,0),(-1,0),(0,1),(0,-1)]

COLORS = ["赤","青","緑","黄","紫","ハート","空"]
EMOJI = {
    "赤":"🟥","青":"🟦","緑":"🟩",
    "黄":"🟨","紫":"🟪","ハート":"💖","空":"⬛"
}

NEXT_COLORS = ["赤","青","緑","黄","紫"]

# =========================
# 連結数（局所判定用）
# =========================
def count_connected(field, sr, sc):
    """(sr,sc) と同色の連結数を数える（空は0）"""
    color = field[sr][sc]
    if color == "空":
        return 0

    visited = set()
    stack = [(sr, sc)]
    visited.add((sr, sc))

    while stack:
        r, c = stack.pop()
        for dr, dc in DIR4:
            nr, nc = r+dr, c+dc
            if 0 <= nr < ROWS and 0 <= nc < COLS:
                if (nr, nc) not in visited and field[nr][nc] == color:
                    visited.add((nr, nc))
                    stack.append((nr, nc))

    return len(visited)

def will_erase_if_painted(field, r, c, paint_color):
    """
    (r,c) を paint_color に塗った瞬間に
    4つ以上が成立するなら True
    ※盤面全体は見ない。局所だけ。
    """
    if field[r][c] == "空":
        return False
    if field[r][c] == paint_color:
        return False

    # 一時的に塗る
    original = field[r][c]
    field[r][c] = paint_color

    # そのマスの連結だけ見れば十分
    cnt = count_connected(field, r, c)

    # 戻す
    field[r][c] = original

    return cnt >= 4

# =========================
# グループ探索（消去判定）
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
                        if not visited[nr][nc] and field[nr][nc] == color:
                            visited[nr][nc] = True
                            stack.append((nr,nc))
                            comp.append((nr,nc))

            groups.append((color, comp))

    return groups

def erase_step(field):
    """
    1ステップ消す
    return:
      erased_normal_count（ハートは得点0なので数えない）
      erased_total_count（ハート込みの同時消し数）
      ok（消えたかどうか）
    """
    groups = find_groups(field)
    erase = set()

    # 通常色（赤青緑黄紫）だけが4以上で消える
    for color, cells in groups:
        if color in ["赤","青","緑","黄","紫"]:
            if len(cells) >= 4:
                erase |= set(cells)

    # ハートは「4つで消えない」
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

    normal_count = 0
    for r, c in erase:
        if field[r][c] != "ハート":
            normal_count += 1
        field[r][c] = "空"

    # 落下
    for c in range(COLS):
        stack = []
        for r in range(ROWS-1, -1, -1):
            if field[r][c] != "空":
                stack.append(field[r][c])
        for r in range(ROWS-1, -1, -1):
            field[r][c] = stack.pop(0) if stack else "空"

    return normal_count, len(erase), True

def simulate_chain(field):
    """
    盤面が自然に消えるだけ消す
    return:
      chains
      total_erased_normal（ハート除外）
      max_simul_total（ハート込みの同時消し最大）
      final_field
    """
    field = copy.deepcopy(field)

    chains = 0
    total = 0
    maxsim = 0

    while True:
        erased_normal, erased_total, ok = erase_step(field)
        if not ok:
            break
        chains += 1
        total += erased_normal
        maxsim = max(maxsim, erased_total)

    return chains, total, maxsim, field

def drop_nexts(field, nexts):
    """
    ネクスト8個を
    各列の「一番上の空き」に1個ずつ入れる（A方式）
    """
    field = copy.deepcopy(field)
    for c, color in enumerate(nexts):
        for r in range(ROWS):
            if field[r][c] == "空":
                field[r][c] = color
                break
    return field

def remove_start_cell(field, start_pos):
    """
    起点ぷよを指で消す（得点0扱い）
    """
    field = copy.deepcopy(field)
    r, c = start_pos
    field[r][c] = "空"

    # 落下
    for cc in range(COLS):
        stack = []
        for rr in range(ROWS-1, -1, -1):
            if field[rr][cc] != "空":
                stack.append(field[rr][cc])
        for rr in range(ROWS-1, -1, -1):
            field[rr][cc] = stack.pop(0) if stack else "空"

    return field

# =========================
# Streamlit UI
# =========================
st.set_page_config(layout="wide")
st.title("ぷよクエ ぷよ使い大会：盤面エディタ＆塗り替え探索（起点1マス固定）")

# -------------------------
# 状態
# -------------------------
if "field" not in st.session_state:
    st.session_state.field = [["空"] * COLS for _ in range(ROWS)]

if "history" not in st.session_state:
    st.session_state.history = []

if "current_color" not in st.session_state:
    st.session_state.current_color = "赤"

if "mode" not in st.session_state:
    st.session_state.mode = "paint"  # paint / start

if "start_pos" not in st.session_state:
    st.session_state.start_pos = None

if "save_slots" not in st.session_state:
    st.session_state.save_slots = [None, None, None]

if "fixed_field" not in st.session_state:
    st.session_state.fixed_field = None

if "fixed_start" not in st.session_state:
    st.session_state.fixed_start = None

if "nexts" not in st.session_state:
    st.session_state.nexts = ["赤"] * 8

# -------------------------
# helper
# -------------------------
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
st.header("🎨 色パレット")

pal_cols = st.columns(len(COLORS))
for i, color in enumerate(COLORS):
    with pal_cols[i]:
        if st.button(EMOJI[color], key=f"pal_{color}"):
            st.session_state.current_color = color
            st.session_state.mode = "paint"

st.markdown(f"### 選択中： {EMOJI[st.session_state.current_color]} {st.session_state.current_color}")

m1, m2 = st.columns(2)
with m1:
    if st.button("🧨 起点ぷよ指定モード"):
        st.session_state.mode = "start"
with m2:
    st.write("モード:", "配置" if st.session_state.mode == "paint" else "起点指定")

# =====================
# 操作
# =====================
st.header("🛠 操作")

b1, b2, b3, b4, b5 = st.columns(5)

with b1:
    if st.button("🧹 盤面クリア"):
        push_history()
        st.session_state.field = [["空"] * COLS for _ in range(ROWS)]
        st.session_state.start_pos = None

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
    if st.button("起点解除"):
        st.session_state.start_pos = None

with b5:
    if st.button("📌 盤面確定"):
        st.session_state.fixed_field = copy.deepcopy(st.session_state.field)
        st.session_state.fixed_start = st.session_state.start_pos

# =====================
# 保存
# =====================
st.header("💾 保存")

for i in range(3):
    c1, c2 = st.columns(2)
    with c1:
        if st.button(f"保存{i+1}", key=f"save{i}"):
            st.session_state.save_slots[i] = copy.deepcopy(st.session_state.field)
    with c2:
        if st.button(f"読込{i+1}", key=f"load{i}"):
            if st.session_state.save_slots[i] is not None:
                push_history()
                st.session_state.field = copy.deepcopy(st.session_state.save_slots[i])

# =====================
# 盤面
# =====================
st.header("🧩 盤面（クリックで塗る）")

for r in range(ROWS):
    row_cols = st.columns(COLS)
    for c in range(COLS):
        with row_cols[c]:
            label = EMOJI[st.session_state.field[r][c]]
            if st.session_state.start_pos == (r, c):
                label = "⭐"

            if st.button(label, key=f"cell_{r}_{c}"):

                push_history()

                if st.session_state.mode == "paint":
                    st.session_state.field[r][c] = st.session_state.current_color

                elif st.session_state.mode == "start":
                    st.session_state.start_pos = (r, c)
                    st.session_state.mode = "paint"

# =====================
# 表示（編集）
# =====================
st.markdown("### 編集中盤面")
for r in range(ROWS):
    row = []
    for c in range(COLS):
        if st.session_state.start_pos == (r, c):
            row.append("⭐")
        else:
            row.append(EMOJI[st.session_state.field[r][c]])
    st.write(" ".join(row))

# =====================
# 確定盤面
# =====================
if st.session_state.fixed_field is not None:
    st.markdown("## 📌 確定盤面")
    for r in range(ROWS):
        row = []
        for c in range(COLS):
            if st.session_state.fixed_start == (r, c):
                row.append("⭐")
            else:
                row.append(EMOJI[st.session_state.fixed_field[r][c]])
        st.write(" ".join(row))

# =====================
# ネクスト
# =====================
st.header("⏬ ネクスト（8個）")

next_cols = st.columns(8)
for i in range(8):
    with next_cols[i]:
        st.session_state.nexts[i] = st.selectbox(
            f"next{i+1}",
            NEXT_COLORS,
            index=NEXT_COLORS.index(st.session_state.nexts[i]),
            key=f"next_{i}",
            label_visibility="collapsed"
        )

st.write(" ".join(EMOJI[c] for c in st.session_state.nexts))

# =====================
# 解析
# =====================
st.markdown("---")
st.header("🔍 解析（塗り替え全探索）")

paint_color = st.selectbox("塗り替え色", ["赤","青","緑","黄","紫","ハート"])
paint_count = st.number_input("塗り替え数（最大12）", 0, 12, 0)

# 進捗表示
progress_bar = st.progress(0)
status_text = st.empty()

def get_paint_candidates(base_field, paint_color):
    """
    塗り替え候補を列挙し、さらに
    「そのマスを塗った瞬間に4つ成立するなら除外」
    """
    cands = []
    tmp = copy.deepcopy(base_field)

    for r in range(ROWS):
        for c in range(COLS):
            v = tmp[r][c]
            if v == "空":
                continue
            if v == paint_color:
                continue

            # 1マスだけ塗って即消えるなら候補から除外
            if will_erase_if_painted(tmp, r, c, paint_color):
                continue

            cands.append((r, c))

    return cands

def run_search(base_field, start_pos, nexts, paint_color, paint_count):

    # --------------------------
    # 塗り替え候補（枝切り）
    # --------------------------
    cands = get_paint_candidates(base_field, paint_color)

    st.markdown(f"### ✅ 塗り替え候補マス数： **{len(cands)} / 48**")

    # min_k（探索削減）
    min_k = max(0, paint_count - 4)

    # 候補が少なすぎる場合
    if len(cands) < min_k:
        st.error(f"候補が少なすぎます（候補={len(cands)} / min_k={min_k}）")
        return []

    # --------------------------
    # 総パターン数計算
    # --------------------------
    total_patterns = 0
    for k in range(min_k, paint_count + 1):
        if k <= len(cands):
            total_patterns += comb(len(cands), k)

    if total_patterns == 0:
        st.error("探索できません（total_patterns=0）")
        return []

    best = []

    done = 0
    last_pct = -1

    for k in range(min_k, paint_count + 1):
        for combi in combinations(cands, k):

            # 盤面コピー known
            field = [row[:] for row in base_field]

            # --------------------------
            # 塗り替え適用
            # --------------------------
            for r, c in combi:
                field[r][c] = paint_color

            # --------------------------
            # ルール：塗り替え直後に消えたら廃案
            # → simulate_chainで消えるか確認
            # --------------------------
            chains0, _, _, after0 = simulate_chain(field)
            if chains0 > 0:
                done += 1
                continue

            # --------------------------
            # ネクスト落下
            # --------------------------
            field2 = drop_nexts(after0, nexts)

            # ネクスト落下で消えたら廃案
            chains1, _, _, after1 = simulate_chain(field2)
            if chains1 > 0:
                done += 1
                continue

            # --------------------------
            # 起点ぷよ（1個だけ手で消す）
            # --------------------------
            if start_pos is None:
                done += 1
                continue

            # 起点が空なら無理
            sr, sc = start_pos
            if after1[sr][sc] == "空":
                done += 1
                continue

            # 起点を消してから連鎖
            after_start = remove_start_cell(after1, start_pos)

            chains, total, maxsim, final = simulate_chain(after_start)

            # 条件：6連鎖 or 最大同時消し16
            if not (chains >= 6 or maxsim >= 16):
                done += 1
                continue

            # --------------------------
            # 採用（上位3件）
            # --------------------------
            best.append({
                "chains": chains,
                "total": total,
                "maxsim": maxsim,
                "pattern": combi,
                "final": final,
            })

            best = sorted(
                best,
                key=lambda x: (x["total"], x["chains"], x["maxsim"]),
                reverse=True
            )[:3]

            # --------------------------
            # 進捗更新
            # --------------------------
            done += 1
            pct = int(done / total_patterns * 100)

            if pct != last_pct:
                progress_bar.progress(pct)
                bar = "█" * (pct // 5) + "░" * (20 - pct // 5)

                status_text.markdown(f"""
**進捗:** {pct}%  
**試行中:** {done:,} / {total_patterns:,}

{bar}
""")
                last_pct = pct

    # 最後に100%に
    progress_bar.progress(100)
    status_text.markdown(f"""
**進捗:** 100%  
**試行中:** {total_patterns:,} / {total_patterns:,}

{"█"*20}
""")

    return best

if st.button("🚀 解析開始"):

    if st.session_state.fixed_field is None:
        st.error("先に 📌盤面確定 を押してね！")
        st.stop()

    if st.session_state.fixed_start is None:
        st.error("先に ⭐起点ぷよ を1マス指定してから 📌盤面確定 を押してね！")
        st.stop()

    base_field = [row[:] for row in st.session_state.fixed_field]
    start_pos = st.session_state.fixed_start
    nexts = st.session_state.nexts

    with st.spinner("探索中…（重いので待ってね）"):
        results = run_search(base_field, start_pos, nexts, paint_color, paint_count)

    st.success("完了！")

    if not results:
        st.warning("条件を満たす結果が見つからなかった！")
    else:
        st.markdown("## 🏆 上位3件")

        for i, r in enumerate(results, start=1):
            st.markdown(f"### {i}位")
            st.write(f"連鎖: {r['chains']}")
            st.write(f"総消去数（ハート除外）: {r['total']}")
            st.write(f"最大同時消し（ハート込み）: {r['maxsim']}")
            st.write(f"塗り替えた座標: {list(r['pattern'])}")

            st.markdown("**最終盤面**")
            for rr in range(ROWS):
                row = []
                for cc in range(COLS):
                    row.append(EMOJI[r["final"][rr][cc]])
                st.write(" ".join(row))

            st.markdown("---")
