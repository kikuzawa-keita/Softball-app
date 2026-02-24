import streamlit as st
import pandas as pd
import database as db 

def show():
    # --- 0. ログインチェック ---
    club_id = st.session_state.get("club_id")
    if not club_id:
        st.error("倶楽部セッションが見つかりません。ログインし直してください。")
        return

    st.title("🏆 チーム個人成績ランキング")

    # --- 1. データの取得 ---
    try:
        # database.py で新しく実装した精密集計版を呼び出す
        raw_stats = db.get_batting_stats_filtered(club_id)
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return

    if not raw_stats:
        st.info("集計対象データがありません。")
        return

    # 全データをDataFrame化
    df_all = pd.DataFrame(raw_stats)
    
    # --- 2. フィルタ設定 (サイドバー) ---
    st.sidebar.header("表示条件")
    # 年度フィルタ（現在は"通算"のみ。拡張性確保のためリスト化）
    years = ["通算"] 
    sel_year = st.sidebar.selectbox("年度", years, index=0)
    
    # チームフィルタ
    all_teams = db.get_all_teams_in_order(club_id)
    sel_team = st.sidebar.selectbox("チーム", ["すべて"] + all_teams, index=0)

    # フィルタリング実行 (将来的な拡張用)
    df_filtered = df_all.copy()
    # ※ チーム絞り込みロジックなどが必要な場合はここに追加

    tab1, tab2 = st.tabs(["⚾ 打撃成績", "🥎 投手成績"])

    # --- 3. 打撃成績タブ ---
    with tab1:
        st.subheader(f"⚾ 打撃部門 ({sel_year} / {sel_team})")
        
        # 表示項目と日本語名のマッピング（ご要望の全項目を網羅）
        mapping = {
            'name': '氏名', 
            '打率': '打率',    # 氏名のすぐ右に
            '試合': '試合', 
            '打席': '打席', 
            '打数': '打数', 
            '安打': '安打', 
            '本塁打': '本塁',  # 主要な本塁打を前に
            '打点': '打点', 
            '貢献打率': '貢献率',
            '長打率': '長打率',
            '二塁打': '二塁', 
            '三塁打': '三塁', 
            '塁打': '塁打',
            '盗塁': '盗塁', 
            '犠打': '犠打', 
            '犠飛': '犠飛', 
            '進塁打': '進塁', 
            '野選': '野選', 
            '併殺': '併殺', 
            '敵失': '敵失',
            '貢献打': '貢献', 
            '四球': '四球', 
            '死球': '死球',
            '三振': '三振', 
            '三振率': '三振率',
            '失策': '失策'
        }
        
        # 1. カラムの抽出とリネーム
        available_cols = [c for c in mapping.keys() if c in df_filtered.columns]
        disp_df = df_filtered[available_cols].rename(columns=mapping)
        
        # 2. 数値型への変換（ソートやフォーマットを正しく行うため）
        num_cols = [c for c in disp_df.columns if c != '氏名']
        disp_df[num_cols] = disp_df[num_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
        
        # 3. ソート（デフォルトは打率、次いで打席数）
        disp_df = disp_df.sort_values(by=["打率", "打席"], ascending=[False, False])

        # 4. 表示フォーマットの設定
        format_dict = {col: "{:g}" for col in num_cols} # 基本（整数等）はそのまま
        # 率系のカラムは小数点第3位まで表示
        rate_cols = ["打率", "長打率", "三振率", "貢献率"]
        for rc in rate_cols:
            if rc in disp_df.columns:
                format_dict[rc] = "{:.3f}"

        # 5. テーブル表示（ここ1回のみ！）
        st.dataframe(
            disp_df.style.format(format_dict)
            .highlight_max(subset=["打率", "打点", "貢献率"], color="#e6f2ff"),
            width='stretch',
            hide_index=True
        )
        
        st.caption("※モバイル同期の『超詳細スコア』および移行された『過去データ』を精密に集計しています。")

    # --- 4. 投手成績タブ ---
    with tab2:
        st.subheader(f"🥎 投手部門 ({sel_year} / {sel_team})")
        
        try:
            pitch_stats = db.get_pitching_stats_filtered(club_id)
            if not pitch_stats:
                st.info("投手成績データがありません。")
            else:
                df_pitch = pd.DataFrame(pitch_stats)
                
                mapping_p = {
                    'name': '氏名', '登板': '登板', '回数': '回', '防御率': '防御率',
                    '勝利': '勝', '敗戦': '敗', 'セーブ': 'S', 'ホールド': 'H',
                    '失点': '失点', '自責点': '自責', '奪三振': '三振', '四球': '四球', '死球': '死球',
                    '被安打': '被安', '被本塁打': '被本', '投球数': '球数', 'WP': 'WP',
                    '奪三振率': '奪三振率', '四球率': '四球率', '死球率': '死球率',
                    '被安率': '被安率', '被本率': '被本率', 'CS': 'CS', 'CS率': 'CS率', 'K/BB': 'K/BB'
                }
                
                available_p = [c for c in mapping_p.keys() if c in df_pitch.columns]
                disp_p = df_pitch[available_p].rename(columns=mapping_p)
                
                num_p = [c for c in disp_p.columns if c != '氏名' and c != '回']
                disp_p[num_p] = disp_p[num_p].apply(pd.to_numeric, errors='coerce').fillna(0)
                disp_p = disp_p.sort_values(by=["防御率", "勝"], ascending=[True, False])

                format_p = {col: "{:g}" for col in num_p}
                for rate_col in ["防御率", "奪三振率", "四球率", "死球率", "被安率", "被本率", "K/BB"]:
                    format_p[rate_col] = "{:.2f}"
                format_p["CS率"] = "{:.3f}"

                st.dataframe(
                    disp_p.style.format(format_p)
                    .highlight_min(subset=["防御率"], color="#e6f2ff")
                    .highlight_max(subset=["勝", "三振"], color="#fff2e6"),
                    width='stretch',
                    hide_index=True
                )
        except Exception as e:
            st.error(f"投手成績取得エラー: {e}")