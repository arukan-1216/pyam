from itertools import combinations
import copy
import streamlit as st

# =========================
# 定数
# =========================
ROWS = 6
COLS = 8
DIR4 = [(1,0),(-1,0),(0,1),(0,-1)]

COLORS = ["赤","青","緑","黄","紫","ハート","空"]
COLORS_DROP = ["赤","青","緑","黄","紫"]      # ネクスト入力用
COLORS_ALL = ["赤","青","緑","黄","紫","ハート"]  # 塗り替え色用（空は除外）

EMOJI = {
    "赤":"🟥","青":"🟦","緑":"🟩",
    "黄":"🟨","紫":"🟪","ハート":"💖","空":"⬛"
}

# =========================
# ぷよシミュ
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


def apply_gravity(field):
    """列ごとに落下"""
    for c in range(COLS):
        stack = []
        for r in range(ROWS-1, -1, -1):
            if field[r][c] != "空":
                stack.append(field[r][c])

        # 下から詰める
        for r in range(ROWS-1, -1, -1):
            if stack:
                field[r][c] = stack.pop(0)
            else:
                field[r][c] = "空"


def erase_step(field):
    """
    1回分の消去＆落下
    return:
      erased_normal: 通常色の消去数（ハート除外）
      erased_simul: 同時消去数（ハート含む）
      ok: 消去が起きたか
    """
    groups = find_groups(field)
    erase = set()

    # 通常色：4つ以上で消える（ハートは消えない）
    for color, cells in groups:
        if color in ["空", "ハート"]:
            continue
        if len(cells) >= 4:
            erase |= set(cells)

    # ハート巻き込み：
    # 4つ繋がっても消えないが、消えるぷよに隣接してたら消える
    heart_add = set()
    for r in range(ROWS):
        for c in range(COLS):
            if field[r][c] == "ハート":
                for dr, dc in DIR4:
                    nr, nc = r+dr, c+dc
                    if 0 <= nr < ROWS and 0 <= nc < COLS:
                        if (nr, nc) in erase:
                            heart_add.add((r,c))
                            break
    erase |= heart_add

    if not erase:
        return 0, 0, False

    # 消去
    erased_normal = 0
    for r, c in erase:
        if field[r][c] not in ["空", "ハート"]:
            erased_normal += 1
        field[r][c] = "空"

    # 落下
    apply_gravity(field)

    return erased_normal, len(erase), True


def simulate(field, nexts):
    """
    field: 6x8
    nexts: 8個（各列に1個ずつ落とす）
    """
    field = copy.deepcopy(field)

    # ネクスト落下（各列の「一番下の空き」に入れる）
    for c, color in enumerate(nexts):
        for r in range(ROWS-1, -1, -1):
            if field[r][c] == "空":
                field[r][c] = color
                break

    chains = 0
    total_normal = 0
    max_simul = 0

    while True:
        erased_normal, erased_simul, ok = erase_step(field)
        if not ok:
            break

        chains += 1
        total_normal += erased_normal
        max_simul = max(max_simul, erased_simul)

    return chains, total_normal, max_simul, field


# =========================
# Streamlit UI
# =========================
st.set_page_config(layout="wide")
st.title("ぷよクエ盤面エディタ（キー無し版）")

# ---- session state ----
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
    st.session_state.next = ["赤"] * COLS


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
st.header("色パレット")

pal_cols = st.columns(len(COLORS))
for i, color in enumerate(COLORS):
    with pal_cols[i]:
        if st.button(EMOJI[color], key=f"pal_{color}"):
            st.session_state.current_color = color

st.markdown(f"## 選択中： {EMOJI[st.session_state.current_color]} {st.session_state.current_color}")


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
st.header("保存")
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
st.header("盤面（クリックで塗る）")

for r in range(ROWS):
    row_cols = st.columns(COLS)
    for c in range(COLS):
        with row_cols[c]:
            label = EMOJI[st.session_state.field[r][c]]
            if st.button(label, key=f"cell_{r}_{c}"):
                push_history()
                st.session_state.field[r][c] = st.session_state.current_color


# =====================
# 表示
# =====================
st.markdown("### 編集中盤面")
for r in range(ROWS):
    st.write(" ".join(EMOJI[st.session_state.field[r][c]] for c in range(COLS)))


# =====================
# 確定盤面表示
# =====================
if st.session_state.fixed_field is not None:
    st.markdown("## 📌 確定盤面")
    for r in range(ROWS):
        st.write(" ".join(EMOJI[st.session_state.fixed_field[r][c]] for c in range(COLS)))


# =====================
# ネクスト
# =====================
st.header("ネクスト（8個）")
ncols = st.columns(COLS)
for i in range(COLS):
    with ncols[i]:
        st.session_state.next[i] = st.selectbox(
            label=f"next_{i}",
            options=COLORS_DROP,
            index=COLORS_DROP.index(st.session_state.next[i]),
            key=f"nextsel_{i}",
            label_visibility="collapsed"
        )

st.write(" ".join(EMOJI[c] for c in st.session_state.next))


# =========================
# 解析UI
# =========================
st.markdown("---")
st.header("解析（塗り替え全探索：1色）")

paint_color = st.selectbox("塗り替え色", COLORS_ALL)
paint_count = st.number_input("塗り替え数（最大12）", 0, 12, 0)

progress_bar = st.progress(0)
status_text = st.empty()


def get_candidates(field, paint_color):
    cands = []
    for r in range(ROWS):
        for c in range(COLS):
            v = field[r][c]
            if v == "空":
                continue
            if v == paint_color:
                continue  # 不毛なので除外
            cands.append((r, c))
    return cands


def run_search(base_field, nexts, paint_color, paint_count):
    cands = get_candidates(base_field, paint_color)
    best = []

    # paint_count=12なら 8〜12 だけ探索して軽量化
    min_k = max(0, paint_count - 4)

    # 総パターン数
    from math import comb
    total_patterns = 0
    for k in range(min_k, paint_count + 1):
        if k <= len(cands):
            total_patterns += comb(len(cands), k)

    if total_patterns == 0:
        return []

    done = 0
    last_pct = -1

    for k in range(min_k, paint_count + 1):
        for combi in combinations(cands, k):
            field = [row[:] for row in base_field]
            for r, c in combi:
                field[r][c] = paint_color

            chains, total, maxsim, final = simulate(field, nexts)

            # 条件：6連鎖 or 同時16以上
            ok = (chains >= 6) or (maxsim >= 16)

            if ok:
                best.append({
                    "chains": chains,
                    "total": total,
                    "maxsim": maxsim,
                    "pattern": combi
                })
                best = sorted(
                    best,
                    key=lambda x: (x["total"], x["chains"], x["maxsim"]),
                    reverse=True
                )[:3]

            # 進捗
            done += 1
            pct = int(done / total_patterns * 100)

            if pct != last_pct:
                progress_bar.progress(pct)
                bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                status_text.markdown(
                    f"**進捗:** {pct}%  \n"
                    f"**試行中:** {done:,} / {total_patterns:,}\n\n"
                    f"{bar}"
                )
                last_pct = pct

    return best


if st.button("解析開始"):
    if st.session_state.fixed_field is None:
        st.error("先に「盤面確定」してね")
        st.stop()

    base_field = [row[:] for row in st.session_state.fixed_field]
    nexts = st.session_state.next

    with st.spinner("探索中…"):
        results = run_search(base_field, nexts, paint_color, paint_count)

    st.success("完了")

    if not results:
        st.write("見つからず（条件を満たす塗り替えが無かった）")
    else:
        for i, r in enumerate(results):
            st.write(f"## {i+1}位")
            st.write(f"連鎖: {r['chains']}")
            st.write(f"総消去(ハート除外): {r['total']}")
            st.write(f"同時消去(ハート含む): {r['maxsim']}")
            st.write(f"塗り替え座標: {r['pattern']}")
