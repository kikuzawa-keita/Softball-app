import streamlit as st
import database as db
import os
import datetime
import sqlite3
from PIL import Image
from streamlit_cropper import st_cropper

# database.py などの読み込み関数にキャッシュをかける例
@st.cache_data
def get_all_players_cached():
    return db.get_all_players()

def show():
    # --- 現在の年度を取得 (メンテナンスフリー化) ---
    current_year = datetime.date.today().year

    # --- セッション状態の初期化 ---
    if "edit_player_id" not in st.session_state:
        st.session_state.edit_player_id = None
    
    role = st.session_state.get("user_role", "guest")
    username = st.session_state.get("username", "Guest")

    # --- 1. CSS設定 ---
    st.markdown(f"""
        <style>

        .retired-card {{ background-color: #f8f9fa; opacity: 0.8; border-style: dashed; }}
        
        div.stButton > button[kind="secondary"] {{
            border: none !important;
            background: transparent !important;
            padding: 0 !important;
            color: #007bff !important;
            text-align: left !important;
            font-size: 1.2rem !important;
            font-weight: bold !important;
        }}
        div.stButton > button[kind="secondary"]:hover {{ color: #ff4b4b !important; }}

        .status-badge {{
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.7rem;
            font-weight: bold;
            display: inline-block;
            margin-right: 5px;
            color: white;
        }}
        .active-badge {{ background-color: #28a745; }}
        .retired-label {{ background-color: #6c757d; }}
        .team-badge {{
            padding: 2px 10px;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: bold;
            display: inline-block;
            color: white;
        }}
        .stats-header {{
            font-size: 0.75rem;
            font-weight: bold;
            color: #555;
            margin-top: 10px;
            border-bottom: 1px solid #eee;
        }}
        .stats-label {{ font-size: 0.6rem; color: gray; }}
        .stats-value {{ font-size: 0.8rem; font-weight: bold; }}
        
        .stExpander {{ border: 1px solid #eee !important; border-radius: 5px; margin-top: -5px; margin-bottom: 10px; }}
        </style>
        """, unsafe_allow_html=True)

    st.title("📇 選手名鑑")

    # --- 2. 画像保存ヘルパー ---
    def save_cropped_image(img_obj, name):
        if not os.path.exists("images"):
            os.makedirs("images")
        img_obj = img_obj.convert("RGB")
        img_obj.thumbnail((400, 400))
        path = os.path.join("images", f"{name}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.jpg")
        img_obj.save(path, "JPEG", quality=85)
        return path

    # --- 3. 新規登録 (Admin/Operatorのみ) ---
    if role in ["admin", "operator"]:
        with st.expander("➕ 新しい選手を登録する"):
            new_name = st.text_input("選手名（必須）")
            all_teams = db.get_all_teams()
            new_team = st.selectbox("所属チーム", all_teams, key="reg_team_sel")
            
            c1, c2 = st.columns(2)
            new_birth = c1.text_input("生年月日", placeholder="1995/05/20")
            new_home = c2.text_input("出身地", placeholder="東京都")
            new_memo = st.text_area("備考・紹介文")
            
            uploaded_file = st.file_uploader("写真を選択", type=['jpg', 'png', 'jpeg'], key="new_upload")
            cropped_img_data = None
            if uploaded_file:
                img = Image.open(uploaded_file)
                cropped_img_data = st_cropper(img, realtime_update=True, box_color='#FF0000', aspect_ratio=(1, 1))
                st.image(cropped_img_data, width=150, caption="プレビュー")

            if st.button("選手を新規登録する", type="primary"):
                if new_name:
                    img_path = save_cropped_image(cropped_img_data, new_name) if cropped_img_data else ""
                    # database.pyの構成に合わせて背番号なしで登録
                    db.add_player(new_name, new_birth, new_home, new_memo, img_path, new_team)
                    db.add_activity_log(username, "ADD_PLAYER", f"登録: {new_name}")
                    st.success(f"{new_name} 選手を登録しました！")
                    st.rerun()
                else:
                    st.error("名前は必須です")

    st.divider()

    # --- 4. 一覧表示と検索 ---
    players_raw = db.get_all_players()
    ordered_teams = db.get_all_teams() 
    team_colors = {name: color for name, color in db.get_all_teams_with_colors()}
    
    f1, f2 = st.columns([2, 1])
    search_q = f1.text_input("🔍 選手名検索")
    selected_team = f2.selectbox("チーム絞込", ["すべて合算"] + ordered_teams)

    # 表示対象のフィルタリング
    players_filtered = [
        p for p in players_raw 
        if (search_q.lower() in p[1].lower()) and 
           (selected_team == "すべて合算" or (len(p) > 8 and p[8] == selected_team))
    ]

    # 自動並べ替え: 1. 引退選手を末尾, 2. チーム順, 3. 五十音順
    players_filtered.sort(key=lambda p: (
        -(p[7] if (len(p) > 7 and p[7] is not None) else 1), 
        ordered_teams.index(p[8]) if (len(p) > 8 and p[8] in ordered_teams) else 999,
        p[1]
    ))

    if not players_filtered:
        st.info("選手が見つかりません。")
        return

    # --- グリッド表示 ---
    cols = st.columns(3)
    for i, p in enumerate(players_filtered):
        p_id, p_name, p_birth, p_home, p_memo, p_img = p[0], p[1], p[2], p[3], p[4], p[5]
        # p[7]は現役フラグ(1:現役, 0:引退)
        is_active = p[7] if (len(p) > 7 and p[7] is not None) else 1
        p_team = p[8] if len(p) > 8 else "未所属"
        
        with cols[i % 3]:
            if st.session_state.edit_player_id == p_id:
                # 編集モード
                with st.container(border=True):
                    st.markdown("### 選手情報の編集")
                    e_name = st.text_input("名前", value=p_name, key=f"en_{p_id}")
                    e_team = st.selectbox("所属", ordered_teams, index=ordered_teams.index(p_team) if p_team in ordered_teams else 0, key=f"et_{p_id}")
                    e_status = st.radio("状態", ["現役", "引退"], index=0 if is_active == 1 else 1, horizontal=True, key=f"es_{p_id}")
                    
                    ec1, ec2 = st.columns(2)
                    e_birth = ec1.text_input("生年月日", value=p_birth, key=f"eb_{p_id}")
                    e_home = ec2.text_input("出身地", value=p_home, key=f"eh_{p_id}")
                    e_memo = st.text_area("備考", value=p_memo, key=f"em_{p_id}")
                    
                    st.write("📸 写真の変更")
                    e_uploaded = st.file_uploader("新しい写真を選択", type=['jpg', 'png', 'jpeg'], key=f"eup_{p_id}")
                    
                    # 修正：セッション状態で新しく確定された画像パスを保持する
                    temp_img_key = f"temp_img_path_{p_id}"
                    if temp_img_key not in st.session_state:
                        st.session_state[temp_img_key] = p_img
                    
                    if e_uploaded:
                        e_img_obj = Image.open(e_uploaded)
                        e_cropped = st_cropper(e_img_obj, realtime_update=True, box_color='#FF0000', aspect_ratio=(1, 1), key=f"ecrop_{p_id}")
                        if st.button("この写真で確定", key=f"conf_img_{p_id}"):
                            new_path = save_cropped_image(e_cropped, e_name)
                            st.session_state[temp_img_key] = new_path # 確定したパスをセッションに保存
                            st.success("写真を一時保存しました")

                    btn_c1, btn_c2 = st.columns(2)
                    if btn_c1.button("保存", key=f"sv_{p_id}", type="primary", use_container_width=True):
                        # セッションに保存された最新の画像パス（変更なければ元のパス）を使用
                        final_img_path = st.session_state.get(temp_img_key, p_img)
                        db.update_player_info(p_id, e_name, e_birth, e_home, e_memo, final_img_path, (1 if e_status=="現役" else 0), e_team)
                        db.add_activity_log(username, "EDIT_PLAYER", f"更新: {e_name}")
                        
                        # 後片付け
                        if temp_img_key in st.session_state:
                            del st.session_state[temp_img_key]
                        st.session_state.edit_player_id = None
                        st.rerun()
                        
                    if btn_c2.button("取消", key=f"cn_{p_id}", use_container_width=True):
                        if temp_img_key in st.session_state:
                            del st.session_state[temp_img_key]
                        st.session_state.edit_player_id = None
                        st.rerun()

                    # --- 管理者専用：削除機能の追加 ---
                    if role == "admin":
                        st.divider()
                        with st.expander("⚠️ 危険な操作"):
                            confirm_delete = st.checkbox("この選手を完全に削除することに同意します", key=f"conf_del_cb_{p_id}")
                            if st.button(f"🗑️ {p_name} 選手を削除", key=f"del_btn_{p_id}", type="primary", disabled=not confirm_delete):
                                db.delete_player(p_id)
                                db.add_activity_log(username, "DELETE_PLAYER", f"削除: {p_name}")
                                st.session_state.edit_player_id = None
                                st.success(f"{p_name} を削除しました。")
                                st.rerun()

            else:
                # 通常表示モード
                card_class = "retired-card" if is_active == 0 else ""
                st.markdown(f'<div class="player-card {card_class}">', unsafe_allow_html=True)
                
                c_img, c_txt = st.columns([1, 1.8])
                with c_img:
                    img_src = p_img if p_img and os.path.exists(p_img) else "https://via.placeholder.com/150"
                    st.image(img_src, use_container_width=True)
                
                with c_txt:
                    name_row, edit_row = st.columns([4, 1])
                    with name_row:
                        if st.button(p_name, key=f"btn_{p_id}", type="secondary"):
                            st.session_state.selected_player_id = p_id
                            st.session_state.current_page = "選手個人分析" # 画面遷移名を修正
                            st.rerun()
                    with edit_row:
                        if role == "admin" and st.button("📝", key=f"ed_{p_id}"):
                            st.session_state.edit_player_id = p_id
                            st.rerun()
                    
                    bg_color = team_colors.get(p_team, "#6c757d")
                    status_badge = '<span class="status-badge active-badge">現役</span>' if is_active == 1 else '<span class="status-badge retired-label">引退</span>'
                    st.markdown(f'<div>{status_badge}<span class="team-badge" style="background-color:{bg_color};">{p_team}</span></div>', unsafe_allow_html=True)
                    st.markdown(f'<div style="font-size:0.7rem; color:#666; line-height:1.2;">🎂 {p_birth}<br>🏠 {p_home}</div>', unsafe_allow_html=True)

                # 成績ヘッダーの出し分け
                header_label = f"{current_year}年度成績" if is_active == 1 else "生涯成績"
                st.markdown(f'<div class="stats-header">{header_label}</div>', unsafe_allow_html=True)
                
                try:
                    # 現役なら現在の年度、引退ならNone（生涯成績）を渡す
                    target_year = current_year if is_active == 1 else None
                    stats = db.get_player_season_stats(p_id, year=target_year)
                    
                    s1, s2, s3, s4 = st.columns(4)
                    s1.markdown(f"<div class='stats-label'>打率</div><div class='stats-value'>{stats.get('avg',0):.3f}</div>", unsafe_allow_html=True)
                    s2.markdown(f"<div class='stats-label'>本打</div><div class='stats-value'>{stats.get('hr',0)}</div>", unsafe_allow_html=True)
                    s3.markdown(f"<div class='stats-label'>盗塁</div><div class='stats-value'>{stats.get('sb',0)}</div>", unsafe_allow_html=True)
                    s4.markdown(f"<div class='stats-label'>防御</div><div class='stats-value'>{stats.get('era',0):.2f}</div>", unsafe_allow_html=True)
                except:
                    st.caption("データなし")
                
                st.markdown('</div>', unsafe_allow_html=True)
                
                with st.expander("📝 備考・紹介文"):
                    st.write(p_memo if p_memo else "記載なし")