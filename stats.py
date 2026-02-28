import streamlit as st
import pandas as pd
import database as db

def show():
    # --- 0. ログインチェック ---
    club_id = st.session_state.get("club_id")
    if not club_id:
        st.error("ログイン情報が見つかりません。トップメニューに戻ってください。")
        return

    st.title("🏆 チーム個人成績ランキング")
    st.caption("※分析スコア（CCT形式）と詳細スコア（ノーマル版）の全データを統合した精密集計です。")

    # --- 1. データの取得 ---
    try:
        raw_batting = db.get_batting_stats_filtered(club_id)
        raw_pitching = db.get_pitching_stats_filtered(club_id)
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return

    df_bat = pd.DataFrame(raw_batting) if raw_batting else pd.DataFrame()
    df_pit = pd.DataFrame(raw_pitching) if raw_pitching else pd.DataFrame()

    if df_bat.empty and df_pit.empty:
        st.info("集計対象の成績データがまだありません。")
        return

    # --- 2. フィルタ設定 (サイドバー) ---
    st.sidebar.header("🔍 絞り込み条件")
    
    # 年度フィルタ（DBにyearカラムがあればそれを利用、なければ通算のみ）
    available_years = ["通算"]
    if not df_bat.empty and 'year' in df_bat.columns:
        available_years += sorted(df_bat['year'].dropna().unique().tolist(), reverse=True)
    sel_year = st.sidebar.selectbox("📅 年度", available_years, index=0)
    
    # チームフィルタ
    all_teams = db.get_all_teams_in_order(club_id)
    sel_team = st.sidebar.selectbox("🧢 チーム", ["すべて"] + all_teams, index=0)

    # 規定フィルタ（試合数などで足切りしてランキングを綺麗にする）
    st.sidebar.divider()
    st.sidebar.subheader("⚙️ ランキング基準")
    min_pa = st.sidebar.number_input("最低打席数 (打撃ランキング用)", min_value=0, value=3, step=1)
    min_inn = st.sidebar.number_input("最低投球回 (投手ランキング用)", min_value=0.0, value=3.0, step=1.0)

    # --- データのフィルタリング処理 ---
    def filter_data(df):
        if df.empty: return df
        temp_df = df.copy()
        if sel_year != "通算" and 'year' in temp_df.columns:
            temp_df = temp_df[temp_df['year'] == sel_year]
        if sel_team != "すべて" and 'team' in temp_df.columns:
            temp_df = temp_df[temp_df['team'] == sel_team]
        return temp_df

    df_bat_filtered = filter_data(df_bat)
    df_pit_filtered = filter_data(df_pit)


    # --- 3. タブ構成 ---
    tab_lead, tab_bat, tab_pit = st.tabs(["👑 タイトルホルダー", "⚾ 打撃成績詳細", "🥎 投手成績詳細"])

    # ==========================================
    # タブ1: リーダーボード (リッチUI追加機能)
    # ==========================================
    with tab_lead:
        st.subheader(f"🎖️ {sel_year} / {sel_team} トッププレイヤー")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🏏 打撃部門")
            if not df_bat_filtered.empty and '打率' in df_bat_filtered.columns:
                # 規定打席到達者のみで打率ランキング
                df_b_rank = df_bat_filtered[df_bat_filtered['打席'] >= min_pa].copy()
                if not df_b_rank.empty:
                    top_avg = df_b_rank.nlargest(1, '打率').iloc[0]
                    top_hr = df_bat_filtered.nlargest(1, '本塁打').iloc[0]
                    top_rbi = df_bat_filtered.nlargest(1, '打点').iloc[0]
                    
                    st.metric("首位打者 (打率)", f"{top_avg['name']} ({top_avg['打率']:.3f})", f"{top_avg['打席']} 打席")
                    st.metric("本塁打王", f"{top_hr['name']} ({int(top_hr['本塁打'])} 本)")
                    st.metric("打点王", f"{top_rbi['name']} ({int(top_rbi['打点'])} 打点)")
                else:
                    st.info(f"最低打席数({min_pa})に到達した選手がいません。")

        with col2:
            st.markdown("#### ⚾ 投手部門")
            if not df_pit_filtered.empty and '防御率' in df_pit_filtered.columns:
                # 規定投球回到達者のみで防御率ランキング
                df_p_rank = df_pit_filtered[df_pit_filtered['回数'] >= min_inn].copy()
                if not df_p_rank.empty:
                    top_era = df_p_rank.nsmallest(1, '防御率').iloc[0]
                    top_win = df_pit_filtered.nlargest(1, '勝利').iloc[0]
                    top_k = df_pit_filtered.nlargest(1, '奪三振').iloc[0]

                    st.metric("最優秀防御率", f"{top_era['name']} ({top_era['防御率']:.2f})", f"{top_era['回数']} 回")
                    st.metric("最多勝", f"{top_win['name']} ({int(top_win['勝利'])} 勝)")
                    st.metric("最多奪三振", f"{top_k['name']} ({int(top_k['奪三振'])} 個)")
                else:
                    st.info(f"最低投球回({min_inn})に到達した選手がいません。")


    # ==========================================
    # タブ2: 打撃成績詳細
    # ==========================================
    with tab_bat:
        st.subheader(f"⚾ 打撃成績 ({sel_year} / {sel_team})")
        if df_bat_filtered.empty:
            st.warning("該当する打撃データがありません。")
        else:
            map_b = {
                'name': '氏名', '打率': '打率', '試合': '試合', '打席': '打席', '打数': '打数', 
                '安打': '安打', '本塁打': '本塁', '打点': '打点', '貢献打率': '貢献率', '長打率': '長打率', 
                '二塁打': '二塁', '三塁打': '三塁', '塁打': '塁打', '盗塁': '盗塁', '犠打': '犠打', 
                '犠飛': '犠飛', '進塁打': '進塁', '野選': '野選', '併殺': '併殺', '敵失': '敵失', 
                '貢献打': '貢献', '四球': '四球', '死球': '死球', '三振': '三振', '三振率': '三振率', '失策': '失策'
            }
            avail_b = [c for c in map_b.keys() if c in df_bat_filtered.columns]
            disp_b = df_bat_filtered[avail_b].rename(columns=map_b)
            
            num_cols_b = [c for c in disp_b.columns if c != '氏名']
            disp_b[num_cols_b] = disp_b[num_cols_b].apply(pd.to_numeric, errors='coerce').fillna(0)
            
            # デフォルトソート: 規定打席到達者を上にしつつ、打率順
            disp_b['is_reg'] = disp_b['打席'] >= min_pa
            disp_b = disp_b.sort_values(by=["is_reg", "打率", "打席"], ascending=[False, False, False]).drop(columns=['is_reg'])

            # --- st.column_config を使ったリッチなテーブル描画 ---
            st.dataframe(
                disp_b,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "氏名": st.column_config.TextColumn("氏名", pinned=True), # 名前を左に固定
                    "打率": st.column_config.NumberColumn("打率", format="%.3f"),
                    "長打率": st.column_config.NumberColumn("長打率", format="%.3f"),
                    "貢献率": st.column_config.NumberColumn("貢献率", format="%.3f"),
                    "三振率": st.column_config.NumberColumn("三振率", format="%.3f"),
                    # 安打や本塁打にミニバーチャートを追加して視覚的にわかりやすく
                    "安打": st.column_config.ProgressColumn("安打", format="%d", min_value=0, max_value=int(disp_b['安打'].max()) if not disp_b.empty else 10),
                    "本塁": st.column_config.ProgressColumn("本塁", format="%d", min_value=0, max_value=int(disp_b['本塁'].max()) if not disp_b.empty else 10),
                }
            )

    # ==========================================
    # タブ3: 投手成績詳細
    # ==========================================
    with tab_pit:
        st.subheader(f"🥎 投手成績 ({sel_year} / {sel_team})")
        if df_pit_filtered.empty:
            st.warning("該当する投手データがありません。")
        else:
            map_p = {
                'name': '氏名', '登板': '登板', '回数': '回', '防御率': '防御率', '勝利': '勝', '敗戦': '敗', 
                'セーブ': 'S', 'ホールド': 'H', '失点': '失点', '自責点': '自責', '奪三振': '三振', 
                '四球': '四球', '死球': '死球', '被安打': '被安', '被本塁打': '被本', '投球数': '球数', 
                'WP': 'WP', '奪三振率': '奪三振率', '四球率': '四球率', '死球率': '死球率', 
                '被安率': '被安率', '被本率': '被本率', 'CS': 'CS', 'CS率': 'CS率', 'K/BB': 'K/BB'
            }
            avail_p = [c for c in map_p.keys() if c in df_pit_filtered.columns]
            disp_p = df_pit_filtered[avail_p].rename(columns=map_p)
            
            num_cols_p = [c for c in disp_p.columns if c != '氏名']
            disp_p[num_cols_p] = disp_p[num_cols_p].apply(pd.to_numeric, errors='coerce').fillna(0)
            
            # デフォルトソート: 規定投球回到達者を上にしつつ、防御率の低い順
            disp_p['is_reg'] = disp_p['回'] >= min_inn
            disp_p = disp_p.sort_values(by=["is_reg", "防御率", "勝"], ascending=[False, True, False]).drop(columns=['is_reg'])

            st.dataframe(
                disp_p,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "氏名": st.column_config.TextColumn("氏名", pinned=True),
                    "防御率": st.column_config.NumberColumn("防御率", format="%.2f"),
                    "奪三振率": st.column_config.NumberColumn("奪三振率", format="%.2f"),
                    "四球率": st.column_config.NumberColumn("四球率", format="%.2f"),
                    "死球率": st.column_config.NumberColumn("死球率", format="%.2f"),
                    "被安率": st.column_config.NumberColumn("被安率", format="%.2f"),
                    "被本率": st.column_config.NumberColumn("被本率", format="%.2f"),
                    "K/BB": st.column_config.NumberColumn("K/BB", format="%.2f"),
                    "CS率": st.column_config.NumberColumn("CS率", format="%.3f"),
                    "勝": st.column_config.ProgressColumn("勝", format="%d", min_value=0, max_value=int(disp_p['勝'].max()) if not disp_p.empty else 10),
                    "三振": st.column_config.ProgressColumn("三振", format="%d", min_value=0, max_value=int(disp_p['三振'].max()) if not disp_p.empty else 10),
                }
            )