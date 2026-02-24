import streamlit as st
import database as db
import pandas as pd

def show():
    # --- 0. ログインチェックと club_id 取得 ---
    club_id = st.session_state.get("club_id")
    if not club_id:
        st.error("倶楽部セッションが見つかりません。ログインし直してください。")
        return

    st.title("⚙️ 管理設定パネル")
    
    # 権限チェック
    if st.session_state.get("user_role") != "admin":
        st.error("このページを表示する権限がありません。")
        return

    # タブを5つに増やして「SNS・メッセージ」を統合
    tab0, tab1, tab2, tab3, tab4 = st.tabs(["🏠 倶楽部基本設定", "🌐 SNS・メッセージ", "🏃 チーム管理", "👥 ユーザー管理", "📜 操作ログ"])

    # --- TAB0: 基本設定 (正式名称・ログインID・パスワード) ---
    with tab0:
        st.subheader("🏢 倶楽部基本情報・認証設定")
        
        # 現在の設定値をDBから取得（最新の状態を反映させるため）
        with db.sqlite3.connect(db.DB_NAME) as conn:
            conn.row_factory = db.sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT display_name, login_id, raw_password FROM clubs WHERE id = ?", (club_id,))
            club_info = c.fetchone()
        
        if club_info:
            current_display_name = club_info['display_name']
            current_login_id = club_info['login_id']
            current_raw_password = club_info['raw_password']
        else:
            st.error("倶楽部情報の取得に失敗しました。")
            return

        with st.container(border=True):
            st.markdown("#### 📝 名称とIDの設定")
            
            new_display_name = st.text_input(
                "倶楽部 正式名称", 
                value=current_display_name, 
                help="ホーム画面や一覧に表示される名前です。"
            )
            
            new_login_id = st.text_input(
                "ログイン用ID (略称)", 
                value=current_login_id, 
                help="ログイン画面で入力する識別子です。他倶楽部と重複はできません。"
            )
            
            if new_login_id != current_login_id:
                st.warning("⚠️ ログインIDを変更すると、次回から新しいIDを入力する必要があります。")

            st.divider()
            st.markdown("#### 🔐 倶楽部ログインパスワード")
            new_password = st.text_input(
                "新しいパスワード (変更する場合のみ入力)", 
                value=current_raw_password,
                type="password",
                help="マスター（管理者）が忘却時に確認できるよう、平文でも保存されます。"
            )
            
            if st.button("設定を更新する", type="primary", use_container_width=True):
                if not new_display_name or not new_login_id or not new_password:
                    st.error("すべての項目を入力してください。")
                else:
                    success = db.update_club_settings(
                        club_id, 
                        new_display_name, 
                        new_login_id, 
                        password=new_password 
                    )
                    
                    if success:
                        st.session_state.club_name = new_display_name
                        db.add_activity_log(
                            st.session_state.username, 
                            "UPDATE_CLUB_SETTINGS", 
                            f"Name:{new_display_name}, ID:{new_login_id}", 
                            club_id=club_id
                        )
                        st.success("倶楽部設定を更新しました！")
                        st.rerun()
                    else:
                        st.error("更新に失敗しました。ログインIDが他の倶楽部と重複している可能性があります。")

    # --- TAB1: SNS・メッセージ設定 (統合・加筆) ---
    with tab1:
        st.subheader("🌐 ホームページ・SNS設定")
        current_data = db.get_club_customization(club_id)
        
        with st.form("custom_form"):
            msg = st.text_area("訪問者への挨拶", value=current_data['welcome_message'])
            ann = st.text_area("メンバーへのお知らせ", value=current_data['member_announcement'])
            insta = st.text_input("Instagram URL", value=current_data['instagram_url'])
            x_url = st.text_input("X (旧Twitter) URL", value=current_data.get('x_url', ""))
            yt_url = st.text_input("YouTube URL", value=current_data.get('youtube_url', ""))
            
            if st.form_submit_button("設定を更新"):
                db.update_club_customization(club_id, {
                    "welcome_message": msg,
                    "member_announcement": ann,
                    "instagram_url": insta,
                    "x_url": x_url,
                    "youtube_url": yt_url
                })
                st.success("設定を更新しました！")
                st.rerun()

    # --- TAB2: チーム管理 (旧TAB1) ---
    with tab2:
        st.subheader("チーム編成・カラー管理")
        with st.container(border=True):
            st.markdown("#### ➕ 新規チームの設立")
            col_name, col_color = st.columns([2, 1])
            with col_name:
                new_team = st.text_input("チーム名を入力", placeholder="例：シニアチーム", key="new_team_input")
            with col_color:
                new_color = st.color_picker("カラーを選択", "#3498db", key="new_team_color")
            
            if st.button("チームを新設する", type="primary", use_container_width=True):
                if new_team:
                    if db.add_team_master(new_team, new_color, club_id=club_id):
                        st.success(f"チーム「{new_team}」を新設しました！")
                        st.rerun()
                    else:
                        st.error("登録済みの名前か、無効な入力です。")

        st.markdown("---")
        st.markdown("#### 📋 登録済みチームの管理")
        teams_data = db.get_all_teams_with_colors(club_id=club_id)
        
        if not teams_data:
            st.info("登録されたチームはありません。")
        else:
            for team_info in teams_data:
                name, color = team_info[0], team_info[1]
                with st.container(border=True):
                    cp, ci, ce, ca = st.columns([0.4, 1.5, 1.2, 1.2])
                    with cp:
                        st.markdown(f'<div style="background-color:{color}; width:35px; height:35px; border-radius:5px; border:1px solid #ddd; margin-top:10px;"></div>', unsafe_allow_html=True)
                    with ci:
                        st.markdown(f"**{name}**")
                        st.caption(f"現在の色: {color}")
                    with ce:
                        changed_color = st.color_picker("色変更", color, key=f"cp_{name}", label_visibility="collapsed")
                    with ca:
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("更新", key=f"upd_{name}"):
                                db.update_team_color(name, changed_color, club_id=club_id)
                                st.toast(f"{name}の色を更新しました")
                                st.rerun()
                        with c2:
                            if st.button("削除", key=f"del_{name}"):
                                db.delete_team(name, club_id=club_id)
                                st.rerun()

    # --- TAB3: ユーザー管理 (旧TAB2) ---
    with tab3:
        st.subheader(f"👥 {st.session_state.get('club_name', '自倶楽部')} のユーザー一覧")
        users = db.get_all_users(club_id=club_id)
        if users:
            st.dataframe(pd.DataFrame(users), use_container_width=True, hide_index=True)
        else:
            st.info("ユーザーがいません。")

        st.divider()
        st.subheader("新規ユーザー作成")
        c1, c2, c3 = st.columns(3)
        new_u = c1.text_input("ユーザー名", key="admin_new_u")
        new_p = c2.text_input("パスワード", type="password", key="admin_new_p")
        new_r = c3.selectbox("権限", ["admin", "operator"], key="admin_new_r")
        
        if st.button("ユーザー追加", use_container_width=True):
            if new_u and new_p:
                if db.create_user(new_u, new_p, new_r, club_id=club_id):
                    st.success(f"ユーザー {new_u} を作成しました")
                    db.add_activity_log(st.session_state.username, "CREATE_USER", f"New: {new_u} ({new_r})", club_id=club_id)
                    st.rerun()
                else:
                    st.error("ユーザー名が重複しているか、作成に失敗しました")
            else:
                st.warning("全項目入力してください")
        
        st.divider()
        st.subheader("ユーザー削除")
        if users:
            target_list = [u['username'] for u in users]
            del_target = st.selectbox("削除するユーザーを選択", target_list)
            if st.button("削除実行", type="primary"):
                if del_target == st.session_state.username:
                    st.error("自分自身は削除できません")
                else:
                    if hasattr(db, 'delete_user'):
                        db.delete_user(del_target, club_id=club_id)
                        db.add_activity_log(st.session_state.username, "DELETE_USER", f"Deleted: {del_target}", club_id=club_id)
                        st.success(f"{del_target} を削除しました")
                        st.rerun()
                    else:
                        st.error("削除関数が定義されていません")
        else:
            st.info("削除できるユーザーがいません")

    # --- TAB4: 操作ログ (旧TAB3) ---
    with tab4:
        st.subheader("📜 システム操作ログ (最新50件)")
        if st.button("ログを最新に更新"):
            st.rerun()
        
        logs = db.get_activity_logs(club_id=club_id)
        if logs:
            st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True)
        else:
            st.info("操作ログはありません。")

