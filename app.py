import streamlit as st
from ortools.sat.python import cp_model
import pandas as pd

# --- ページ設定 ---
st.set_page_config(page_title="余市JRシフト", page_icon="🚃", layout="wide")

# ==========================================
# 🎨 デザイン（CSS）設定エリア
# ==========================================
st.markdown("""
    <style>
    /* 全体の背景色を薄い緑に */
    .stApp {
        background-color: #F1F8E9;
    }
    /* タイトルの色を濃い緑に */
    h1 {
        color: #2E7D32;
        font-family: 'Helvetica', sans-serif;
    }
    /* サイドバーの背景 */
    [data-testid="stSidebar"] {
        background-color: #DCEDC8;
    }
    /* ボタンの色 */
    div.stButton > button {
        background-color: #2E7D32;
        color: white;
        border-radius: 10px;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# --- ✨ スプレッドシート風の見た目にする関数 ---
def make_grid(df):
    return df.style.set_properties(**{
        'border': '1px solid #c0c0c0',  # 枠線の色（グレー）
        'text-align': 'center'          # 文字を中央寄せ
    }).set_table_styles([
        {'selector': 'th', 'props': [('border', '1px solid #c0c0c0'), ('background-color', '#e8f5e9')]}
    ])

# タイトル表示
st.title("🚃 余市JR シフト作成システム")
st.markdown("**左のメニューで条件を設定し、「作成開始」を押してください**")

# --- 設定 ---
num_days = st.sidebar.number_input("📅 作成する日数", 28, 31, 31)

# メンバー定義
default_mem = [
    {'name':'嶋田', 'sk':5, 'ban':True, 'type':'normal', 'act':True},
    {'name':'渡辺', 'sk':5, 'ban':True, 'type':'normal', 'act':True},
    {'name':'坂東', 'sk':4, 'ban':False,'type':'normal', 'act':False},
    {'name':'村田', 'sk':4, 'ban':False,'type':'max7',   'act':True},
    {'name':'穂苅', 'sk':4, 'ban':False,'type':'normal', 'act':True},
    {'name':'伊藤', 'sk':4, 'ban':False,'type':'normal', 'act':True},
    {'name':'林',   'sk':4, 'ban':False,'type':'normal', 'act':True},
    {'name':'東',   'sk':4, 'ban':False,'type':'normal', 'act':True},
    {'name':'曽我部','sk':4,'ban':False,'type':'normal', 'act':True},
    {'name':'吉川', 'sk':3, 'ban':False,'type':'normal', 'act':True},
    {'name':'今野', 'sk':3, 'ban':False,'type':'normal', 'act':True},
    {'name':'嶋倉', 'sk':2, 'ban':False,'type':'normal', 'act':True},
    {'name':'橋本', 'sk':1, 'ban':False,'type':'hashi',  'act':True},
    {'name':'乙茂内','sk':1,'ban':True, 'type':'normal', 'act':True},
    {'name':'森',   'sk':1, 'ban':True, 'type':'normal', 'act':True},
]

df = pd.DataFrame(default_mem)
st.sidebar.markdown("### 1. 👥 メンバー設定")
edited = st.sidebar.data_editor(
    df, 
    column_config={"act":"参加","name":"名前","sk":"Lv","ban":"1番NG","type":"タイプ"},
    disabled=["name","sk","ban","type"],
    hide_index=True
)
active = edited[edited['act']==True].to_dict('records')

# --- 希望入力 ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 2. 🙋‍♂️ 希望入力")
reqs = {}
with st.sidebar.expander("🔽 ここをクリックして入力", expanded=True):
    kind = st.radio("種類", ["🛌絶対休","🍵明or休","☀️日勤","💪泊まり"], horizontal=True)
    code = 0
    if "絶対" in kind: code=10
    elif "日勤" in kind: code=5
    elif "泊まり" in kind: code=99
    
    for m in active:
        days = st.multiselect(f"{m['name']}", range(1,num_days+1), key=f"r_{m['name']}_{code}")
        if days:
            if m['name'] not in reqs: reqs[m['name']] = {}
            for d in days: reqs[m['name']][d] = code

# --- メイン処理 ---
if st.button("🚀 シフト作成開始"):
    with st.spinner("AIが最適なシフトを計算中..."):
        model = cp_model.CpModel()
        nm = len(active)
        S = [0,1,2,3,4,5] # 0:休, 1-4:泊, 5:日
        WS = [1,2,3,4]    # 泊まり
        
        x = {}
        is_s = {}
        for i in range(nm):
            for d in range(num_days):
                is_s[i,d] = model.NewBoolVar(f's_{i}_{d}')
                for s in S:
                    x[i,d,s] = model.NewBoolVar(f'x_{i}_{d}_{s}')
                model.Add(sum(x[i,d,s] for s in WS) == is_s[i,d])

        # 制約
        for d in range(num_days):
            for s in S:
                if s!=0: model.Add(sum(x[i,d,s] for i in range(nm)) == 1)
            for i in range(nm):
                model.Add(sum(x[i,d,s] for s in S) == 1)
            
            # 熟練度>=10
            model.Add(sum(x[i,d,s]*active[i]['sk'] for i in range(nm) for s in WS) >= 10)
            
            # 初心者<=2
            model.Add(sum(x[i,d,s] for i in range(nm) if active[i]['sk']==1 for s in WS) <= 2)

            # 橋本ルール
            h_idx = [i for i,m in enumerate(active) if m['type']=='hashi']
            if h_idx:
                hid = h_idx[0]
                others = [i for i,m in enumerate(active) if m['sk']==1 and m['type']!='hashi']
                o_sum = sum(x[o,d,s] for o in others for s in WS)
                model.Add(o_sum==0).OnlyEnforceIf(x[hid,d,1])

            # 希望反映
            for i in range(nm):
                name = active[i]['name']
                if name in reqs and (d+1) in reqs[name]:
                    c = reqs[name][d+1]
                    if c==10: 
                        model.Add(x[i,d,0]==1)
                        if d>0: model.Add(is_s[i,d-1]==0)
                    elif c==0: model.Add(x[i,d,0]==1)
                    elif c==5: model.Add(x[i,d,5]==1)
                    elif c==99: model.Add(is_s[i,d]==1)

        # 禁止メンバー
        for i in range(nm):
            if active[i]['ban']:
                for d in range(num_days): model.Add(x[i,d,1]==0)

        # 並び制約
        for i in range(nm):
            for d in range(num_days-1):
                model.Add(is_s[i,d] + is_s[i,d+1] <= 1)
                model.Add(is_s[i,d] + x[i,d+1,5] <= 1)
                model.Add(x[i,d+1,0]==1).OnlyEnforceIf(is_s[i,d])
        
        # 村田ルール
        for i in range(nm):
            if active[i]['type']=='max7':
                model.Add(sum(is_s[i,d] for d in range(num_days)) <= 7)

        # 目的関数
        objs = []
        for i in range(nm):
            for d in range(num_days-2):
                b1 = model.NewBoolVar(f'b1_{i}_{d}')
                model.AddBoolOr([is_s[i,d].Not(), is_s[i,d+2].Not(), b1])
                objs.append(b1*50)
                b2 = model.NewBoolVar(f'b2_{i}_{d}')
                model.AddBoolOr([is_s[i,d].Not(), x[i,d+2,5].Not(), b2])
                objs.append(b2*50)
            
            cn = model.NewIntVar(0, num_days, f'cn_{i}')
            model.Add(cn == sum(x[i,d,5] for d in range(num_days)))
            sn = model.NewIntVar(0, num_days**2, f'sn_{i}')
            model.AddMultiplicationEquality(sn, [cn,cn])
            objs.append(sn*500)

            if not active[i]['ban']:
                cr = model.NewIntVar(0, num_days, f'cr_{i}')
                model.Add(cr == sum(x[i,d,1] for d in range(num_days)))
                sr = model.NewIntVar(0, num_days**2, f'sr_{i}')
                model.AddMultiplicationEquality(sr, [cr,cr])
                objs.append(sr*100)
            
            cs = model.NewIntVar(0, num_days, f'cs_{i}')
            model.Add(cs == sum(is_s[i,d] for d in range(num_days)))
            ct = model.NewIntVar(0, num_days, f'ct_{i}')
            model.Add(ct == cs + cn)
            stt = model.NewIntVar(0, num_days**2, f'stt_{i}')
            model.AddMultiplicationEquality(stt, [ct,ct])
            objs.append(stt*200)

        model.Minimize(sum(objs))
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        status = solver.Solve(model)

        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            st.success("✅ シフト作成完了！")
            
            # --- 1. シフト表データ作成 ---
            matrix_data = []
            for i in range(nm):
                row_data = {}
                for d in range(num_days):
                    val = ""
                    if solver.Value(x[i,d,1]): val = "1"
                    elif solver.Value(x[i,d,2]): val = "2"
                    elif solver.Value(x[i,d,3]): val = "3"
                    elif solver.Value(x[i,d,4]): val = "4"
                    elif solver.Value(x[i,d,5]): val = "日"
                    elif solver.Value(x[i,d,0]):
                        if d > 0 and solver.Value(is_s[i,d-1]): val = "ー"
                        else: val = "" 
                    row_data[d+1] = val
                matrix_data.append(row_data)

            df_matrix = pd.DataFrame(matrix_data, index=[m['name'] for m in active])
            df_matrix.columns = [f"{c}日" for c in df_matrix.columns]

            st.markdown("### 📋 シフト表 (コピペ用)")
            st.info("右上のコピーボタンを押して、スプレッドシートに貼り付けてください")
            
            # コピペ用テキスト
            tsv = df_matrix.to_csv(sep='\t', header=True, index=True)
            st.code(tsv, language="text")
            
            # 画面表示用（枠線あり・中央揃え）
            st.dataframe(make_grid(df_matrix), use_container_width=True)

            # --- 2. 集計データ作成 ---
            st.markdown("---")
            st.markdown("### 📊 集計データ (コピペ用)")
            
            stats_data = []
            for i in range(nm):
                c_stay = sum(solver.Value(is_s[i,d]) for d in range(num_days))
                c_nikkin = sum(solver.Value(x[i,d,5]) for d in range(num_days))
                c_role1 = sum(solver.Value(x[i,d,1]) for d in range(num_days))
                c_total = c_stay + c_nikkin
                
                stats_data.append({
                    '出勤計': c_total,
                    '日勤': c_nikkin,
                    '①番': c_role1
                })
            
            df_stats = pd.DataFrame(stats_data, index=[m['name'] for m in active])
            
            col1, col2 = st.columns([2, 1])
            with col1:
                # 画面表示用（枠線あり・中央揃え）
                st.dataframe(make_grid(df_stats), use_container_width=True)
            with col2:
                # コピペ用テキスト
                tsv_stats = df_stats.to_csv(sep='\t', header=True, index=True)
                st.code(tsv_stats, language="text")

        else:
            st.error("❌ 条件が厳しすぎます。希望を少し減らしてみてください。")
