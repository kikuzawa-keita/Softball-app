import streamlit as st
import database as db
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import json
import sqlite3
import numpy as np

# --- 1. 査定エンジン：定数定義 ---
GRADES = ['S', 'A', 'B', 'C', 'D', 'E', 'F', 'G']
GRADE_COLORS = {
    'S': '#ffd700', 'A': '#ff6b6b', 'B': '#ff9f43', 
    'C': '#feca57', 'D': '#54a0ff', 'E': '#48dbfb', 'F': '#c8d6e5', 'G': '#8395a7'
}

# --- 2. 査定・判定ロジック ---
def calc_rank(value, thresholds):
    """数値をS~Gのランクに変換する"""
    for i, t in enumerate(thresholds):
        if value >= t: return GRADES[i]
    return 'G'

def get_rank_color(rank):
    return GRADE_COLORS.get(rank, '#8395a7')

def self_render_rank(label, rank, val):
    """HTML文字列を生成して返す"""
    color = get_rank_color(rank)
    # バーの長さ計算 (G:10% ~ S:100%)
    width = {"S":100, "A":85, "B":70, "C":55, "D":40, "E":25, "F":15, "G":5}[rank]
    return f"""
        <div class='rank-row'>
            <span class='rank-label'>{label}</span>
            <div class='st-bar-bg'><div class='st-bar-fill' style='width: {width}%; background: {color}; box-shadow: 0 0 10px {color};'></div></div>
            <span class='rank-symbol' style='color: {color};'>{rank}</span>
        </div>
    """

def get_player_abilities(stats, detailed_logs):
    """打撃結果ログから特殊能力を抽出する"""
    abs_list = []
    avg = stats.get('avg', 0)
    hr = stats.get('hr', 0)
    rbi = stats.get('rbi', 0)
    pa = stats.get('pa', 0)
    
    # 金特
    if avg >= 0.550 and pa >= 20: abs_list.append(("安打製造機", "gold", "圧倒的な打率を誇る至高の打者"))
    if hr >= 8: abs_list.append(("アーチスト", "gold", "弾道が芸術的な放物線を描く"))
    if rbi >= 25: abs_list.append(("勝負師", "gold", "好機で神懸かった打撃を見せる"))
    # 青特
    if avg >= 0.400: abs_list.append(("アベレージヒッター", "blue", "ヒット性の打球が出やすい"))
    if stats.get('slg', 0) - avg >= 0.250: abs_list.append(("パワーヒッター", "blue", "強烈な打球を飛ばす"))
    
    # 状況判定 (pitch_countカラムがDBにある場合のみ判定)
    first_pitch_hits = 0
    for log in detailed_logs:
        if log.get('pitch_count') == 1 and "安" in log.get('result', ''):
            first_pitch_hits += 1
    if first_pitch_hits >= 3: abs_list.append(("初球○", "blue", "初球から積極的な打撃"))
    
    return abs_list

def show():
    club_id = st.session_state.get("club_id")
    if not club_id:
        st.error("セッション切れです。再ログインしてください。")
        return

    # デザインCSS
    st.markdown("""
        <style>
        .player-card {
            background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
            border-radius: 20px; padding: 25px; color: white;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5); border: 3px solid #ffd700;
            margin-bottom: 30px; position: relative; overflow: hidden;
        }
        .rank-row {
            display: flex; align-items: center; background: rgba(255,255,255,0.1);
            margin: 5px 0; border-radius: 10px; padding: 5px 15px; border-left: 5px solid #ffd700;
        }
        .rank-label { flex: 1; font-weight: 900; font-size: 1.1rem; color: #eee; }
        .rank-symbol { font-size: 1.8rem; font-weight: 900; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); width: 30px; text-align: center; }
        .st-bar-bg { background: #333; height: 12px; border-radius: 6px; flex: 2; margin: 0 15px; overflow: hidden; }
        .st-bar-fill { height: 100%; border-radius: 6px; }
        .abi-badge {
            display: inline-block; padding: 5px 12px; border-radius: 5px; font-weight: 900;
            margin: 3px; font-size: 0.85rem; box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
        }
        .gold-abi { background: linear-gradient(#f7e157, #f39c12); color: #4d2e00; border: 1px solid #fff; }
        .blue-abi { background: linear-gradient(#4facfe, #00f2fe); color: #fff; border: 1px solid #005bea; }
        </style>
    """, unsafe_allow_html=True)

    # 選手選択
    all_players = db.get_all_players(club_id)
    if not all_players:
        st.info("選手を登録してください。")
        return

    player_names = [p[1] for p in all_players]
    selected_name = st.selectbox("分析対象選手を選択", player_names)
    p_full = next(p for p in all_players if p[1] == selected_name)
    p_id = p_full[0]
    
    # データ取得
    stats = db.get_player_detailed_stats(selected_name, club_id)
    detailed_logs = db.get_raw_at_bat_logs(selected_name, club_id)
    
    # 査定計算
    r_meet = calc_rank(stats['avg'], [0.550, 0.450, 0.350, 0.280, 0.220, 0.150, 0.080])
    isop = stats['slg'] - stats['avg']
    r_power = calc_rank(isop, [0.350, 0.280, 0.200, 0.150, 0.100, 0.050, 0.020])
    r_speed = calc_rank(stats['sb'], [12, 8, 5, 3, 2, 1, 0.5])
    bb_k = stats['bb'] / (stats['so'] + 0.1)
    r_eye = calc_rank(bb_k, [1.5, 1.0, 0.8, 0.6, 0.4, 0.2, 0.1])
    abilities = get_player_abilities(stats, detailed_logs)

    # --- 3. 選手カード表示 (完全修正) ---
    # render関数で生成したHTMLをf-string内で結合し、最後に一つのst.markdownで出す
    abi_html = "".join([f"<span class='abi-badge {c}-abi' title='{desc}'>{n}</span>" for n, c, desc in abilities]) if abilities else "<span style='color:#7f8c8d;'>なし</span>"
    
    card_html = f"""
        <div class='player-card'>
            <div style='display: flex; align-items: center;'>
                <div style='flex: 1;'>
                    <span style='font-size: 1.2rem; color: #ffd700;'>背番号 {p_full[2]}</span>
                    <h1 style='margin: 0; font-size: 3rem; color: white;'>{selected_name}</h1>
                    <p style='margin: 0; color: #bdc3c7;'>{p_full[8] if len(p_full)>8 else "所属チームなし"} | {p_full[4] or "右投右打"}</p>
                </div>
                <div style='text-align: right;'>
                    <div style='font-size: 0.8rem; color: #bdc3c7;'>Pawa-Analyze ID</div>
                    <div style='font-weight: bold;'>#{p_id:04d}</div>
                </div>
            </div>
            <hr style='border: 0; border-top: 1px solid rgba(255,255,255,0.2); margin: 15px 0;'>
            <div style='display: flex; flex-wrap: wrap;'>
                <div style='flex: 1; min-width: 250px;'>
                    {self_render_rank("ミート", r_meet, stats['avg'])}
                    {self_render_rank("パワー", r_power, isop)}
                    {self_render_rank("走　力", r_speed, stats['sb'])}
                    {self_render_rank("選球眼", r_eye, bb_k)}
                </div>
                <div style='flex: 1; min-width: 250px; padding-left: 20px;'>
                    <div style='margin-bottom: 10px; font-weight: bold; color: #ffd700;'>特殊能力</div>
                    <div style='display: flex; flex-wrap: wrap;'>{abi_html}</div>
                </div>
            </div>
        </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

    # --- 4. 詳細分析タブ ---
    tab_bat, tab_pitch, tab_trend = st.tabs(["🔥 打撃・傾向分析", "🥎 投手スタッツ", "📈 成長記録・ビデオ"])

    with tab_bat:
        col_s1, col_s2 = st.columns([1, 1])
        with col_s1:
            st.markdown("#### 🚀 打撃指標")
            bb_rate = (stats['bb'] / stats['pa']) * 100 if stats['pa'] > 0 else 0
            so_rate = (stats['so'] / stats['pa']) * 100 if stats['pa'] > 0 else 0
            st.table(pd.DataFrame({
                "指標": ["wOBA(簡)", "BB%", "K%", "IsoP", "BABIP"],
                "数値": [f"{(0.7*stats['bb']+0.9*stats['h']+2.0*stats['hr'])/(stats['pa'] or 1):.3f}", f"{bb_rate:.1f}%", f"{so_rate:.1f}%", f"{isop:.3f}", f"{stats.get('babip',0):.3f}"]
            }).set_index("指標"))

        with col_s2:
            st.markdown("#### 🎯 打球方向")
            pull, center, oppo = stats.get('pull_count',0), stats.get('center_count',0), stats.get('oppo_count',0)
            if pull + center + oppo > 0:
                fig = px.pie(values=[pull, center, oppo], names=["左", "中", "右"], hole=0.5, color_discrete_sequence=['#ff4b4b', '#00d2ff', '#3dd56d'])
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=200, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else: st.caption("データ不足")

        st.markdown("#### 🕸️ コース別成績")
        zone_data = db.get_zone_hit_data(selected_name, club_id)
        fig_zone = go.Figure(data=go.Heatmap(z=zone_data, x=['外', '中', '内'], y=['高', '中', '低'], colorscale='YlOrRd', texttemplate="%{z:.3f}", showscale=False))
        fig_zone.update_layout(width=300, height=250, margin=dict(t=10, b=10))
        st.plotly_chart(fig_zone, use_container_width=True)

    with tab_pitch:
        p_stats = db.get_pitching_stats_filtered(club_id, "すべて")
        p_data = next((p for p in p_stats if p['name'] == selected_name), None)
        if p_data and float(p_data.get('total_ip', 0)) > 0:
            c1, c2, c3 = st.columns(3)
            c1.metric("防御率", f"{float(p_data['era']):.2f}")
            c2.metric("奪三振率", f"{(int(p_data['total_so'])*7)/float(p_data['total_ip']):.2f}")
            c3.metric("WHIP", f"{(float(p_data['total_h'])+float(p_data['total_bb']))/float(p_data['total_ip']):.2f}")
        else: st.info("投手記録なし")

    with tab_trend:
        history = db.get_player_batting_history(selected_name, club_id)
        if history:
            df_hist = pd.DataFrame(history)
            st.plotly_chart(px.line(df_hist, x='date', y='avg', markers=True, title="打率推移").update_yaxes(range=[0, 1.05]), use_container_width=True)
        if p_full[6]: st.video(p_full[6])
        st.info(f"指導メモ: {p_full[4] or 'なし'}")