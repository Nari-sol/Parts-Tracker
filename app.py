import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import json
import db

# データベースの初期化
db.init_db()

# アプリ設定
st.set_page_config(
    page_title="Parts Tracker",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# プレミアムなスタイリングを適用するカスタムCSS
st.markdown("""
<style>
    /* 全般的なフォントと余白の調整 */
    html, body, [class*="ViewCreator"] {
        font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
    }
    
    /* ヘッダースタイル（文字色はテーマに自動連動） */
    .header-style {
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
        font-size: 2.2rem;
        margin-bottom: 0.5rem;
    }
    
    /* カード調コンテナの背景（ライト/ダークテーマ両対応） */
    div.stButton > button:first-child {
        background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        font-weight: 600;
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2);
        transition: all 0.2s ease;
    }
    div.stButton > button:first-child:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 16px rgba(99, 102, 241, 0.4);
    }
    
    /* メトリック値の強調表示 */
    div[data-testid="stMetricValue"] {
        font-size: 2.5rem;
        font-weight: 700;
        color: #6366f1;
    }
    
    /* シミュレーション結果表示の巨大ハイライト */
    .result-box {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(79, 70, 229, 0.1) 100%);
        border: 2px solid #6366f1;
        border-radius: 12px;
        padding: 24px;
        text-align: center;
        margin: 20px 0;
        box-shadow: 0 8px 24px rgba(99, 102, 241, 0.1);
    }
    .result-val {
        font-size: 3.5rem;
        font-weight: 800;
        color: #4f46e5;
        margin: 10px 0;
    }
    .result-title {
        font-size: 1rem;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        color: #64748b;
    }
    
    /* タイムラインの箇条書き調整 */
    .timeline-item {
        border-left: 3px solid #6366f1;
        padding-left: 15px;
        margin-bottom: 15px;
        position: relative;
    }
</style>
""", unsafe_allow_html=True)

# サイドバーによる画面遷移
st.sidebar.markdown('<div style="font-size: 1.5rem; font-weight: 700; margin-bottom: 20px;">📦 Parts Tracker</div>', unsafe_allow_html=True)
menu = st.sidebar.radio(
    "機能メニュー",
    ["📊 期間実績の抽出", "🛠️ 発注シミュレーション", "📂 データ管理"],
    index=0
)

# 共通: ユニーク品番リストの取得と加工
parts_dict = db.get_unique_parts()
part_options = []
part_name_map = {}
for p in parts_dict:
    label = f"{p['part_number']} ({p['part_name']})" if p['part_name'] else p['part_number']
    part_options.append(label)
    part_name_map[label] = p['part_number']

# ==============================================================================
# SCREEN 1: 期間実績の抽出
# ==============================================================================
if menu == "📊 期間実績の抽出":
    st.title("📊 期間実績の抽出")
    st.markdown('<p style="color: gray; font-size: 0.8rem;">特定の品番の過去の実績データを抽出・確認します。</p>', unsafe_allow_html=True)
    st.markdown("---")

    if not part_options:
        st.info("💡 まだデータベースに実績データが登録されていません。「⚙️ データ管理」メニューから実績Excelをアップロードしてください。")
    else:
        # 検索条件コントロール
        col_search_1, col_search_2 = st.columns([1, 2])
        
        with col_search_1:
            st.markdown("### 🔍 検索条件")
            
            # 品番選択モード切り替え
            search_mode = st.radio(
                "検索モード",
                ["単一品番モード", "複数品番比較モード"],
                horizontal=True,
                key="search_mode"
            )
            
            # 品番入力UIの切り替え
            if search_mode == "単一品番モード":
                selected_part = st.text_input(
                    "対象の品番を入力", 
                    placeholder="品番を入力またはコピペしてください",
                    key="input_single_part"
                )
                query_part_param = selected_part.strip()
            else:
                selected_parts_labels = st.multiselect(
                    "対象の品番を複数選択", 
                    part_options, 
                    default=[],
                    key="select_multi_parts"
                )
                parts_multiselect = [part_name_map[lbl] for lbl in selected_parts_labels]
                
                # Excel等からコピペ可能なテキストエリア
                copied_parts_text = st.text_area(
                    "Excelから品番をコピペ（改行区切りで入力）",
                    height=100,
                    placeholder="例:\n000000004039A\n000000006513",
                    key="copied_parts_text"
                )
                
                # 改行コードで分割し、前後の不要な空白をクレンジングして空行を除外
                parts_copied = []
                if copied_parts_text:
                    parts_copied = [p.strip() for p in copied_parts_text.split("\n") if p.strip()]
                    
                # 選択値と貼り付け値を統合（重複を排除して順序維持）
                query_part_param = list(dict.fromkeys(parts_multiselect + parts_copied))
                
            # 集計期間の選択肢をデータベースから取得（昇順）
            ym_options = sorted(db.get_unique_months())
            
            # デフォルト値の設定
            start_index = 0
            end_index = len(ym_options) - 1 if ym_options else 0
            
            if ym_options:
                default_start = "2025-01" if "2025-01" in ym_options else ym_options[0]
                default_end = "2026-12" if "2026-12" in ym_options else ym_options[-1]
                start_index = ym_options.index(default_start)
                end_index = ym_options.index(default_end)
            
            start_ym = st.selectbox("集計開始年月", ym_options, index=start_index, key="start_ym")
            end_ym = st.selectbox("集計終了年月", ym_options, index=end_index, key="end_ym")
            
            submitted = st.button("実績を抽出する", key="btn_execute_search")
        
        with col_search_2:
            # 検索の実行
            if submitted:
                if search_mode == "単一品番モード" and not query_part_param:
                    st.warning("👉 品番を入力してください。")
                    st.session_state.pop('search_df', None)
                elif search_mode == "複数品番比較モード" and not query_part_param:
                    st.error("⚠️ 品番が選択または入力されていません。")
                    st.session_state.pop('search_df', None)
                elif start_ym > end_ym:
                    st.error("⚠️ 開始年月は終了年月より前の月を指定してください。")
                else:
                    # 単一品番モードの場合、DB内存在チェック
                    if search_mode == "単一品番モード":
                        if not db.has_part(query_part_param):
                            st.error(f"❌ 該当する品番「{query_part_param}」が見つかりません。登録されている品番かご確認ください。")
                            st.session_state.pop('search_df', None)
                        else:
                            df = db.query_records(query_part_param, start_ym, end_ym)
                            st.session_state['search_df'] = df
                            st.session_state['last_searched_part'] = query_part_param
                            st.session_state['last_search_mode'] = search_mode
                            st.session_state['last_start_ym'] = start_ym
                            st.session_state['last_end_ym'] = end_ym
                    else:
                        # 複数品番比較モード
                        df = db.query_records(query_part_param, start_ym, end_ym)
                        st.session_state['search_df'] = df
                        st.session_state['last_searched_part'] = query_part_param
                        st.session_state['last_search_mode'] = search_mode
                        st.session_state['last_start_ym'] = start_ym
                        st.session_state['last_end_ym'] = end_ym

            # 結果表示
            if 'search_df' not in st.session_state or st.session_state.get('last_search_mode') != search_mode:
                st.info("💡 検索条件を入力し、「実績を抽出する」をクリックしてください。")
                
            elif 'search_df' in st.session_state and st.session_state.get('last_search_mode') == search_mode:
                df = st.session_state['search_df']
                last_param = st.session_state.get('last_searched_part')
                
                # 入力パラメータとセッションの状態が一致している場合のみ表示
                if df.empty:
                    st.warning("指定された期間・品番に合致するデータが見つかりませんでした。")
                else:
                    if search_mode == "単一品番モード":
                        # --- 単一品番モードの表示レイアウト ---
                        part_number = last_param
                        part_name = df['part_name'].iloc[0] if not df['part_name'].empty and df['part_name'].iloc[0] else "品名未登録"
                        
                        st.markdown(f"### 📊 抽出結果: {part_number} ({part_name})")
                        
                        # KPI指標カード
                        total_qty = df['quantity'].sum()
                        avg_qty = df['quantity'].mean()
                        months_count = len(df)
                        
                        col_kpi_1, col_kpi_2, col_kpi_3 = st.columns(3)
                        col_kpi_1.metric("期間累計実績数量", f"{int(total_qty):,}")
                        col_kpi_2.metric("期間月平均実績", f"{avg_qty:.1f}")
                        col_kpi_3.metric("該当データ月数", f"{months_count} ヶ月")
                        
                        # 推移グラフ
                        fig = px.line(
                            df, 
                            x='date', 
                            y='quantity', 
                            title="月別実績数量の推移",
                            labels={'date': '年月', 'quantity': '数量'},
                            markers=True,
                            color_discrete_sequence=['#6366f1']
                        )
                        fig.update_layout(
                            font_family="Plus Jakarta Sans",
                            plot_bgcolor="rgba(0,0,0,0)",
                            yaxis=dict(gridcolor="rgba(0,0,0,0.05)", title="実績数量"),
                            xaxis=dict(gridcolor="rgba(0,0,0,0.05)", title="年月")
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # 詳細データテーブル
                        with st.expander("📝 月別詳細データ一覧を表示"):
                            display_df = df.copy()
                            display_df.columns = ["年月", "品番", "品名", "実績数量"]
                            st.dataframe(display_df.set_index("年月"), use_container_width=True)
                    
                    else:
                        # --- 複数品番比較モードの表示レイアウト ---
                        st.markdown("### 📊 抽出結果: 複数品番の実績比較")
                        
                        # 1. サマリーテーブル比較の作成
                        summary_data = []
                        for p_num in df['part_number'].unique():
                            p_df = df[df['part_number'] == p_num]
                            p_name = p_df['part_name'].iloc[0] if not p_df['part_name'].empty and p_df['part_name'].iloc[0] else "品名未登録"
                            summary_data.append({
                                "品番": p_num,
                                "品名": p_name,
                                "期間累計実績": int(p_df['quantity'].sum()),
                                "月平均実績": round(p_df['quantity'].mean(), 1),
                                "データ月数": len(p_df)
                            })
                            
                        df_summary = pd.DataFrame(summary_data)
                        st.markdown("#### 📋 品番ごとの実績サマリー比較")
                        st.dataframe(df_summary.set_index("品番"), use_container_width=True)
                        
                        # 2. 複数系列の折れ線グラフ
                        fig = px.line(
                            df,
                            x='date',
                            y='quantity',
                            color='part_number',
                            title="月別実績数量の比較推移",
                            labels={'date': '年月', 'quantity': '数量', 'part_number': '品番'},
                            markers=True
                        )
                        fig.update_layout(
                            font_family="Plus Jakarta Sans",
                            plot_bgcolor="rgba(0,0,0,0)",
                            yaxis=dict(gridcolor="rgba(0,0,0,0.05)", title="実績数量"),
                            xaxis=dict(gridcolor="rgba(0,0,0,0.05)", title="年月")
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # 3. 年月×品番のピボットテーブル
                        st.markdown("#### 📝 横並び比較データ（年月 × 品番）")
                        pivot_df = df.pivot_table(
                            index='date', 
                            columns='part_number', 
                            values='quantity', 
                            aggfunc='sum'
                        ).fillna(0.0)
                        st.dataframe(pivot_df, use_container_width=True)

# ==============================================================================
# SCREEN 2: 適正発注数量のシミュレーション
# ==============================================================================
elif menu == "🛠️ 発注シミュレーション":
    st.title("🛠️ 発注シミュレーション")
    st.markdown('<p style="color: gray; font-size: 0.8rem;">過去の実績と条件に基づき、適正な発注数量を算出します。</p>', unsafe_allow_html=True)
    st.markdown("---")

    if not part_options:
        st.info("💡 まだデータベースに実績データが登録されていません。「⚙️ データ管理」メニューから実績CSVをアップロードしてください。")
    else:
        # 入力コントロール
        col_sim_1, col_sim_2 = st.columns([2, 3])
        
        with col_sim_1:
            st.markdown("### 🛠️ シミュレーション条件")
            
            # 品番選択モード切り替え
            sim_mode = st.radio(
                "品番選択モード",
                ["単一品番モード", "複数品番比較モード"],
                horizontal=True,
                key="sim_mode"
            )
            
            # 品番入力UIの切り替え
            if sim_mode == "単一品番モード":
                selected_part = st.text_input(
                    "対象の品番を入力", 
                    placeholder="品番を入力またはコピペしてください",
                    key="sim_single_part"
                )
                part_numbers_to_calc = [selected_part.strip()] if selected_part.strip() else []
            else:
                copied_parts_text = st.text_area(
                    "Excelから品番をコピペ（改行区切りで入力）",
                    height=120,
                    placeholder="例:\n000000004039A\n000000006513",
                    key="sim_copied_parts_text"
                )
                # 改行で分割し、前後の不要な空白をクレンジングして空行を除外
                part_numbers_to_calc = []
                if copied_parts_text:
                    part_numbers_to_calc = [p.strip() for p in copied_parts_text.split("\n") if p.strip()]
                    
            # 集計期間の選択肢をデータベースから取得（昇順）
            ym_options = sorted(db.get_unique_months())
            
            # デフォルト値の設定
            order_index = 0
            delivery_index = 0
            
            if ym_options:
                # 発注時期は直近の月（最後から2番目）
                order_index = max(0, len(ym_options) - 2)
                # 納期は直近の月（最後の月）
                delivery_index = len(ym_options) - 1
            
            order_ym = st.selectbox("発注時期 (年月)", ym_options, index=order_index, key="sim_order_ym")
            delivery_ym_choice = st.selectbox("納期 (納入年月)", ym_options, index=delivery_index, key="sim_delivery_ym")
            
            cover_months = st.selectbox(
                "必要期間 (何か月分の数量が必要か)", 
                [1, 2, 3, 4, 5, 6, 12], 
                index=2, # デフォルト3ヶ月分
                key="sim_cover_months"
            )
            
            logic = st.selectbox(
                "予測計算ロジック",
                [
                    "過去12ヶ月の単純平均",
                    "過去3ヶ月の単純平均",
                    "過去3ヶ月＋当月の単純平均",
                    "前年同期の実績 (季節性を考慮)",
                    "過去6ヶ月の最大実績"
                ],
                key="sim_logic"
            )
            
            safety_factor = st.selectbox(
                "安全バッファ (安全係数)",
                ["なし (1.0倍)", "10%追加 (1.1倍)", "20%追加 (1.2倍)", "30%追加 (1.3倍)", "50%追加 (1.5倍)"],
                index=2, # デフォルト1.2倍
                key="sim_safety_factor"
            )
            
            submitted = st.button("シミュレーションを実行", key="btn_run_sim")

        with col_sim_2:
            if submitted:
                if not part_numbers_to_calc:
                    st.error("⚠️ 品番が入力または貼り付けされていません。")
                elif delivery_ym_choice < order_ym:
                    st.error("⚠️ 納期（納入年月）は、発注時期より後の年月を指定してください。")
                else:
                    # カバー対象月リストの構築
                    target_months = []
                    d_year, d_month = map(int, delivery_ym_choice.split('-'))
                    for i in range(cover_months):
                        m_idx = d_month - 1 + i
                        y_add = m_idx // 12
                        m_real = (m_idx % 12) + 1
                        target_months.append(f"{d_year + y_add}-{m_real:02d}")
                        
                    # 安全係数の数値抽出
                    factor_val = float(safety_factor.split(" (")[1].replace("倍)", "").replace("1.0", "1.0").replace("1.1", "1.1").replace("1.2", "1.2").replace("1.3", "1.3").replace("1.5", "1.5"))

                    # 一括シミュレーション計算
                    results_list = []
                    error_flag = False
                    
                    for p_num in part_numbers_to_calc:
                        # 1. 存在チェック
                        if not db.has_part(p_num):
                            if sim_mode == "単一品番モード":
                                st.error(f"❌ 該当する品番「{p_num}」が見つかりません。登録されている品番かご確認ください。")
                                error_flag = True
                                break
                            else:
                                results_list.append({
                                    'part_number': p_num,
                                    'part_name': '未登録',
                                    'raw_sum': 0,
                                    'buffer_qty': 0,
                                    'final_qty': 0,
                                    'predictions': [],
                                    'explanation': '該当する品番が見つかりません。',
                                    'status': '品番未登録'
                                })
                                continue
                                
                        # 2. 実績データの取得
                        df_part = db.query_records(p_num)
                        if df_part.empty:
                            if sim_mode == "単一品番モード":
                                st.error(f"❌ 品番「{p_num}」の実績データがありません。")
                                error_flag = True
                                break
                            else:
                                results_list.append({
                                    'part_number': p_num,
                                    'part_name': '実績なし',
                                    'raw_sum': 0,
                                    'buffer_qty': 0,
                                    'final_qty': 0,
                                    'predictions': [],
                                    'explanation': '実績データがありません。',
                                    'status': '実績データなし'
                                })
                                continue
                                
                        part_name = df_part['part_name'].iloc[0] if not df_part['part_name'].empty and df_part['part_name'].iloc[0] else "品名未登録"
                        
                        # 過去データの抽出
                        if logic == "過去3ヶ月＋当月の単純平均":
                            calc_df = df_part[df_part['date'] <= order_ym]
                        else:
                            calc_df = df_part[df_part['date'] < order_ym]
                            
                        if calc_df.empty:
                            calc_df = df_part
                            
                        # 予測計算
                        predictions = []
                        explanation = ""
                        if logic in ["過去12ヶ月の単純平均", "過去3ヶ月の単純平均", "過去3ヶ月＋当月の単純平均"]:
                            if logic == "過去12ヶ月の単純平均":
                                limit = 12
                            elif logic == "過去3ヶ月の単純平均":
                                limit = 3
                            else: # "過去3ヶ月＋当月の単純平均"
                                limit = 4
                                
                            recent_df = calc_df.sort_values('date', ascending=False).head(limit)
                            avg_qty = recent_df['quantity'].mean() if not recent_df.empty else 0.0
                            avg_qty = round(avg_qty)
                            
                            if logic == "過去3ヶ月＋当月の単純平均":
                                explanation = f"過去3ヶ月＋当月の単純平均実績（直近{len(recent_df)}ヶ月の平均: {avg_qty:,} 個/月）を需要予測ベースに設定。"
                                basis_label = f"直近{len(recent_df)}ヶ月平均 (当月含む): {avg_qty:,}"
                            else:
                                explanation = f"過去{len(recent_df)}ヶ月の単純平均実績（{avg_qty:,} 個/月）を需要予測ベースに設定。"
                                basis_label = f"過去{len(recent_df)}ヶ月平均: {avg_qty:,}"
                                
                            for m in target_months:
                                predictions.append({
                                    'month': m,
                                    'predicted': avg_qty,
                                    'basis': basis_label
                                })
                        elif logic == "前年同期の実績 (季節性を考慮)":
                            explanation = f"前年同月の実績値を各月の予測需要として採用。"
                            for m in target_months:
                                y, mon = map(int, m.split('-'))
                                prev_year_ym = f"{y - 1}-{mon:02d}"
                                matched = calc_df[calc_df['date'] == prev_year_ym]
                                if not matched.empty:
                                    qty = int(matched['quantity'].iloc[0])
                                    predictions.append({
                                        'month': m,
                                        'predicted': qty,
                                        'basis': f"前年同月 ({prev_year_ym}) 実績: {qty:,}"
                                    })
                                else:
                                    overall_avg = int(calc_df['quantity'].mean()) if not calc_df.empty else 0
                                    predictions.append({
                                        'month': m,
                                        'predicted': overall_avg,
                                        'basis': f"前年同月データなし -> 過去全体平均: {overall_avg:,}"
                                    })
                        elif logic == "過去6ヶ月の最大実績":
                            recent_df = calc_df.sort_values('date', ascending=False).head(6)
                            max_qty = recent_df['quantity'].max() if not recent_df.empty else 0.0
                            max_qty = int(max_qty)
                            explanation = f"直近{len(recent_df)}ヶ月の単月最大実績（{max_qty:,} 個）を需要予測ベースに設定。"
                            for m in target_months:
                                predictions.append({
                                    'month': m,
                                    'predicted': max_qty,
                                    'basis': f"直近最大値: {max_qty:,}"
                                })

                        # 総和と安全係数の適用
                        raw_sum = sum(p['predicted'] for p in predictions)
                        final_order_qty = round(raw_sum * factor_val)
                        buffer_qty = final_order_qty - raw_sum

                        # 正常系データの蓄積
                        results_list.append({
                            'part_number': p_num,
                            'part_name': part_name,
                            'raw_sum': raw_sum,
                            'buffer_qty': buffer_qty,
                            'final_qty': final_order_qty,
                            'predictions': predictions,
                            'explanation': explanation,
                            'status': '計算成功'
                        })

                    # ループ終了後の描画処理
                    if not error_flag:
                        st.markdown("### 🏆 シミュレーション結果")
                        
                        if sim_mode == "単一品番モード":
                            if results_list:
                                res = results_list[0]
                                if res['status'] == '計算成功':
                                    part_label = f"{res['part_number']} ({res['part_name']})"
                                    st.markdown(f"""
                                    <div class="result-box">
                                        <div class="result-title">推奨発注数量 ({part_label})</div>
                                        <div class="result-val">{res['final_qty']:,} 個</div>
                                        <div style="font-size: 0.85rem; color: #64748b;">
                                            納品対象: {target_months[0]} ～ {target_months[-1]} ({cover_months}ヶ月間)
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    
                                    st.markdown("#### 📝 計算根拠・内訳")
                                    st.write(res['explanation'])
                                    
                                    for p in res['predictions']:
                                        y, mon = p['month'].split('-')
                                        jp_month = f"{y}年{int(mon)}月"
                                        st.markdown(f"""
                                        <div class="timeline-item">
                                            <strong>{jp_month} の予測需要: {int(p['predicted']):,} 個</strong><br>
                                            <span style="font-size: 0.85rem; color: #64748b;">({p['basis']})</span>
                                        </div>
                                        """, unsafe_allow_html=True)
                                        
                                    if factor_val > 1.0:
                                        st.markdown(f"""
                                        <div class="timeline-item" style="border-left-color: #f59e0b;">
                                            <strong>安全バッファ ({int((factor_val - 1)*100)}% 加算): +{res['buffer_qty']:,} 個</strong><br>
                                            <span style="font-size: 0.85rem; color: #64748b;">(安全係数 {factor_val} を適用)</span>
                                        </div>
                                        """, unsafe_allow_html=True)
                                        
                                    st.success(f"計算結果: 予測ベース合計 {res['raw_sum']:,} 個 × 安全係数 {factor_val} ＝ 推奨発注数量 {res['final_qty']:,} 個")
                        else:
                            # 複数品番比較モード
                            if results_list:
                                comparison_data = []
                                for res in results_list:
                                    comparison_data.append({
                                        "品番": res['part_number'],
                                        "品名": res['part_name'],
                                        "状態": res['status'],
                                        "予測計算ロジック": logic if res['status'] == '計算成功' else '-',
                                        "予測ベース合計": res['raw_sum'],
                                        "安全バッファ": res['buffer_qty'],
                                        "推奨発注数量": res['final_qty']
                                    })
                                df_compare = pd.DataFrame(comparison_data)
                                st.dataframe(
                                    df_compare.set_index("品番"),
                                    use_container_width=True,
                                    column_config={
                                        "予測ベース合計": st.column_config.NumberColumn(format="%d 個"),
                                        "安全バッファ": st.column_config.NumberColumn(format="+%d 個"),
                                        "推奨発注数量": st.column_config.NumberColumn(format="%d 個"),
                                    }
                                )

# ==============================================================================
# SCREEN 3: データ管理
# ==============================================================================
elif menu == "📂 データ管理":
    st.title("📂 データ管理")
    st.markdown('<p style="color: gray; font-size: 0.8rem;">実績データ(Excel)のアップロードと、データベースのバックアップ・リセットを行います。</p>', unsafe_allow_html=True)
    st.markdown("---")

    col_db_1, col_db_2 = st.columns(2)
    
    with col_db_1:
        st.markdown("### 📤 実績データのアップロード")
        uploaded_file = st.file_uploader("Excelファイル (.xlsx) をアップロードしてください", type=["xlsx"])
        
        if uploaded_file is not None:
            try:
                # 1. 対象月の抽出と西暦変換 (A2セル / インデックス [1, 0])
                # 最初の3行のみをヘッダーなしで読み込む
                df_meta = pd.read_excel(uploaded_file, header=None, nrows=3)
                
                # A2セルの値を取得
                if df_meta.shape[0] < 2 or df_meta.shape[1] < 1:
                    st.error("❌ Excelファイルのデータ構造が足りません。A2セル（2行目の1列目）に対象期間が記載されているか確認してください。")
                else:
                    a2_value = str(df_meta.iloc[1, 0]).strip()
                    
                    # 正規表現で「令和〇年」の数字と「〇月」の数字を抽出
                    import re
                    match = re.search(r'令和\s*(\d+)\s*年\s*(\d+)\s*月', a2_value)
                    if not match:
                        match = re.search(r'令和(\d+)年(\d+)月', a2_value)
                        
                    if not match:
                        st.error(f"❌ A2セル（表示値: '{a2_value}'）から「令和〇年〇月」を検出できませんでした。フォーマットを確認してください。")
                    else:
                        reiwa_year = int(match.group(1))
                        month = int(match.group(2))
                        
                        # 令和から西暦へ変換 (令和年数 + 2018)
                        seireki_year = reiwa_year + 2018
                        target_month = f"{seireki_year}-{month:02d}"
                        
                        st.success(f"📅 対象期間を検出しました: **{target_month}** ({a2_value})")
                        
                        # 2. 実データの読み込み (上部4行をスキップし、5行目をヘッダーとする)
                        # ※アップロードファイルのポインタを先頭に戻す必要は pandas.read_excel では通常自動処理されますが、
                        # st.file_uploaderの挙動を考慮し、再度ファイルを読み込みます。
                        df_data = pd.read_excel(uploaded_file, skiprows=4)
                        
                        # 3. データのクレンジングと集計
                        if "コード" not in df_data.columns or "出庫数量" not in df_data.columns:
                            st.error("❌ Excelファイルに「コード」列または「出庫数量」列が見つかりません。5行目の項目名を確認してください。")
                            st.write("検出された項目名:", list(df_data.columns))
                        else:
                            # 欠損値の除去（コードがない行は除外）
                            df_clean = df_data.dropna(subset=["コード"])
                            
                            # コード列のハイフン分割と品番上書き
                            df_clean["品番"] = df_clean["コード"].astype(str).apply(lambda x: x.split("-")[0].strip())
                            
                            # 出庫数量を数値化
                            df_clean["出庫数量"] = pd.to_numeric(df_clean["出庫数量"], errors='coerce').fillna(0.0)
                            
                            # 品名列があれば抽出
                            has_name = "品名" in df_clean.columns
                            if has_name:
                                df_clean["品名"] = df_clean["品名"].astype(str).str.strip()
                                # 品番ごとに最初の品名を取得
                                name_mapping = df_clean.groupby("品番")["品名"].first().reset_index()
                            
                            # 品番ごとにグループ化して出庫数量の合計を計算
                            df_grouped = df_clean.groupby("品番")["出庫数量"].sum().reset_index()
                            
                            if has_name:
                                df_grouped = pd.merge(df_grouped, name_mapping, on="品番", how="left")
                            else:
                                df_grouped["品名"] = ""
                                
                            # プレビュー表示
                            st.write("📋 読み込み・集計結果プレビュー:")
                            preview_display = df_grouped.copy()
                            preview_display.columns = ["品番", "集計出庫数量", "品名"]
                            st.dataframe(preview_display, use_container_width=True)
                            
                            # データベース登録フォーム
                            with st.form("import_form"):
                                st.write(f"上記 {len(df_grouped)} 品番の集計データをデータベースの **{target_month}** 分として登録します。")
                                st.warning(f"⚠️ 登録を実行すると、既に登録されている **{target_month}** のデータはすべて消去され、今回のデータに置き換わります。")
                                
                                import_submit = st.form_submit_button("データベースへ登録・上書き")
                                
                                if import_submit:
                                    # 4. データベースへの統合と保存
                                    # 既存の対象月データを一括削除 (完全な置き換え上書き)
                                    deleted = db.delete_records_by_month(target_month)
                                    
                                    # 保存用レコードリストの作成
                                    records_to_save = []
                                    for _, row in df_grouped.iterrows():
                                        records_to_save.append({
                                            'part_number': row['品番'],
                                            'date': target_month,
                                            'quantity': row['出庫数量'],
                                            'part_name': row['品名']
                                        })
                                        
                                    success, skips = db.save_records(records_to_save)
                                    st.success(f"🎉 データベースに登録しました！ (削除された古いレコード: {deleted}件 / 新規登録: {success}件)")
                                    st.balloons()
                                    st.rerun()
                                    
            except Exception as e:
                st.error(f"❌ ファイルのパースまたは処理中にエラーが発生しました: {e}")
                
    with col_db_2:
        st.markdown("### 🗄️ データベースステータス")
        
        stats = db.get_db_stats()
        
        col_stat_1, col_stat_2 = st.columns(2)
        col_stat_1.metric("蓄積レコード数", f"{stats['total_records']:,} 件")
        col_stat_2.metric("登録品番数", f"{stats['total_parts']:,} 品番")
        
        st.markdown("---")
        st.markdown("### 💾 バックアップと復元 (JSON)")
        
        # バックアップエクスポート
        conn = db.get_connection()
        df_all = pd.read_sql_query("SELECT part_number, date, quantity, part_name FROM actual_records", conn)
        conn.close()
        
        if not df_all.empty:
            json_str = df_all.to_json(orient='records', force_ascii=False, indent=2)
            st.download_button(
                label="📥 データベースをエクスポートする",
                data=json_str,
                file_name=f"parts_tracker_backup_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json"
            )
        else:
            st.button("📥 データベースをエクスポートする", disabled=True)
            st.caption("※エクスポートするデータが登録されていません。")
            
        # バックアップ復元インポート
        backup_file = st.file_uploader("JSONバックアップから復元", type=["json"])
        if backup_file is not None:
            try:
                backup_data = json.load(backup_file)
                if not isinstance(backup_data, list):
                    st.error("❌ 無効なバックアップファイルです。")
                else:
                    success, skips = db.save_records(backup_data)
                    st.success(f"復元完了！ 新規/更新: {success}件, スキップ: {skips}件")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ バックアップの読み込み中にエラーが発生しました: {e}")
                
        st.markdown("---")
        st.markdown("### 📅 特定月のデータ削除")
        st.write("蓄積されているデータから、任意の月のデータのみを安全に削除します。")
        
        # 登録されているユニークな対象月を取得
        unique_months = db.get_unique_months()
        
        if unique_months:
            selected_del_month = st.selectbox("削除する対象月を選択", unique_months, key="select_del_month")
            confirm_del_month = st.checkbox(f"【確認】{selected_del_month} のデータを完全に削除することに同意します。", key="confirm_del_month")
            
            if st.button("🗑️ 選択した月のデータを削除", disabled=not confirm_del_month, key="btn_del_month"):
                deleted_rows = db.delete_records_by_month(selected_del_month)
                st.success(f"🎉 {selected_del_month} の実績データを完全に削除しました。(削除されたレコード: {deleted_rows}件)")
                st.rerun()
        else:
            st.caption("※削除可能な月データが登録されていません。")

        st.markdown("---")
        st.markdown("### ⚠️ データベースの初期化")
        st.write("データベース内のすべての実績データを消去し、アプリを初期状態に戻します。")
        
        # 誤操作防止の確認チェックボックス
        confirm_clear = st.checkbox("【重要】本当にすべての蓄積データを削除します。この操作は取り消せません。", key="confirm_clear")
        
        if st.button("🚨 データベースを全消去", disabled=not confirm_clear, key="btn_clear_db"):
            db.clear_db()
            st.success("🎉 データベースのすべてのレコードを完全に消去しました。")
            st.rerun()
