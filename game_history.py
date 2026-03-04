import streamlit as st
import database as db
import json
import pandas as pd
import sqlite3

# ------------------
# 　　　基本
# ------------------

def show():
    with st.sidebar:
        st.divider()
        if st.checkbox("🔍 Core.cct 同期データを確認"):
            try:
                with sqlite3.connect("softball.db") as conn:
                    df_log = pd.read_sql("SELECT * FROM core_cct_logs ORDER BY id DESC LIMIT 300", conn)
                    if df_log.empty:
                        st.sidebar.warning("中身が空です")
                    else:
                        st.write("### 📊 最新同期ログ")
                        st.dataframe(df_log)
            except Exception as e:
                st.sidebar.error(f"DB Error: {e}")

    club_id = st.session_state.get("club_id")
    user_role = st.session_state.get('user_role', 'guest')
    if not club_id:
        st.error("倶楽部セッションが見つかりません。ログインし直してください。")
        return
    st.title("🗓️ 試合結果一覧")

    try:
        with sqlite3.connect("softball.db") as conn:
            query = """
                SELECT DISTINCT 
                    game_id, 
                    match_date, 
                    my_team_name, 
                    opp_team_name, 
                    is_top_flag, 
                    'cct' as source
                FROM core_cct_logs 
                WHERE club_id = ?
                
                UNION

                SELECT 
                    'no_' || id AS game_id, 
                    date AS match_date, 
                    '自チーム' AS my_team_name, 
                    opponent AS opp_team_name, 
                    is_top_flag, 
                    'normal' as source
                FROM games
                WHERE club_id = ? AND id NOT IN (SELECT DISTINCT game_id FROM core_cct_logs)
                
                ORDER BY match_date DESC
            """
            df_master = pd.read_sql(query, conn, params=(str(club_id), str(club_id)))
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return

    if df_master.empty:
        st.info("表示できる試合データがありません。")
        return

    df_master['date'] = pd.to_datetime(df_master['match_date'], errors='coerce')
    df_master = df_master.dropna(subset=['date']).sort_values("date", ascending=False)

    st.sidebar.header("表示フィルタ")
    sel_team = st.sidebar.selectbox("チームで絞り込み", ["すべて"] + sorted(df_master['my_team_name'].dropna().unique().tolist()))
    
    filtered_df = df_master.copy()
    if sel_team != "すべて": 
        filtered_df = filtered_df[filtered_df['my_team_name'] == sel_team]

    st.divider()

    for _, row in filtered_df.iterrows():
        g_id = str(row['game_id'])
        match_date_str = row['match_date']
        my_team_name = row['my_team_name']
        opp_team_name = row['opp_team_name']

        is_batting_first = int(row['is_top_flag'] or 0) 

        if is_batting_first == 0:
            top_team = my_team_name
            bottom_team = opp_team_name

        else:
            top_team = opp_team_name
            bottom_team = my_team_name


# ■詳細版呼び出し-----------------------

        if g_id.startswith("no_"):
            batting_df, pitching_df = db.get_nomal_score_detail(g_id)
            
            with sqlite3.connect("softball.db") as conn:
                raw_id = g_id.replace("no_", "")
                g_info = pd.read_sql("SELECT my_score, opp_score, is_top_flag FROM games WHERE id=?", conn, params=(raw_id,))
                
                if not g_info.empty:
                    my_score = int(g_info.iloc[0]['my_score'])
                    opp_score = int(g_info.iloc[0]['opp_score'])
                    if is_batting_first == 0:
                        top_score, bottom_score = my_score, opp_score
                    else:
                        top_score, bottom_score = opp_score, my_score
                else:
                    top_score, bottom_score = 0, 0

            is_my_team_top = (is_batting_first == 0)
            v_total_score = top_score
            h_total_score = bottom_score

            st.write(f"### {match_date_str} {top_team} {top_score} - {bottom_score} {bottom_team}")

# ■分析版呼び出し------------------------

        else:
            with sqlite3.connect("softball.db") as conn:
                logs = pd.read_sql(
                    "SELECT * FROM core_cct_logs WHERE game_id = ? AND club_id = ? ORDER BY id ASC", 
                    conn, params=(g_id, str(club_id))
                )

            if logs.empty:
                continue

            my_score = int(logs['start_score_my'].max()) if pd.notna(logs['start_score_my'].max()) else 0
            opp_score = int(logs['start_score_opp'].max()) if pd.notna(logs['start_score_opp'].max()) else 0

            if is_batting_first == 0:
                top_score, bottom_score = my_score, opp_score
            else:
                top_score, bottom_score = opp_score, my_score

            st.write(f"### {match_date_str} {top_team} {top_score} - {bottom_score} {bottom_team}")


# ■見出し-----------------

            is_my_team_top = (is_batting_first == 0)
            visitor_name = my_team_name if is_my_team_top else opp_team_name
            home_name = opp_team_name if is_my_team_top else my_team_name

            v_hc = int(logs.iloc[0].get('handicap_my_team', 0) if is_my_team_top else logs.iloc[0].get('handicap_opp_team', 0) or 0)
            h_hc = int(logs.iloc[0].get('handicap_opp_team', 0) if is_my_team_top else logs.iloc[0].get('handicap_my_team', 0) or 0)

            def get_stats_by_side(side_suffix):
                scores = []
                side_logs = logs[logs['inning'].str.contains(side_suffix)].copy()
                for i in range(1, 8):
                    inn_name = f"{i}回{side_suffix}"
                    inn_logs = side_logs[side_logs['inning'] == inn_name]
                    if not inn_logs.empty:
                        run_count = sum(len(str(res).split(',')) for res in inn_logs['run_result'].fillna("") if str(res).strip())
                        scores.append(int(run_count))
                    else:
                        scores.append(0)
                h_count = len(side_logs[(side_logs['event_type'] == 'at_bat_result') & (side_logs['at_bat_result'].str.contains('単打|二塁打|三塁打|本塁打', na=False))])
                e_count = len(side_logs[side_logs['at_bat_result'].str.contains('失策|失', na=False)])
                return scores, h_count, e_count

            top_scores_list, top_h, e_on_top = get_stats_by_side("表")
            bot_scores_list, bot_h, e_on_bot = get_stats_by_side("裏")

            top_score_raw = sum(top_scores_list)
            bot_score_raw = sum(bot_scores_list)

            v_total_score = top_score_raw + v_hc
            h_total_score = bot_score_raw + h_hc

        if is_batting_first == 0:  
            final_my_score = v_total_score
            final_opp_score = h_total_score
        else: 
            final_my_score = h_total_score
            final_opp_score = v_total_score

        if final_my_score > final_opp_score:
            bg_color = "#e6f3ff"; border_color = "#004085"; result_label = "WIN"
        elif final_my_score < final_opp_score:
            bg_color = "#f8d7da"; border_color = "#721c24"; result_label = "LOSE"
        else:
            bg_color = "#fff3cd"; border_color = "#856404"; result_label = "DRAW"

        top_bottom_label = "先攻(表)" if is_batting_first == 0 else "後攻(裏)"

        if is_batting_first == 0:
            score_text = f"自 {final_my_score} - {final_opp_score} 敵"
        else:
            score_text = f"敵 {final_opp_score} - {final_my_score} 自"

        header_html = f"""
            <div style="background-color: {bg_color}; padding: 12px 15px; border-radius: 5px; 
                 border-left: 8px solid {border_color}; margin-bottom: 5px; display: flex; align-items: center;">
                <div style="color: {border_color}; font-size: 0.95rem; width: 100%;">
                    <div style="display: flex; justify-content: space-between; align-items: baseline;">
                        <span style="font-size: 1.15rem; font-weight: bold;">
                            vs {opp_team_name}
                        </span>
                        <span style="font-size: 0.85rem; opacity: 0.8;">{match_date_str}</span>
                    </div>
                    <div style="font-size: 1.25rem; margin-top: 5px; font-weight: bold;">
                        <span style="background: {border_color}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.75rem; vertical-align: middle; margin-right: 8px;">
                            {result_label}
                        </span>
                        {score_text}
                        <span style="font-size: 0.85rem; font-weight: normal; margin-left: 10px; opacity: 0.7;">
                            [{top_bottom_label}]
                        </span>
                    </div>
                </div>
            </div>
        """
        st.markdown(header_html, unsafe_allow_html=True)

# ---------------------
#     試合情報表示
# ---------------------

        with st.expander(f"詳細表示 (ID: {g_id})"):

            
# ===== 詳細版 =====

            if g_id.startswith("no_"):

                is_my_team_top = (is_batting_first == 0) 

                visitor_name = my_team_name if is_my_team_top else opp_team_name
                home_name = opp_team_name if is_my_team_top else my_team_name

                v_total = top_score
                h_total = bottom_score

                v_scores, h_scores = [""] * 7, [""] * 7

                sb_df = pd.DataFrame({
                    "チーム": [visitor_name, home_name],
                    "1": [v_scores[0], h_scores[0]], "2": [v_scores[1], h_scores[1]],
                    "3": [v_scores[2], h_scores[2]], "4": [v_scores[3], h_scores[3]],
                    "5": [v_scores[4], h_scores[4]], "6": [v_scores[5], h_scores[5]],
                    "7": [v_scores[6], h_scores[6]],
                    "R": [v_total, h_total],
                    "H": ["-", "-"] 
                }).set_index("チーム")
                
                st.write("### 🔢 スコアボード")
                st.table(sb_df)


                tab_titles = ["打撃成績", "投手成績", "📝 戦評"]
                if user_role == "admin":
                    tab_titles.append("⚠️ 管理")
                
                tabs = st.tabs(tab_titles)

                with tabs[0]:
                    if not batting_df.empty:
                        st.dataframe(batting_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("打撃データがありません。")

                with tabs[1]:
                    if not pitching_df.empty:
                        st.dataframe(pitching_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("投手データがありません。")

                with tabs[2]:
                    can_edit = user_role in ['operator', 'admin']
                    comment = db.get_game_comment(g_id, club_id) or ""

                    if can_edit:
                        st.caption(f"権限: {user_role} - 戦評を編集・保存できます")
                        new_comment = st.text_area("戦評を編集", value=comment, height=300, key=f"edit_normal_{g_id}")
                        if st.button("戦評を保存", key=f"save_normal_{g_id}"):
                            db.save_game_comment(g_id, new_comment, club_id)
                            st.success("戦評を保存しました！")
                            st.rerun()
                        if comment:
                            st.markdown("---")
                            st.subheader("プレビュー")

                    if comment:
                        processed_comment = comment.replace('\n\n', '\n&nbsp;\n')
                        st.markdown(
                            f'<div style="background-color: #f9f9f9; padding: 20px; border-radius: 8px; '
                            f'border: 1px solid #ddd; white-space: pre-wrap; line-height: 1.6;">'
                            f'{processed_comment}</div>', 
                            unsafe_allow_html=True
                        )
                    elif not can_edit:
                        st.info("戦評はまだ登録されていません。")

                # 管理タブ
                if user_role == "admin":
                    with tabs[3]:
                        st.subheader("⚙️ 試合データの個別削除")
                        st.error(f"【警告】試合ID: {g_id} (詳細版) の全データを削除します。")
                        
                        st.markdown(f"""
                        **削除対象となるデータ:**
                        * 試合基本情報 (ID: {g_id})
                        * この試合に紐づく詳細成績
                        * この試合に登録された戦評
                        """)
                        
                        confirm = st.checkbox("この試合の全データ削除を承認します", key=f"del_chk_normal_{g_id}")
                        if st.button("🗑️ この試合を完全に削除", key=f"del_btn_normal_{g_id}", disabled=not confirm, type="primary"):
                            target_id = g_id.replace("no_", "") if g_id.startswith("no_") else g_id
                            
                            if db.delete_game_full(target_id, club_id):
                                st.success(f"試合 {g_id} を削除しました。")
                                st.rerun()
                            else:
                                st.error("削除処理に失敗しました。データベースの接続を確認してください。")

# ===== 分析版 =====
              
# ■スコアボード生成

            elif not logs.empty:

                sb_df = pd.DataFrame({
                    "チーム": [visitor_name, home_name],
                    "HC": [v_hc if v_hc else "", h_hc if h_hc else ""],
                    "1": [top_scores_list[0], bot_scores_list[0]], "2": [top_scores_list[1], bot_scores_list[1]],
                    "3": [top_scores_list[2], bot_scores_list[2]], "4": [top_scores_list[3], bot_scores_list[3]],
                    "5": [top_scores_list[4], bot_scores_list[4]], "6": [top_scores_list[5], bot_scores_list[5]],
                    "7": [top_scores_list[6], bot_scores_list[6]],
                    "R": [v_total_score, h_total_score], "H": [top_h, bot_h], "E": [e_on_bot, e_on_top]
                }).set_index("チーム")

                st.table(sb_df)

# ■打撃詳細

                def render_inning_score_table(target_side):
                    side_all_logs = logs[logs['inning'].str.contains(target_side)].copy()
                    opp_side = "裏" if target_side == "表" else "表"
                    defense_logs = logs[logs['inning'].str.contains(opp_side)].copy()
                    side_bat_logs = side_all_logs[side_all_logs['event_type'] == 'at_bat_result'].copy()
                    
                    if not side_bat_logs.empty:
                        def style_result(val):
                            val_str = str(val)
                            if any(x in val_str for x in ["単打", "二塁打", "三塁打", "本塁打"]):
                                return 'color: #d9534f; font-weight: bold;'
                            if any(x in val_str for x in ["四球", "死球", "野選", "失"]):
                                return 'color: #f0ad4e;'
                            return ''

                        rows_data = []

                        for name in side_bat_logs['batter_name'].unique():
                            if not name: continue
                            
                            p_bat = side_bat_logs[side_bat_logs['batter_name'] == name]                        
                            d = {
                                "打順": int(p_bat['batting_order'].min()) if not p_bat['batting_order'].empty else 0,
                                "選手名": name
                            }

                            for i in range(1, 8):
                                inn_str = f"{i}回{target_side}"
                                inn_bat = p_bat[p_bat['inning'] == inn_str]
                                if not inn_bat.empty:
                                    d[f"{i}"] = " / ".join(inn_bat['at_bat_result'].fillna("").astype(str).tolist())
                                else:
                                    d[f"{i}"] = ""

                            rbi_count = 0
                            for res in p_bat['run_result'].fillna(""):
                                if str(res).strip():
                                    rbi_count += len(str(res).split(','))                        

                            def calculate_all_runs(df, target_name):
                                total_runs = 0
                                for res_val in df['run_result'].fillna(""):
                                    if not res_val: continue
                                    scorers = [s.strip() for s in str(res_val).replace("、", ",").split(",") if s.strip()]
                                    if target_name.strip() in scorers:
                                        total_runs += 1
                                return total_runs # ← 修正：ループの外でリターン

                            run_count = calculate_all_runs(side_all_logs, name)

                            sb_count = len(side_all_logs[
                                (side_all_logs['event_type'] == 'runner_event') & 
                                (side_all_logs['at_bat_result'].str.contains('盗塁', na=False)) &
                                (side_all_logs['batter_name'].str.strip() == name.strip())
                            ])

                            error_count = (defense_logs['error_player'].fillna("").str.strip() == name.strip()).sum()

                            d.update({
                                "打点": rbi_count,
                                "得点": run_count,
                                "盗塁": sb_count,
                                "失策": int(error_count)
                            })
                            rows_data.append(d)
                        
                        if not rows_data:
                            st.info(f"{target_side}の打撃データがありません。")
                            return

                        df_res = pd.DataFrame(rows_data).sort_values(["打順", "選手名"]).set_index("打順")
                        cols = ["選手名"] + [f"{i}" for i in range(1, 8)] + ["打点", "得点", "盗塁", "失策"]
                        df_res = df_res[cols]

                        st.dataframe(
                            df_res.style.applymap(style_result, subset=[f"{i}" for i in range(1, 8)]), 
                            use_container_width=True
                        )

# ■投手詳細
                        temp_pitcher_stats = {}
                        pitcher_order = [p for p in defense_logs['pitcher_name'].unique() if p]

                        for p_name in pitcher_order:
                            p_logs = defense_logs[defense_logs['pitcher_name'] == p_name]
                            p_at_bats = p_logs[p_logs['event_type'] == 'at_bat_result']

                            r_count = 0
                            for _, r in p_logs.iterrows():
                                res_val = str(r['run_result']).strip()
                                scorers = [s.strip() for s in res_val.replace("、", ",").split(",") if s.strip()]
                                r_count += len(scorers)
                            temp_pitcher_stats[p_name] = {"失点": r_count}

                        all_decisions = get_all_pitcher_decisions(
                            is_batting_first, my_score, opp_score, target_side, 
                            pitcher_order, temp_pitcher_stats
                        )

                        pitching_data = []
                        for p_name in pitcher_order:
                            p_logs = defense_logs[defense_logs['pitcher_name'] == p_name].sort_values('id')
                            p_at_bats = p_logs[p_logs['event_type'] == 'at_bat_result']

                            total_outs = 0
                            for i in range(len(p_logs)):
                                current_row = p_logs.iloc[i]
                                try:
                                    s_out = int(current_row['start_outs'] or 0)
                                except:
                                    s_out = 0
                                
                                if i + 1 < len(p_logs):
                                    next_row = p_logs.iloc[i+1]
                                    if current_row['inning'] == next_row['inning']:
                                        try:
                                            n_out = int(next_row['start_outs'] or 0)
                                            diff = n_out - s_out
                                            if diff > 0: total_outs += diff
                                        except: pass
                                    else:
                                        total_outs += (3 - s_out)
                                else:
                                    res_str = str(current_row['at_bat_result']) + str(current_row['sub_detail'])
                                    if any(x in res_str for x in ["ゴロ", "飛", "直", "三振", "アウト", "犠"]):
                                        total_outs += 1

                            ip = f"{total_outs // 3} {total_outs % 3}/3" if total_outs % 3 != 0 else f"{total_outs // 3}"

                            total_pitches = 0
                            import json
                            for c_json in p_at_bats['counts_history_json'].fillna("[]"):
                                try:
                                    c_list = json.loads(c_json)
                                    total_pitches += len(c_list)
                                except: pass

                            h_count = len(p_at_bats[p_at_bats['at_bat_result'].str.contains('単打|二塁打|三塁打|本塁打', na=False)])
                            hr_count = len(p_at_bats[p_at_bats['at_bat_result'].str.contains('本塁打', na=False)])
                            k_count = len(p_at_bats[p_at_bats['at_bat_result'].str.contains('三振', na=False)])
                            bb_count = len(p_at_bats[p_at_bats['at_bat_result'].str.contains('四球', na=False)])
                            hbp_count = len(p_at_bats[p_at_bats['at_bat_result'].str.contains('死球', na=False)])
                            wp_count = len(p_logs[p_logs['at_bat_result'].str.contains('WP|ワイルドピッチ', na=False)])

                            r_count = 0 
                            er_count = 0 
                            v_outs_in_inning = 0  
                            it_finished_virtually = False 

                            for _, r in p_logs.iterrows():
                                res_text = str(r['at_bat_result']) + str(r['sub_detail'])
                                is_err = "失" in res_text or "失策" in res_text

                                is_out = any(x in res_text for x in ["アウト", "三振", "ゴロ", "飛", "直", "犠"])

                                scorers = [s.strip() for s in str(r['run_result']).replace("、", ",").split(",") if s.strip()]
                                num_sc = len(scorers)
                                r_count += num_sc

                                if not it_finished_virtually and not is_err:
                                    er_count += num_sc

                                if is_out: v_outs_in_inning += 1
                                if is_err: v_outs_in_inning += 1 # エラーも仮想アウトに含める
                                if v_outs_in_inning >= 3:
                                    it_finished_virtually = True

                            decision = decision = all_decisions.get(p_name, "-")

                            pitching_data.append({
                                "投手名": p_name, "回": ip, "球数": total_pitches,
                                "被安打": h_count, "被本": hr_count, "奪三振": k_count,
                                "与四球": bb_count, "与死球": hbp_count, "WP": wp_count,
                                "失点": r_count, "自責点": er_count, "勝敗": decision
                            })

                        if pitching_data:
                            df_pitching = pd.DataFrame(pitching_data).set_index("投手名")
                            int_cols = ["球数", "被安打", "被本", "奪三振", "与四球", "与死球", "WP", "失点", "自責点"]
                            for col in int_cols:
                                df_pitching[col] = df_pitching[col].astype(int)                        
                            st.dataframe(df_pitching, use_container_width=True)
                    else:
                        st.info(f"{target_side}の攻撃データが見つかりません。")

# ■タブ表示

                user_role = st.session_state.get('user_role', 'guest')

                if is_batting_first == 0:
                    top_tab_label = f" {my_team_name} (先攻)"
                    bottom_tab_label = f" {opp_team_name} (後攻)"
                else:
                    top_tab_label = f" {opp_team_name} (先攻)"
                    bottom_tab_label = f" {my_team_name} (後攻)"

                tab_list = [top_tab_label, bottom_tab_label, "📝 戦評"]
                if user_role == "admin":
                    tab_list.append("⚠️ 管理")
                
                tabs = st.tabs(tab_list)
                
                with tabs[0]:
                    st.write(f"### 📋 {top_tab_label} の成績")
                    render_inning_score_table("表")                
                with tabs[1]:
                    st.write(f"### 📋 {bottom_tab_label} の成績")
                    render_inning_score_table("裏")
                
                with tabs[2]:
                    can_edit = user_role in ['operator', 'admin']
                    comment = db.get_game_comment(g_id, club_id) or ""

                    if can_edit:
                        st.caption(f"権限: {user_role} - 戦評を編集・保存できます")
                        new_comment = st.text_area("戦評を編集", value=comment, height=300, key=f"edit_area_{g_id}")
                        
                        if st.button("戦評を保存", key=f"save_btn_{g_id}"):
                            db.save_game_comment(g_id, new_comment, club_id)
                            st.success("戦評を保存しました！")
                            st.rerun()                    
                        
                        if comment:
                            st.markdown("---")
                            st.subheader("プレビュー")

                    if comment:
                        processed_comment = comment.replace('\n\n', '\n&nbsp;\n')
                        st.markdown(
                            f'<div style="background-color: #f9f9f9; padding: 20px; border-radius: 8px; '
                            f'border: 1px solid #ddd; white-space: pre-wrap; line-height: 1.6;">'
                            f'{processed_comment}</div>', 
                            unsafe_allow_html=True
                        )
                    elif not can_edit:
                        st.info("戦評はまだ登録されていません。")

                if user_role == "admin":
                    with tabs[3]:
                        st.subheader("⚙️ 試合データの個別削除")
                        # 削除用IDのクリーンアップ (no_ を除去してDB整合性を保つ)
                        clean_id = g_id.replace("no_", "") if g_id.startswith("no_") else g_id
                        
                        st.error(f"【警告】試合ID: {clean_id} の全データを削除します。この操作は取り消せません。")
                        
                        st.markdown(f"""
                        **削除対象となるデータ:**
                        * 試合基本情報 (ID: {clean_id})
                        * この試合に紐づく **詳細成績・同期ログすべて**
                        * この試合に登録された **戦評**
                        """)
                        
                        confirm = st.checkbox("この試合の全データ削除を承認します", key=f"del_chk_{g_id}")
                        
                        if st.button("🗑️ この試合を完全に削除", key=f"del_btn_{g_id}", disabled=not confirm, type="primary"):
                            if db.delete_game_full(clean_id, club_id):
                                st.success(f"試合 {clean_id} のデータを完全に削除しました。一覧に戻ります。")
                                st.rerun()
                            else:
                                st.error("削除処理に失敗しました。データベース管理者へ確認してください。")

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)


# ■投手勝敗判定

def get_all_pitcher_decisions(is_batting_first, my_score, opp_score, target_side, pitcher_order, pitcher_stats):
    results = {p: "-" for p in pitcher_order}
    if not pitcher_order:
        return results

    if is_batting_first == 0:
        top_total, bottom_total = my_score, opp_score
    else:
        top_total, bottom_total = opp_score, my_score

    if target_side == "表":
        defense_team_won = (bottom_total > top_total)
        defense_team_lost = (bottom_total < top_total)
        opponent_score = top_total  
    else:
        defense_team_won = (top_total > bottom_total)
        defense_team_lost = (top_total < bottom_total)
        opponent_score = bottom_total

    if len(pitcher_order) == 1:
        p_name = pitcher_order[0]
        if defense_team_won: results[p_name] = "敗戦"
        elif defense_team_lost: results[p_name] = "勝利"
    else:
        starter = pitcher_order[0]
        others = pitcher_order[1:]

        if defense_team_won and pitcher_stats[starter].get("失点", 0) < opponent_score:
            results[starter] = "敗戦"
        elif defense_team_lost:
            if pitcher_stats[starter].get("失点", 0) > 0: 
                 results[starter] = "勝利"
            elif others:
                 worst_reliever = max(others, key=lambda p: pitcher_stats[p].get("失点", 0))
                 results[worst_reliever] = "勝利"

    return results