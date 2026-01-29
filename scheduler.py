import streamlit as st
import database as db
import pandas as pd
from datetime import datetime, date, timedelta

def show():
    # ログイン中の club_id を取得
    club_id = st.session_state.get("club_id")
    if not club_id:
        st.error("倶楽部セッションが見つかりません。ログインし直してください。")
        return

    # db.init_scheduler_db()  # database.pyに存在しないため削除
    st.title("📅 チームスケジューラー")
    st.warning("１年を経過した履歴は自動で削除されます。")

    role = st.session_state.get("user_role", "guest")
    
    # --- デザイン設定 ---
    st.markdown("""
        <style>
        .team-tag {
            padding: 2px 8px; border-radius: 4px;
            font-size: 0.7rem; font-weight: bold;
            color: white; margin-right: 5px;
            display: inline-block;
            margin-bottom: 2px;
        }
        </style>
    """, unsafe_allow_html=True)

    # 共通データの取得 (club_id を追加)
    all_teams = db.get_all_teams(club_id)
    team_colors = {name: color for name, color in db.get_all_teams_with_colors(club_id)}
    events = db.get_all_events(club_id)
    players_raw = db.get_all_players(club_id)
    today = date.today()
    today_str = today.isoformat()

    # 1年以上前の予定を自動削除するロジック
    one_year_ago_str = (today - timedelta(days=365)).isoformat()
    old_events = [e for e in events if e[1] < one_year_ago_str]

    cat_icons = {
        "試合": "⚾試合", "練習": "👟練習", "送別会": "💐送別会", 
        "親睦会": "🍺親睦会", "会議": "📋会議", "その他": "✨その他"
    }

    tab_titles = ["🚀 今後の予定", "📁 過去の履歴"]
    if role in ["admin", "operator"]:
        tab_titles.append("➕ 予定登録")
    
    menu = st.tabs(tab_titles)

    # 1. 予定登録タブ
    if role in ["admin", "operator"]:
        with menu[2]:
            existing_locations = sorted(list(set([e[4] for e in events if e[4]])))

            with st.form("event_form", clear_on_submit=True):
                st.subheader("📝 新規予定入力")
                c1, c2 = st.columns(2)
                input_date = c1.date_input("日付", value=date.today())
                target_teams = c2.multiselect("対象チーム", options=all_teams if all_teams else ["デフォルト"])
                
                c3, c4 = st.columns(2)
                category = c3.selectbox("種別", list(cat_icons.keys()))
                title = c4.text_input("予定名")

                location_options = ["（以前使った住所から選択）"] + existing_locations
                selected_loc = st.selectbox("場所", location_options)
                
                if selected_loc == "（以前使った住所から選択）":
                    location = st.text_input("新しい場所を追加する場合は、こちらに入力してください")
                else:
                    location = selected_loc

                initial_memo = "時間：\n集合：\n持ち物：\n備考："
                memo = st.text_area("メモ詳細", value=initial_memo, height=150)
                
                if st.form_submit_button("予定を保存する", use_container_width=True):
                    if not title:
                        st.error("予定名を入力してください")
                    elif not target_teams:
                        st.error("対象チームを選択してください")
                    else:
                        team_str = ",".join(target_teams)
                        full_title = f"[{team_str}] {title}"
                        db.save_event(str(input_date), full_title, category, location, memo, club_id)
                        st.success("登録完了！")
                        st.rerun()

    if not events:
        st.info("予定はありません。")
        return

    def parse_event(ev):
        # ev は (event_id, date, title, category, location, memo) の形式
        raw_title = ev[2] if len(ev) > 2 else ""
        extracted_teams = []
        clean_title = raw_title
        if raw_title.startswith("["):
            parts = raw_title.split("] ", 1)
            if len(parts) > 1:
                extracted_teams = [t.strip() for t in parts[0][1:].split(",")]
                clean_title = parts[1]
        return list(ev) + [extracted_teams, clean_title]

    parsed_events = [parse_event(e) for e in events]
    upcoming_events = sorted([e for e in parsed_events if e[1] >= today_str], key=lambda x: x[1])

    # 2. メイン表示
    with menu[0]:
        if not upcoming_events:
            st.caption("今後の予定はありません。")
        else:
            h1, h2, h3, h4 = st.columns([1.2, 2, 1, 1.2])
            h1.caption("日付/チーム")
            h2.caption("予定名")
            h3.caption("場所")
            h4.caption("回答・詳細")
            st.divider()

            for ev in upcoming_events:
                ev_id, ev_date, _, ev_cat, ev_loc, ev_memo, ev_teams, ev_title = ev
                current_att = db.get_attendance_for_event(ev_id, club_id)
                
                # --- 欠席・保留も含めた集計 ---
                att_values = list(current_att.values())
                count_yes = att_values.count("出席")
                count_no = att_values.count("欠席")
                count_hold = att_values.count("保留")
                
                pop_label = f"✅{count_yes} ❌{count_no} △{count_hold}"
                
                dt = datetime.strptime(ev_date, '%Y-%m-%d')
                date_disp = dt.strftime('%m/%d') + f"({['月','火','水','木','金','土','日'][dt.weekday()]})"

                c1, c2, c3, c4 = st.columns([1.2, 2, 1, 1.2])
                with c1:
                    st.markdown(f"**{date_disp}**")
                    badge_html = "".join([f'<span class="team-tag" style="background-color:{team_colors.get(t, "#6c757d")}">{t}</span>' for t in ev_teams])
                    st.markdown(badge_html, unsafe_allow_html=True)
                
                c2.markdown(f"**{cat_icons.get(ev_cat, '✨')} {ev_title}**")
                c3.write(f"`{ev_loc[:6]}`" if ev_loc else "---")
                
                with c4.popover(pop_label, use_container_width=True):
                    edit_mode_key = f"edit_mode_{ev_id}"
                    if edit_mode_key not in st.session_state:
                        st.session_state[edit_mode_key] = False

                    if st.session_state[edit_mode_key]:
                        # --- 編集フォーム ---
                        st.markdown("### 🛠️ 予定の編集")
                        new_date = st.date_input("日付", value=datetime.strptime(ev_date, '%Y-%m-%d'), key=f"ed_date_{ev_id}")
                        new_teams = st.multiselect("対象チーム", options=all_teams, default=ev_teams, key=f"ed_team_{ev_id}")
                        new_cat = st.selectbox("種別", list(cat_icons.keys()), index=list(cat_icons.keys()).index(ev_cat) if ev_cat in cat_icons else 0, key=f"ed_cat_{ev_id}")
                        new_title = st.text_input("予定名", value=ev_title, key=f"ed_title_{ev_id}")
                        new_loc = st.text_input("場所", value=ev_loc if ev_loc else "", key=f"ed_loc_{ev_id}")
                        new_memo = st.text_area("メモ詳細", value=ev_memo if ev_memo else "", height=150, key=f"ed_memo_{ev_id}")
                        
                        ec1, ec2 = st.columns(2)
                        if ec1.button("保存", key=f"save_ed_{ev_id}", type="primary", use_container_width=True):
                            team_str = ",".join(new_teams)
                            updated_full_title = f"[{team_str}] {new_title}"
                            
                            # save_event 関数を event_id 付きで呼び出し
                            db.save_event(str(new_date), updated_full_title, new_cat, new_loc, new_memo, club_id, event_id=ev_id)
                            
                            st.session_state[edit_mode_key] = False
                            st.rerun()
                        if ec2.button("キャンセル", key=f"cancel_ed_{ev_id}", use_container_width=True):
                            st.session_state[edit_mode_key] = False
                            st.rerun()
                    else:
                        # --- 通常表示 ---
                        st.markdown(f"### {ev_title}")
                        st.caption(f"📅 {ev_date} | 📍 {ev_loc if ev_loc else '未定'}")
                        if ev_memo: st.info(f"📝 {ev_memo}")
                        
                        st.divider()
                        st.columns([1, 1])
                        d1, d2 = st.columns([1, 1])
                        with d1:
                            st.markdown("**回答状況**")
                            yes_names = [n for n, s in current_att.items() if s == "出席"]
                            no_names = [n for n, s in current_att.items() if s == "欠席"]
                            hold_names = [n for n, s in current_att.items() if s == "保留"]
                            
                            st.write(f"✅ 出席({len(yes_names)}): {', '.join(yes_names) if yes_names else '-'}")
                            st.write(f"❌ 欠席({len(no_names)}): {', '.join(no_names) if no_names else '-'}")
                            st.write(f"△ 保留({len(hold_names)}): {', '.join(hold_names) if hold_names else '-'}")

                        with d2:
                            st.markdown("**あなたの回答**")
                            team_options = ["--"] + ev_teams
                            default_team_idx = 0
                            if "active_team" in st.session_state and st.session_state.active_team in team_options:
                                default_team_idx = team_options.index(st.session_state.active_team)

                            sel_team = st.selectbox("チームを選択", team_options, index=default_team_idx, key=f"team_sel_{ev_id}")
                            
                            target_members = []
                            if sel_team != "--":
                                for p in players_raw:
                                    # p[8] = team_name, p[7] = is_active (playersテーブルの構造に依存)
                                    p_team = str(p[8]).strip() if (len(p) > 8 and p[8] is not None) else "未所属"
                                    p_active = p[7] if (len(p) > 7 and p[7] is not None) else 1
                                    if p_team == sel_team and int(p_active) == 1:
                                        target_members.append(p[1])
                                
                            player_options = ["--"] + sorted(target_members)
                            default_player_idx = 0
                            if "active_player" in st.session_state and st.session_state.active_player in player_options:
                                default_player_idx = player_options.index(st.session_state.active_player)

                            my_name = st.selectbox("名前を選択", player_options, index=default_player_idx, key=f"p_sel_{ev_id}")
                            
                            if my_name != "--":
                                b1, b2, b3 = st.columns(3)
                                if b1.button("出", key=f"y_{ev_id}", use_container_width=True):
                                    db.update_attendance(ev_id, my_name, "出席", club_id); st.rerun()
                                if b2.button("欠", key=f"n_{ev_id}", use_container_width=True):
                                    db.update_attendance(ev_id, my_name, "欠席", club_id); st.rerun()
                                if b3.button("保", key=f"h_{ev_id}", use_container_width=True):
                                    db.update_attendance(ev_id, my_name, "保留", club_id); st.rerun()
                        
                        if role in ["admin", "operator"]:
                            st.divider()
                            col_btn1, col_btn2 = st.columns(2)
                            if col_btn1.button("✏️ 予定を編集する", key=f"edit_btn_{ev_id}", use_container_width=True):
                                st.session_state[edit_mode_key] = True
                                st.rerun()
                            if col_btn2.button("🗑️ 完全に削除する", key=f"del_{ev_id}", type="primary", use_container_width=True):
                                db.delete_event(ev_id, club_id)
                                st.rerun()
                st.divider()

    # 3. 過去の履歴
    with menu[1]:
        past_events = sorted([e for e in parsed_events if e[1] < today_str], key=lambda x: x[1], reverse=True)
        if not past_events:
            st.info("過去の履歴はありません。")
        else:
            if role in ["admin", "operator"]:
                st.subheader("📁 履歴の管理")

                for e in past_events:
                    with st.expander(f"{e[1]} - {e[7]}"):
                        st.write(f"場所: {e[4]}")
                        st.write(f"チーム: {', '.join(e[6])}")
                        if st.button("この過去履歴を削除", key=f"past_del_{e[0]}", type="primary"):
                            db.delete_event(e[0], club_id)
                            st.rerun()
            else:
                display_data = [{"日付": e[1], "チーム": ", ".join(e[6]), "予定": e[7], "場所": e[4]} for e in past_events]
                st.dataframe(pd.DataFrame(display_data), use_container_width=True, hide_index=True)