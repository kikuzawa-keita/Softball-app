import streamlit as st
import database as db
import pandas as pd

def get_plan_comparison_df():

    plan_data = {
        "カテゴリ": ["基本", "基本", "基本", "運営", "運営", "運営", "運営", "記録", "記録", "分析", "補助", "価格"],
        "機能内容": ["選手登録", "試合記録", "チーム増設", "スケジュール登録", "出欠登録", "SNS連携", "メッセージ表示", "成績一覧", "スコア入力方法", "個人成績分析", "モバイルスコアブック", "価格"],
        "機能説明": ["画像付き選手名鑑を作成できます。", "スコアボードや打席結果・投球結果を記録できます。", "倶楽部内でガチチームとお楽しみチームなどのチーム分けができます。", "日付・内容・時間・場所などの情報を持ったスケジュールを登録できます。", "出席・欠席の集計、個人を確認できます。", "Instagramなどのリンクをトップページに表示できます", "外部の閲覧者向けと倶楽部メンバー向けのメッセージをトップページに表示できます。", "年度別・生涯成績を一覧で確認できます。", "安打・凡打等のみの簡易入力、打球方向などを含めた詳細入力に対応しています。", "セイバーメトリクスを用いた個人成績分析を表示します。", "試合中にスマホで記録したスコアをワンタッチでCore.cctに登録できます。", "RMB(中国元）"],
        "Free": ["30名まで", "30試合/年", "無制限", "〇", "〇", "〇", "〇", "〇", "簡易版・詳細版対応", "×", "×", "無料"],
        "Standard": ["100名まで", "100試合/年", "無制限", "〇", "〇", "〇", "〇", "〇", "簡易版・詳細版対応", "一部非対応", "×", "80RMB/月（βtest開放中）"],
        "Premium": ["無制限", "無制限", "無制限", "〇", "〇", "〇", "〇", "〇", "簡易版・詳細版・超詳細版対応", "全項目", "〇", "150RMB/月（βtest開放中）"]
    }
    return pd.DataFrame(plan_data)


def viewer_mode_ui(key_prefix):

    st.divider()
    st.subheader("🔍 Core.cctを利用中の倶楽部を閲覧する")
    st.caption("ホームページ・選手名鑑・試合結果を閲覧できます。")
    
    club_list = db.get_club_list_for_view()
    if club_list:
        cols = st.columns(4)
        for i, (c_id, c_name) in enumerate(club_list):
            with cols[i % 4]:
                if st.button(f"📖 {c_name}", key=f"{key_prefix}_view_btn_{c_id}", use_container_width=True):
                    st.session_state.club_id = c_id
                    st.session_state.club_name = c_name
                    st.session_state.is_viewer_mode = True
                    st.session_state.user_role = "guest"
                    st.session_state.username = "Guest(閲覧者)"
                    st.rerun()
    else:
        st.info("登録されている倶楽部はありません。")


def login_club_ui():

    st.warning("Core.cctは、現在βtest実施中です。全機能が無料でお使いいただけます。新規倶楽部登録後、開発者にご一報ください。")
    st.warning("個人成績分析、成績一覧、スコア簡易入力は、現在調整中です。")
    st.success("不具合を発見したら、開発者にご一報お願い致します。✉asahina0325@yahoo.co.jp")
    
    try:
        st.image("Core.cctLOGO.bmp", use_container_width=True)
    except:
        st.markdown("### ⚾ Core.cct SoftballClub Management System")

    st.markdown("### 🔑 倶楽部へ入室する")
    with st.form("club_login_form"):
        club_name = st.text_input("倶楽部名 (ID)")
        password = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button("ログイン")
        
        if submitted:
            club = db.verify_club_login(club_name, password)
            if club:
                st.session_state.club_id = club[0]
                st.session_state.club_name = club[1]
                st.session_state.is_viewer_mode = False
                st.success(f"ようこそ、{club[1]} へ！")
                st.rerun()
            else:
                st.error("倶楽部名またはパスワードが違います")

    viewer_mode_ui(key_prefix="login_tab")

    st.divider()
    st.subheader("🚀 Core.cct プラン別機能一覧")
    st.table(get_plan_comparison_df())


def register_club_ui():

    st.warning("Core.cctは、現在βtest実施中です。全機能が無料でお使いいただけます。新規倶楽部登録後、開発者にご一報ください。")

    st.markdown("### 📝 新規倶楽部登録")
    st.info("登録試合数30/年、登録選手30名までは無料で利用できます")
    with st.form("create_club_form"):
        st.caption("新しいチーム専用の環境を作成します")
        new_name = st.text_input("倶楽部名")
        new_pass = st.text_input("ログインパスワード", type="password")
        created = st.form_submit_button("登録して開始")
        
        if created:
            if not new_name or not new_pass:
                st.error("全ての項目を入力してください")
            else:
                cid = db.create_club(new_name, new_pass)
                if cid:
                    st.session_state.club_id = cid
                    st.session_state.club_name = new_name
                    st.session_state.is_viewer_mode = False
                    st.success(f"倶楽部「{new_name}」を作成しました！")
                    st.rerun()
                else:
                    st.error("その倶楽部名は既に使用されています")

    viewer_mode_ui(key_prefix="reg_tab")

    st.divider()
    st.subheader("🚀 Core.cct プラン別機能一覧")
    st.table(get_plan_comparison_df())


def login_sidebar():

    if "club_id" not in st.session_state or st.session_state.get("is_viewer_mode", False):
        return

    st.sidebar.divider()
    if "user_role" not in st.session_state:
        st.session_state.user_role = "guest"
        st.session_state.username = "Guest"

    club_id = st.session_state.club_id
    try:
        st.sidebar.image("Core.cctLOGO.bmp", use_container_width=True)
    except:
        st.image("Core.cct_LOGO.png", width=300)

    st.sidebar.subheader("👤 一般ログイン")
    all_teams = db.get_all_teams(club_id)
    selected_team = st.sidebar.selectbox("所属チーム", all_teams, key="active_team")
    team_players = ["(未選択)"] + [p[1] for p in db.get_players_by_team(selected_team, club_id)]
    st.sidebar.selectbox("選手氏名", team_players, key="active_player")

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
                    st.rerun()
                else:
                    st.sidebar.error("認証失敗")

    st.sidebar.divider()
    if st.sidebar.button("倶楽部からログアウト"):
        st.session_state.clear()
        st.rerun()