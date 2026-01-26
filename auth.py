import streamlit as st
import database as db

def login_club_ui():
    """倶楽部ログイン画面の入力フォームのみ"""
    st.markdown("### ⚾ 倶楽部へ入室")
    with st.form("club_login_form"):
        club_name = st.text_input("倶楽部名 (ID)")
        password = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button("ログイン")
        
        if submitted:
            club = db.verify_club_login(club_name, password)
            if club:
                st.session_state.club_id = club[0]
                st.session_state.club_name = club[1]
                st.success(f"ようこそ、{club[1]} へ！")
                st.rerun()
            else:
                st.error("倶楽部名またはパスワードが違います")

def register_club_ui():
    """新規倶楽部登録の入力フォームのみ"""
    st.markdown("### 📝 新規倶楽部登録")
    with st.form("create_club_form"):
        st.caption("新しいチーム専用の環境を作成します")
        new_name = st.text_input("希望する倶楽部名 (一意のID)")
        new_pass = st.text_input("管理用パスワード", type="password")
        created = st.form_submit_button("登録して開始")
        
        if created:
            if not new_name or not new_pass:
                st.error("全ての項目を入力してください")
            else:
                cid = db.create_club(new_name, new_pass)
                if cid:
                    st.session_state.club_id = cid
                    st.session_state.club_name = new_name
                    st.success(f"倶楽部「{new_name}」を作成しました！")
                    st.rerun()
                else:
                    st.error("その倶楽部名は既に使用されています")

def login_sidebar():
    """サイドバー：ユーザーログイン（倶楽部内での権限管理）"""
    if "club_id" not in st.session_state:
        return

    st.sidebar.divider()
    
    # セッション初期化
    if "user_role" not in st.session_state:
        st.session_state.user_role = "guest"
        st.session_state.username = "Guest"

    club_id = st.session_state.club_id
    
    # --- 2. 操作プレイヤー選択セクション (疑似ログイン) ---
    st.sidebar.subheader("👤 一般ログイン")
    all_teams = db.get_all_teams(club_id)
    
    # チーム選択
    selected_team = st.sidebar.selectbox(
        "所属チーム", 
        all_teams, 
        key="active_team"
    )
    
    # 選手選択
    team_players = ["(未選択)"] + [p[1] for p in db.get_players_by_team(selected_team, club_id)]
    
    st.sidebar.selectbox(
        "選手氏名", 
        team_players, 
        key="active_player"
    )

    # --- 1. スタッフログインセクション ---
    if st.session_state.user_role == "guest":
        st.sidebar.subheader("🔒 管理者ログイン")
        with st.sidebar.form("login_form"):
            user = st.text_input("ユーザー名")
            pw = st.text_input("パスワード", type="password")
            submit = st.form_submit_button("ログイン")
            
            if submit:
                role = db.verify_user(user, pw, club_id)
                if role:
                    st.session_state.user_role = role
                    st.session_state.username = user
                    db.add_activity_log(user, "LOGIN", "ログインしました", club_id)
                    st.sidebar.success(f"ログイン成功: {role}")
                    st.rerun()
                else:
                    st.sidebar.error("認証失敗")

    st.sidebar.divider()

    if st.session_state.active_player != "(未選択)":
        st.sidebar.caption(f"現在 **{st.session_state.active_player}** として操作中")
        
    if st.sidebar.button("倶楽部からログアウト"):
        st.session_state.clear()
        st.rerun()