import streamlit as st
import database as db

def login_sidebar():
    """サイドバーにログインフォームと選手選択を表示"""
    st.sidebar.divider()
    
    # セッション初期化
    if "user_role" not in st.session_state:
        st.session_state.user_role = "guest"
        st.session_state.username = "Guest"

    # --- 1. スタッフログインセクション ---
    if st.session_state.user_role == "guest":
        st.sidebar.subheader("🔒 スタッフログイン")
        with st.sidebar.form("login_form"):
            user = st.text_input("ユーザー名")
            pw = st.text_input("パスワード", type="password")
            submit = st.form_submit_button("ログイン")
            
        if submit:
            role = db.verify_user(user, pw)
            if role:
                st.session_state.user_role = role
                st.session_state.username = user
                db.add_activity_log(user, "LOGIN", "ログインしました")
                st.sidebar.success(f"ログイン成功: {role}")
                st.rerun()
            else:
                st.sidebar.error("認証失敗")
    else:
        st.sidebar.markdown(f"👤 **{st.session_state.username}** ({st.session_state.user_role})")
        if st.sidebar.button("ログアウト"):
            db.add_activity_log(st.session_state.username, "LOGOUT", "ログアウトしました")
            # 選手選択もクリアする場合
            st.session_state.active_team = None
            st.session_state.active_player = "(未選択)"
            st.session_state.user_role = "guest"
            st.session_state.username = "Guest"
            st.rerun()

    st.sidebar.divider()

    # --- 2. 操作プレイヤー選択セクション (疑似ログイン) ---
    st.sidebar.subheader("👤 操作プレイヤー選択")
    all_teams = db.get_all_teams()
    
    # チーム選択
    selected_team = st.sidebar.selectbox(
        "所属チーム", 
        all_teams, 
        key="active_team"
    )
    
    # 選手選択
    team_players = ["(未選択)"] + [p[1] for p in db.get_players_by_team(selected_team)]
    
    st.sidebar.selectbox(
        "表示・回答する選手", 
        team_players, 
        key="active_player"
    )

    if st.session_state.active_player != "(未選択)":
        st.sidebar.caption(f"現在 **{st.session_state.active_player}** として操作中")