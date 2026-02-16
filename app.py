from itertools import combinations
import copy

# =========================
# ぷよシミュ
# =========================

DIR4 = [(1,0),(-1,0),(0,1),(0,-1)]

def find_groups(field):
    ROWS=6
    COLS=8
    visited=[[False]*COLS for _ in range(ROWS)]
    groups=[]
    
    for r in range(ROWS):
        for c in range(COLS):
            if visited[r][c]: continue
            color=field[r][c]
            if color=="空": continue
            
            stack=[(r,c)]
            visited[r][c]=True
            comp=[(r,c)]
            
            while stack:
                cr,cc=stack.pop()
                for dr,dc in DIR4:
                    nr,nc=cr+dr,cc+dc
                    if 0<=nr<ROWS and 0<=nc<COLS:
                        if not visited[nr][nc] and field[nr][nc]==color:
                            visited[nr][nc]=True
                            stack.append((nr,nc))
                            comp.append((nr,nc))
            
            groups.append((color,comp))
    return groups

def erase_step(field):
    ROWS=6
    COLS=8
    
    groups=find_groups(field)
    
    erase=set()
    
    # 通常色
    for color,cells in groups:
        if color=="ハート": continue
        if len(cells)>=4:
            erase|=set(cells)
    
    # ハート巻き込み
    heart=set()
    for r in range(ROWS):
        for c in range(COLS):
            if field[r][c]=="ハート":
                for dr,dc in DIR4:
                    nr,nc=r+dr,c+dc
                    if 0<=nr<ROWS and 0<=nc<COLS:
                        if (nr,nc) in erase:
                            heart.add((r,c))
    erase|=heart
    
    if not erase:
        return 0,0,False
    
    count=0
    for r,c in erase:
        if field[r][c]!="ハート":
            count+=1
        field[r][c]="空"
    
    # 落下
    for c in range(COLS):
        stack=[]
        for r in range(ROWS-1,-1,-1):
            if field[r][c]!="空":
                stack.append(field[r][c])
        for r in range(ROWS-1,-1,-1):
            field[r][c]=stack.pop(0) if stack else "空"
    
    return count,len(erase),True

def simulate(field,key_pos,nexts):
    field=copy.deepcopy(field)
    
    # ネクスト落下
    for c,color in enumerate(nexts):
        for r in range(6):
            if field[r][c]=="空":
                field[r][c]=color
                break
    
    chains=0
    total=0
    maxsim=0
    
    key_alive=True
    
    while True:
        erased,sim,ok=erase_step(field)
        if not ok:
            break
        
        chains+=1
        total+=erased
        maxsim=max(maxsim,sim)
        
        if key_pos:
            kr,kc=key_pos
            found=False
            for r in range(6):
                for c in range(8):
                    if field[r][c]=="KEY":
                        kr,kc=r,c
                        found=True
            if not found:
                key_alive=False
    
    return chains,total,maxsim,key_alive,field

import streamlit as st
import copy

st.set_page_config(layout="wide")
st.title("ぷよクエ盤面エディタ")

ROWS = 6
COLS = 8

COLORS = ["赤","青","緑","黄","紫","ハート","空"]
EMOJI = {
    "赤":"🟥","青":"🟦","緑":"🟩",
    "黄":"🟨","紫":"🟪","ハート":"💖","空":"⬛"
}

# =====================
# 状態
# =====================
if "field" not in st.session_state:
    st.session_state.field = [["空"] * COLS for _ in range(ROWS)]

if "history" not in st.session_state:
    st.session_state.history = []

if "current_color" not in st.session_state:
    st.session_state.current_color = "赤"

if "mode" not in st.session_state:
    st.session_state.mode = "paint"

if "key" not in st.session_state:
    st.session_state.key = None

if "save_slots" not in st.session_state:
    st.session_state.save_slots = [None,None,None]

if "fixed_field" not in st.session_state:
    st.session_state.fixed_field = None

# =====================
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

cols = st.columns(len(COLORS))
for i,color in enumerate(COLORS):
    with cols[i]:
        if st.button(EMOJI[color], key=f"pal_{color}"):
            st.session_state.current_color = color
            st.session_state.mode = "paint"

st.markdown(f"## 選択中： {EMOJI[st.session_state.current_color]} {st.session_state.current_color}")

if st.button("キーぷよ指定モード"):
    st.session_state.mode = "key"

st.write("モード:", "配置" if st.session_state.mode=="paint" else "キー指定")

# =====================
# 操作
# =====================
st.header("操作")

b1,b2,b3,b4,b5 = st.columns(5)

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
    if st.button("キー解除"):
        st.session_state.key = None

with b5:
    if st.button("📌 盤面確定"):
        st.session_state.fixed_field = copy.deepcopy(st.session_state.field)

# =====================
# 保存
# =====================
st.header("保存")

for i in range(3):
    c1,c2 = st.columns(2)
    with c1:
        if st.button(f"保存{i+1}", key=f"save{i}"):
            st.session_state.save_slots[i] = copy.deepcopy(st.session_state.field)
    with c2:
        if st.button(f"読込{i+1}", key=f"load{i}"):
            if st.session_state.save_slots[i]:
                push_history()
                st.session_state.field = copy.deepcopy(st.session_state.save_slots[i])

# =====================
# 盤面
# =====================
st.header("盤面")

for r in range(ROWS):
    cols = st.columns(COLS)
    for c in range(COLS):
        with cols[c]:
            label = EMOJI[st.session_state.field[r][c]]
            if st.session_state.key == (r,c):
                label = "⭐"

            if st.button(label, key=f"cell_{r}_{c}"):

                push_history()

                if st.session_state.mode == "paint":
                    st.session_state.field[r][c] = st.session_state.current_color

                elif st.session_state.mode == "key":
                    st.session_state.key = (r,c)
                    st.session_state.mode = "paint"

# =====================
# 表示
# =====================
st.markdown("### 編集中盤面")

for r in range(ROWS):
    row=[]
    for c in range(COLS):
        if st.session_state.key == (r,c):
            row.append("⭐")
        else:
            row.append(EMOJI[st.session_state.field[r][c]])
    st.write(" ".join(row))

# =====================
# 確定盤面表示
# =====================
if st.session_state.fixed_field:
    st.markdown("## 📌 確定盤面")
    for row in st.session_state.fixed_field:
        st.write(" ".join(EMOJI[c] for c in row))

# =====================
# ネクスト
# =====================
st.header("ネクスト")

if "next" not in st.session_state:
    st.session_state.next = ["赤"] * 8

cols = st.columns(8)
for i in range(8):
    with cols[i]:
        st.session_state.next[i] = st.selectbox(
            "",
            ["赤","青","緑","黄","紫"],
            index=["赤","青","緑","黄","紫"].index(st.session_state.next[i]),
            key=f"next_{i}",
            label_visibility="collapsed"
        )

st.write(" ".join(EMOJI[c] for c in st.session_state.next))

# =========================
# 解析UI
# =========================

st.markdown("---")
st.header("解析")

COLORS_ALL = ["赤","青","緑","黄","紫","ハート"]

paint_color = st.selectbox("塗り替え色", COLORS_ALL)
paint_count = st.number_input("塗り替え数（最大12）",0,12,0)

if paint_count>12:
    st.error("最大12まで")
    st.stop()

progress_bar = st.progress(0)
status_text = st.empty()

def get_candidates(field,paint_color):
    cands=[]
    for r in range(6):
        for c in range(8):
            v=field[r][c]
            if v=="空": continue
            if v==paint_color: continue
            cands.append((r,c))
    return cands

def run_search(base_field,key_pos,nexts,paint_color,paint_count):

    cands=get_candidates(base_field,paint_color)

    best=[]

    total_patterns=0
    for k in range(paint_count+1):
        from math import comb
        if k<=len(cands):
            total_patterns+=comb(len(cands),k)

    done=0
    last_pct=0

    for k in range(paint_count+1):
        for combi in combinations(cands,k):

            field=[row[:] for row in base_field]

            for r,c in combi:
                field[r][c]=paint_color

            chains,total,maxsim,key_alive,final=simulate(field,key_pos,nexts)

            if key_pos and key_alive:
                pass
            elif key_pos and not key_alive:
                pass
            else:
                pass

            ok=False
            if not key_alive:
                if chains>=6 or maxsim>=16:
                    ok=True

            if ok:
                best.append({
                    "chains":chains,
                    "total":total,
                    "maxsim":maxsim,
                    "pattern":combi
                })

                best=sorted(best,key=lambda x:(x["total"],x["chains"],x["maxsim"]),reverse=True)[:3]

            done+=1
            pct=int(done/total_patterns*100)

            if pct//10>last_pct//10:
                progress_bar.progress(pct)
                status_text.write(f"{pct}%")
                last_pct=pct

    return best

if st.button("解析開始"):

    if "fixed_field" not in st.session_state:
        st.error("盤面確定して")
        st.stop()

    base_field=[row[:] for row in st.session_state.fixed_field]

    key_pos=st.session_state.get("key_pos",None)
    nexts=st.session_state.get("nexts",["空"]*8)

    with st.spinner("探索中…"):

        results=run_search(base_field,key_pos,nexts,paint_color,paint_count)

    st.success("完了")

    if not results:
        st.write("見つからず")
    else:
        for i,r in enumerate(results):
            st.write(f"## {i+1}位")
            st.write(f"連鎖:{r['chains']}")
            st.write(f"総消去:{r['total']}")
            st.write(f"同時:{r['maxsim']}")
            st.write(r["pattern"])
