# player_profile.py
import streamlit as st
import database as db
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import json
import sqlite3

def show():
    # 冒頭にこれを追加（セッションから安全に取得）
    role = st.session_state.get("user_role", "guest")
    username = st.session_state.get("username", "Guest")
    
    # --- CSS: デザイン調整 ---
    st.markdown("""
        <style>
        div[data-testid="stMetric"] {
            background-color: #ffffff;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            border: 1px solid #f0f2f6;
            text-align: center;
        }
        div[data-testid="stMetricLabel"] { font-size: 0.9rem; color: #6c757d; }
        div[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; color: #2c3e50; }
        .stTabs [data-baseweb="tab-list"] { gap: 24px; }
        .stats-box {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 10px;
            border-left: 5px solid #1f77b4;
        }
        </style>
    """, unsafe_allow_html=True)

    # --- データ取得 ---
    all_players = db.get_all_players()
    if not all_players:
        st.info("ℹ️ 選手データがありません。「選手名鑑」から登録してください。")
        return

    player_dict = {}
    player_names = ["(未選択)"]
    
    # --- 疑似ログイン（サイドバーの選択選手）をデフォルトにするロジック ---
    active_player_name = st.session_state.get("active_player", "(未選択)")
    default_index = 0

    for i, p in enumerate(all_players):
        p_id, p_name = p[0], p[1]
        player_names.append(p_name)
        player_dict[p_name] = {
            "id": p_id, 
            "name": p_name, 
            "birth": p[2] if len(p) > 2 else "", 
            "hometown": p[3] if len(p) > 3 else "", 
            "memo": p[4] if len(p) > 4 else "",
            "photo": p[5] if len(p) > 5 else None, 
            "video_url": p[6] if len(p) > 6 else "",
            "team": p[8] if len(p) > 8 else "未所属"
        }
        # サイドバーで選ばれている選手名と一致した場合、そのインデックスをデフォルトにする
        if p_name == active_player_name:
            default_index = i + 1

    # --- 選手選択 ---
    st.markdown("### 🔍 選手プロファイリング")
    selected_name = st.selectbox("分析対象を選択してください", player_names, index=default_index, key="profile_player_sel")

    if selected_name == "(未選択)":
        st.session_state.selected_player_id = None
        st.info("選手を選択すると詳細なプロファイリングデータが表示されます。")
        return

    player_info = player_dict[selected_name]
    p_id = player_info["id"]
    st.session_state.selected_player_id = p_id

    # --- 選手基本情報パネル (表示専用) ---
    with st.container(border=True):
        c_img, c_info, c_memo = st.columns([1, 1.5, 2])
        with c_img:
            # --- 【修正ポイント】強化された画像検索ロジック ---
            img_src = None
            search_base = selected_name.strip()
            
            try:
                # 1. まずはDBにあるパスがそのまま存在するか確認
                if player_info["photo"] and os.path.exists(player_info["photo"]):
                    img_src = player_info["photo"]
                elif os.path.exists("images"):
                    # 2. imagesフォルダ内を選手名で前方一致検索
                    all_files = os.listdir("images")
                    matches = [f for f in all_files if f.startswith(search_base) and f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
                    if matches:
                        matches.sort(reverse=True) # 最新のタイムスタンプを優先
                        img_src = os.path.join("images", matches[0])
            except:
                pass

            if img_src:
                st.image(img_src, use_container_width=True)
            else:
                st.markdown("<div style='background-color:#e9ecef; height:150px; border-radius:10px; display:flex; justify-content:center; align-items:center;'>👤</div>", unsafe_allow_html=True)
        
        with c_info:
            st.subheader(selected_name)
            st.markdown(f"**所属:** {player_info['team']}")
            st.markdown(f"**出身:** {player_info['hometown']}")
            st.markdown(f"**誕生日:** {player_info['birth']}")
        with c_memo:
            st.markdown("**📌 監督・コーチメモ**")
            st.info(player_info['memo'] if player_info['memo'] else "メモなし")

    # --- データ取得と安全な計算 ---
    d_stats_raw = db.get_player_detailed_stats(selected_name)
    default_stats = {"avg":0.0, "obp":0.0, "slg":0.0, "ops":0.0, "pa":0, "ab":0, "h":0, "d2":0, "d3":0, "hr":0, "rbi":0, "sb":0, "bb":0, "so":0, "dp":0, "bb_k":0.0, "sf":0}
    d_stats = {**default_stats, **d_stats_raw} if isinstance(d_stats_raw, dict) else default_stats

    # セイバーメトリクス追加計算
    iso_p = d_stats.get('slg', 0.0) - d_stats.get('avg', 0.0)
    denom_babip = (d_stats.get('ab', 0) - d_stats.get('so', 0) - d_stats.get('hr', 0) + d_stats.get('sf', 0))
    babip = (d_stats.get('h', 0) - d_stats.get('hr', 0)) / denom_babip if denom_babip > 0 else 0.0

    p_stats_all = db.get_pitching_stats_filtered("すべて")
    p_stats = next((p for p in p_stats_all if p.get('name') == selected_name), None) if p_stats_all else None
    
    # 投手データの有無判定
    has_pitching = False
    if p_stats:
        p_stats['total_ip'] = float(p_stats.get('total_ip', 0.0))
        p_stats['era'] = float(p_stats.get('era', 0.0))
        
        if 'k_bb' not in p_stats:
            so = float(p_stats.get('total_so', 0))
            bb = float(p_stats.get('total_bb', 0))
            p_stats['k_bb'] = so / bb if bb > 0 else (so if so > 0 else 0.0)
        
        if 'k_9' not in p_stats:
            so = float(p_stats.get('total_so', 0))
            ip = p_stats['total_ip']
            p_stats['k_9'] = (so * 7) / ip if ip > 0 else 0.0

        if 'whip' not in p_stats:
            h = float(p_stats.get('total_hits', 0))
            bb = float(p_stats.get('total_bb', 0))
            ip = p_stats['total_ip']
            p_stats['whip'] = (h + bb) / ip if ip > 0 else 0.0

        if p_stats['total_ip'] > 0:
            has_pitching = True

    # --- メインタブ ---
    tab1, tab2, tab3, tab4 = st.tabs(["📋 総合プロフ", "🏏 打撃・セイバー", "🥎 投手分析", "📈 傾向・ビデオ"])

    with tab1:
        st.markdown("#### 🏆 主要指標 (Key Metrics)")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("打率 (AVG)", f"{d_stats.get('avg', 0.0):.3f}")
        c2.metric("OPS", f"{d_stats.get('ops', 0.0):.3f}")
        c3.metric("IsoP (長打力)", f"{iso_p:.3f}")
        if has_pitching:
            c4.metric("防御率 (ERA)", f"{p_stats.get('era', 0.0):.2f}")
        else:
            c4.metric("出塁率 (OBP)", f"{d_stats.get('obp', 0.0):.3f}")

        st.divider()
        col_radar, col_dist = st.columns([1, 1])
        with col_radar:
            st.subheader("🛡️ 選手能力レーダー")
            r_slg = min(5, (d_stats.get('slg', 0.0) / 0.6) * 5)
            r_avg = min(5, (d_stats.get('avg', 0.0) / 0.4) * 5)
            r_eye = min(5, (d_stats.get('bb_k', 0.0) / 1.2) * 5)
            r_spd = min(5, (d_stats.get('sb', 0) / 5) * 5)
            r_pwr = min(5, (iso_p / 0.3) * 5)
            
            fig_radar = go.Figure(data=go.Scatterpolar(
                r=[r_slg, r_avg, r_eye, r_spd, r_pwr],
                theta=['長打率', '巧打力', '選球眼', '走力', 'パワー'],
                fill='toself', fillcolor='rgba(31, 119, 180, 0.4)', line_color='#1f77b4'
            ))
            fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5])), showlegend=False, height=350, margin=dict(t=30, b=30, l=30, r=30))
            st.plotly_chart(fig_radar, use_container_width=True)

        with col_dist:
            st.subheader("🎯 打球方向分布")
            try:
                with sqlite3.connect('softball.db') as conn:
                    rows = conn.execute("SELECT innings FROM scorebook_batting WHERE player_name = ?", (selected_name,)).fetchall()
                dir_list = []
                for r in rows:
                    if r[0]:
                        for item in json.loads(r[0]):
                            res = item.get('res', '')
                            if res and res != "---":
                                if "左" in res: dir_list.append("Pull (左)")
                                elif "中" in res: dir_list.append("Center (中)")
                                elif "右" in res: dir_list.append("Opposite (右)")
                                else: dir_list.append("Infield (内野)")
                
                if dir_list:
                    df_dir = pd.DataFrame({"方向": dir_list})
                    fig_dir = px.pie(df_dir, names="方向", hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_dir.update_layout(height=350, margin=dict(t=30, b=30, l=30, r=30))
                    st.plotly_chart(fig_dir, use_container_width=True)
                else:
                    st.info("打球方向データがありません")
            except: st.error("方向分析エラー")

    with tab2:
        st.subheader("🏏 打撃詳細統計 & セイバーメトリクス")
        st.markdown("""<div class='stats-box'><strong>プロ視点メモ:</strong> BABIPが平均(.300)より著しく高い場合は運が良い可能性があり、IsoPが.200を超えると優秀な長打者と評価されます。</div>""", unsafe_allow_html=True)
        
        c_a, c_b = st.columns(2)
        with c_a:
            st.write("**【基本統計】**")
            st.table(pd.DataFrame({
                "指標": ["打席 (PA)", "打数 (AB)", "安打 (H)", "二塁打", "三塁打", "本塁打", "打点 (RBI)", "三振 (SO)", "四球 (BB)"],
                "数値": [d_stats.get(k, 0) for k in ['pa', 'ab', 'h', 'd2', 'd3', 'hr', 'rbi', 'so', 'bb']]
            }))
        with c_b:
            st.write("**【高度指標】**")
            st.table(pd.DataFrame({
                "指標": ["出塁率 (OBP)", "長打率 (SLG)", "OPS", "純粋長打力 (IsoP)", "BABIP", "選球眼 (BB/K)"],
                "数値": [f"{d_stats.get('obp', 0.0):.3f}", f"{d_stats.get('slg', 0.0):.3f}", f"{d_stats.get('ops', 0.0):.3f}", f"{iso_p:.3f}", f"{babip:.3f}", f"{d_stats.get('bb_k', 0.0):.2f}"]
            }))

    with tab3:
        if has_pitching:
            st.subheader("🥎 投手詳細プロファイリング")
            kp = st.columns(4)
            kp[0].metric("防御率 (ERA)", f"{p_stats.get('era', 0.0):.2f}")
            kp[1].metric("K/BB (制球力)", f"{p_stats.get('k_bb', 0.0):.2f}")
            kp[2].metric("奪三振率 (K/7)", f"{p_stats.get('k_9', 0.0):.2f}")
            kp[3].metric("WHIP", f"{p_stats.get('whip', 0.0):.2f}")
            
            st.divider()
            st.write("**【登板成績詳細】**")
            st.dataframe(pd.DataFrame([p_stats]), use_container_width=True)
        else:
            st.markdown("<div style='text-align: center; padding: 100px; color: #ccc;'>投手データが蓄積されていません</div>", unsafe_allow_html=True)

    with tab4:
        st.subheader("📈 成績推移 & スカウティングビデオ")
        history = db.get_player_batting_history(selected_name)
        if history:
            df_hist = pd.DataFrame(history)
            df_hist['試合'] = range(1, len(df_hist)+1)
            fig_line = px.line(df_hist, x='試合', y='打率', markers=True, title="直近の打率推移")
            st.plotly_chart(fig_line, use_container_width=True)
        
        if player_info["video_url"]:
            st.divider()
            st.video(player_info["video_url"])
        else:
            st.info("ビデオが登録されていません")
