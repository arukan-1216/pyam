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

DIR4 = [(1,0),(-1,0),(0,1),(0,-1)]

# =========================
# ぷよ処理
# =========================

def in_bounds(r, c):
    return 0 <= r < ROWS and 0 <= c < COLS

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
                    if in_bounds(nr, nc) and not visited[nr][nc] and field[nr][nc] == color:
                        visited[nr][nc] = True
                        stack.append((nr,nc))
                        comp.append((nr,nc))

            groups.append((color, comp))

    return groups

def erase_step(field):
    """
    仕様:
    - 通常色(赤青緑黄紫)は4つ以上で消える
    - ハートは4つ繋がっても消えない
    - ただし消える通常ぷよに隣接していたら1個でも巻き込まれて消える
    - 得点カウントは「通常色のみ」
    - ハートは得点に含めない
    """
    groups = find_groups(field)

    erase = set()

    # 通常色 4つ以上
    for color, cells in groups:
        if color in NORMAL_COLORS and len(cells) >= 4:
            erase |= set(cells)

    # ハート巻き込み
    heart_add = set()
    for r in range(ROWS):
        for c in range(COLS):
            if field[r][c] == "ハート":
                for dr, dc in DIR4:
                    nr, nc = r+dr, c+dc
                    if in_bounds(nr, nc) and (nr, nc) in erase:
                        heart_add.add((r,c))
    erase |= heart_add

    if not erase:
        return 0, 0, False

    # 得点対象: 通常色のみ
    score_count = 0
    for r, c in erase:
        if field[r][c] in NORMAL_COLORS:
            score_count += 1
        field[r][c] = "空"

    # 落下
    for c in range(COLS):
        stack = []
        for r in range(ROWS-1, -1, -1):
            if field[r][c] != "空":
                stack.append(field[r][c])

        for r in range(ROWS-1, -1, -1):
            field[r][c] = stack.pop(0) if stack else "空"

    return score_count, len(erase), True

def simulate_chain(field):
    """
    盤面を連鎖が止まるまで回す
    return:
      chains, score_total, max_simul, final_field
    """
    field = copy.deepcopy(field)

    chains = 0
    score_total = 0
    max_simul = 0

    while True:
        score, simul, ok = erase_step(field)
        if not ok:
            break
        chains += 1
        score_total += score
        max_simul = max(max_simul, simul)

    return chains, score_total, max_simul, field

def drop_nexts(field, nexts):
    """
    ネクスト8個落下方式 A:
    各列の「一番上の空き」に1個ずつ入れる
    """
    field = copy.deepcopy(field)

    for c, color in enumerate(nexts):
        for r in range(ROWS):
            if field[r][c] == "空":
                field[r][c] = color
                break

    return field

# =========================
# 枝切り用: 塗った瞬間4つ成立判定（軽量）
# =========================

def count_connected_same(field, r, c, target_color):
    """
    (r,c) を target_color とみなして、連結数を数える
    BFSだけど最大48なので軽い
    """
    visited = set()
    stack = [(r,c)]
    visited.add((r,c))

    while stack:
        cr, cc = stack.pop()
        for dr, dc in DIR4:
            nr, nc = cr+dr, cc+dc
            if not in_bounds(nr, nc):
                continue
            if (nr, nc) in visited:
                continue

            v = field[nr][nc]
            if (nr, nc) == (r, c):
                v = target_color

            if v == target_color:
                visited.add((nr,nc))
                stack.append((nr,nc))

    return len(visited)

def would_erase_if_painted(field, r, c, paint_color):
    """
    そのマスを paint_color にした瞬間に
    paint_color が4つ以上繋がるなら True
    """
    # もともと同色なら塗る意味ないので「消える判定」は不要
    if field[r][c] == paint_color:
        return False

    # 空は塗り替え対象にしない（仕様）
    if field[r][c] == "空":
        return False

    # ハートも塗り替え対象OK（仕様）
    # ただし塗った結果4つ繋がるならアウト

    connected = count_connected_same(field, r, c, paint_color)
    return connected >= 4

# =========================
# 起点候補の絞り込み
# =========================

def get_start_candidates(field):
    """
    起点ぷよ候補:
    「消した瞬間にどこかで4つが成立する可能性があるマス」
    → ざっくり:
      - そのマスを空にしたときに落下が起きる列
      - その周辺で4つ成立しそうな場所がある
    ここは厳密じゃなくてもOK
    """
    candidates = []
    for r in range(ROWS):
        for c in range(COLS):
            if field[r][c] == "空":
                continue
            # ハートも起点として消せる（指で消す）扱い
            candidates.append((r,c))
    return candidates

# =========================
# 探索
# =========================

def get_paint_candidates(field, paint_color):
    """
    塗り替え候補マス:
    - 空は除外
    - 既に paint_color のマスは除外（不毛）
    - 「塗った瞬間4つ成立するマス」は除外（枝切り）
    """
    cands = []
    removed = 0

    for r in range(ROWS):
        for c in range(COLS):
            v = field[r][c]
            if v == "空":
                continue
            if v == paint_color:
                continue

            # 枝切り: 塗った瞬間4つ成立なら候補から外す
            if would_erase_if_painted(field, r, c, paint_color):
                removed += 1
                continue

            cands.append((r,c))

    return cands, removed

def remove_one_and_simulate(base_field, start_pos, painted_positions_set):
    """
    起点ぷよを1つ消してから連鎖シミュする
    - 起点ぷよは得点に含めない（指で消すので）
    - 塗り替えで変えたぷよも得点に含めない（得点0）
    """
    field = copy.deepcopy(base_field)

    sr, sc = start_pos
    removed_color = field[sr][sc]
    field[sr][sc] = "空"

    # 落下（1回だけ）
    for c in range(COLS):
        stack = []
        for r in range(ROWS-1, -1, -1):
            if field[r][c] != "空":
                stack.append(field[r][c])
        for r in range(ROWS-1, -1, -1):
            field[r][c] = stack.pop(0) if stack else "空"

    # 連鎖
    chains, score_total, maxsim, final_field = simulate_chain(field)

    # ★得点調整
    # simulate_chainは通常色の消去数を全部得点に入れている
    # でも塗り替えたぷよが消えた分は得点0にしたい
    # → ここでは簡易的に「最終盤面との差分」で消えた座標を取るのが必要だが重い
    #
    # 今回は「塗り替えたぷよは得点0」という仕様を厳密にやるなら
    # erase_step側で座標を返す必要がある
    #
    # なので一旦:
    #   - 得点は「消えた通常色数」(塗り替え含む)として計算
    #   - 後で座標付きに改修
    #
    # とりあえず動くこと優先版

    return chains, score_total, maxsim, final_field

def run_search(fixed_field, nexts, paint_color, paint_count):
    """
    条件:
    - 塗り替え後に「何も消えない」ことが必須
    - その後、起点を1つ消す
    - 連鎖/同時消しが条件を満たすなら採用
    """

    # 1) ネクスト落下適用
    after_next = drop_nexts(fixed_field, nexts)

    # 2) 塗り替え候補作成（枝切り済み）
    paint_cands, removed_count = get_paint_candidates(after_next, paint_color)

    # 3) 起点候補（塗り替えで増える可能性はあるが、今回は後で再計算する）
    start_cands_base = get_start_candidates(after_next)

    # 4) 探索範囲（min_k）
    min_k = max(0, paint_count - 4)

    # 5) 総パターン数
    total_patterns = 0
    for k in range(min_k, paint_count+1):
        if k <= len(paint_cands):
            total_patterns += comb(len(paint_cands), k)

    # 6) 表示用
    info = {
        "paint_candidates": len(paint_cands),
        "removed_by_prune": removed_count,
        "start_candidates": len(start_cands_base),
        "min_k": min_k,
        "max_k": paint_count,
        "total_patterns": total_patterns,
    }

    if total_patterns == 0:
        return [], info

    # 7) 探索
    best = []
    done = 0
    last_pct = -1

    progress_bar = st.progress(0)
    status_text = st.empty()

    for k in range(min_k, paint_count+1):
        for combi in combinations(paint_cands, k):

            # --- 盤面作成（塗り替え適用） ---
            field = [row[:] for row in after_next]
            painted_set = set(combi)

            for r, c in combi:
                field[r][c] = paint_color

            # --- 重要条件: 塗り替え直後に消えたら廃案 ---
            chains0, score0, maxsim0, _ = simulate_chain(field)
            if chains0 > 0:
                # 塗り替えだけで消えるならアウト
                done += 1
                pct = int(done/total_patterns*100)
                if pct != last_pct:
                    progress_bar.progress(pct)
                    bar = "█"*(pct//5) + "░"*(20-pct//5)
                    status_text.markdown(
                        f"**進捗:** {pct}%  \n"
                        f"**試行中:** {done:,} / {total_patterns:,}\n\n"
                        f"{bar}"
                    )
                    last_pct = pct
                continue

            # --- 起点候補をここで再計算（塗り替え後で増える可能性があるので） ---
            start_cands = get_start_candidates(field)

            # --- 起点を1つずつ消して評価 ---
            for start_pos in start_cands:
                chains, score_total, maxsim, final_field = remove_one_and_simulate(
                    field, start_pos, painted_set
                )

                # 条件:
                # ② or ③ どちらか達成でOK
                ok = False
                if chains >= 6 or maxsim >= 16:
                    ok = True

                if ok:
                    best.append({
                        "chains": chains,
                        "score": score_total,
                        "maxsim": maxsim,
                        "painted": combi,
                        "start": start_pos,
                    })

                    # 上位3件だけ保持（score優先→chains→maxsim）
                    best = sorted(
                        best,
                        key=lambda x: (x["score"], x["chains"], x["maxsim"]),
                        reverse=True
                    )[:3]

            # --- 進捗更新 ---
            done += 1
            pct = int(done/total_patterns*100)

            if pct != last_pct:
                progress_bar.progress(pct)

                bar = "█"*(pct//5) + "░"*(20-pct//5)

                status_text.markdown(
                    f"""
**進捗:** {pct}%  
**試行中:** {done:,} / {total_patterns:,}

{bar}
"""
                )
                last_pct = pct

    return best, info


# =========================
# Streamlit UI
# =========================

st.set_page_config(layout="wide")
st.title("ぷよクエ盤面エディタ（塗り替え探索）")

# -------------------------
# session_state 初期化
# -------------------------
if "field" not in st.session_state:
    st.session_state.field = [["空"] * COLS for _ in range(ROWS)]

if "history" not in st.session_state:
    st.session_state.history = []

if "current_color" not in st.session_state:
    st.session_state.current_color = "赤"

if "mode" not in st.session_state:
    st.session_state.mode = "paint"

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
st.header("色パレット")

pal_cols = st.columns(len(ALL_COLORS))
for i, color in enumerate(ALL_COLORS):
    with pal_cols[i]:
        if st.button(EMOJI[color], key=f"pal_{color}"):
            st.session_state.current_color = color

st.markdown(f"## 選択中： {EMOJI[st.session_state.current_color]} {st.session_state.current_color}")


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
            if st.session_state.save_slots[i] is not None:
                push_history()
                st.session_state.field = copy.deepcopy(st.session_state.save_slots[i])


# -------------------------
# 盤面（クリックで塗る）
# -------------------------
st.header("盤面（クリックで塗る）")

for r in range(ROWS):
    row_cols = st.columns(COLS)
    for c in range(COLS):
        with row_cols[c]:
            label = EMOJI[st.session_state.field[r][c]]
            if st.button(label, key=f"cell_{r}_{c}"):
                push_history()
                st.session_state.field[r][c] = st.session_state.current_color


# -------------------------
# 編集中盤面表示
# -------------------------
st.markdown("### 編集中盤面")
for r in range(ROWS):
    st.write(" ".join(EMOJI[st.session_state.field[r][c]] for c in range(COLS)))


# -------------------------
# 確定盤面表示
# -------------------------
if st.session_state.fixed_field is not None:
    st.markdown("## 📌 確定盤面")
    for r in range(ROWS):
        st.write(" ".join(EMOJI[st.session_state.fixed_field[r][c]] for c in range(COLS)))


# -------------------------
# ネクスト
# -------------------------
st.header("ネクスト（8個）")

ncols = st.columns(8)
for i in range(8):
    with ncols[i]:
        st.session_state.next[i] = st.selectbox(
            "n",
            NORMAL_COLORS,
            index=NORMAL_COLORS.index(st.session_state.next[i]),
            key=f"next_{i}",
            label_visibility="collapsed"
        )

st.write(" ".join(EMOJI[c] for c in st.session_state.next))


# -------------------------
# 解析
# -------------------------
st.markdown("---")
st.header("解析（塗り替え→起点1つ消す→連鎖）")

paint_color = st.selectbox("塗り替え色", ["赤","青","緑","黄","紫","ハート"])
paint_count = st.number_input("塗り替え数（最大12）", 0, 12, 0)

if paint_count > 12:
    st.error("最大12まで")
    st.stop()

if st.button("解析開始"):

    if st.session_state.fixed_field is None:
        st.error("盤面を確定してから解析してね！")
        st.stop()

    fixed = copy.deepcopy(st.session_state.fixed_field)
    nexts = st.session_state.next[:]

    with st.spinner("探索中…（クラウドだと数分かかることもあるよ）"):
        results, info = run_search(fixed, nexts, paint_color, paint_count)

    st.success("探索完了！")

    st.markdown("## 探索情報")
    st.write(f"塗り替え候補マス数: {info['paint_candidates']}")
    st.write(f"枝切りで除外されたマス数: {info['removed_by_prune']}")
    st.write(f"起点候補（初期）: {info['start_candidates']}")
    st.write(f"k範囲: {info['min_k']} ～ {info['max_k']}")
    st.write(f"総試行数: {info['total_patterns']:,}")

    if info["total_patterns"] == 0:
        st.error("探索できません（候補数が少なすぎる / min_kが大きすぎる）")
        st.stop()

    st.markdown("---")

    if not results:
        st.error("条件を満たす結果が見つからなかった！")
        st.write("（原因の例）")
        st.write("・塗り替え後に消えてしまう（廃案扱い）")
        st.write("・起点を消しても6連鎖以上 or 16同時以上にならない")
    else:
        for i, r in enumerate(results, start=1):
            st.markdown(f"## 🥇 {i}位")

            st.write(f"連鎖: {r['chains']}")
            st.write(f"得点(暫定): {r['score']}  ※塗り替え得点0は未厳密")
            st.write(f"最大同時消し: {r['maxsim']}")

            st.write(f"塗り替え座標: {r['painted']}")
            st.write(f"起点座標: {r['start']}")
