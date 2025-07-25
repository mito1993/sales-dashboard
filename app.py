import streamlit as st
import gspread
import pandas as pd
import plotly.express as px
from dateutil.relativedelta import relativedelta

# カスタムCSS（変更なし）
st.markdown(
    """
    <style>
    html, body, [class*="css"]  {
        font-family: 'Segoe UI', 'Yu Gothic', 'Meiryo', sans-serif;
        background-color: #f7f9fa;
    }
    .stSidebar {
        background: linear-gradient(135deg, #e0e7ef 60%, #f7f9fa 100%);
        border-radius: 0 16px 16px 0;
        box-shadow: 2px 0 8px rgba(0,0,0,0.04);
    }
    .st-bb, .st-c0, .st-c1, .st-c2, .st-c3, .st-c4, .st-c5 {
        border-radius: 12px !important;
    }
    .stButton>button {
        border-radius: 8px;
        background: #3b82f6;
        color: white;
        font-weight: 600;
        border: none;
        transition: background 0.2s;
    }
    .stButton>button:hover {
        background: #2563eb;
    }
    .stDataFrame, .stTable {
        background: white;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.03);
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ページ設定
st.set_page_config(page_title="営業成績ダッシュボード", layout="wide")

# タイトル
st.title("営業成績ダッシュボード")
st.markdown("""
#### 営業成績データを可視化・分析するダッシュボードです。
サイドバーのフィルターで条件を絞り込み、売上・粗利の推移をグラフで確認できます。
""")

# 日付から営業期を判定する関数
def get_fiscal_period(date):
    """
    日付を受け取り、4月始まりの年度から「第X期」という文字列を返す。
    2023/4/1 ~ 2024/3/31 を 第1期 とする。
    """
    if pd.isna(date):
        return None
    fiscal_year = date.year if date.month >= 4 else date.year - 1
    period_number = fiscal_year - 2022
    if period_number > 0:
        return f"第{period_number}期"
    return "対象期間外"

@st.cache_data(ttl=600)
def load_and_process_data(sheet_name: str) -> pd.DataFrame:
    """Googleスプレッドシートからデータを読み込み、前処理を行う"""
    creds = st.secrets["gcp_service_account"]
    gc = gspread.service_account_from_dict(creds)
    sh = gc.open(sheet_name)
    worksheet = sh.get_worksheet(0)
    
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    if '管理No.' in df.columns:
        df = df[df['管理No.'].astype(str).str.strip() != ''].copy()

    # --- データ処理 ---
    df["受注月"] = pd.to_datetime(df["受注月"], errors="coerce")
    df["納品月"] = pd.to_datetime(df["納品月"], errors="coerce")

    currency_columns = ['売上（税抜）', '粗利（税抜）']
    for col in currency_columns:
        if col in df.columns:
            df[col] = df[col].replace(r'^\s*$', None, regex=True)
            df[col] = df[col].astype(str).str.replace('[¥,]', '', regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df["受注期"] = df["受注月"].apply(get_fiscal_period)
    df["納品期"] = df["納品月"].apply(get_fiscal_period)
    return df

try:
    df = load_and_process_data('営業成績データ')

    st.sidebar.header("フィルター")

    # --- フィルター部分 ---
    shoryu_options = df["商流"].dropna().unique().tolist()
    selected_shoryu = st.sidebar.multiselect("商流を選択", shoryu_options, default=shoryu_options)

    phase_options = df["案件フェーズ"].dropna().unique().tolist()
    selected_phase = st.sidebar.multiselect("案件フェーズを選択", phase_options, default=phase_options)

    sales_options = [
        "相川直輝", "佐々木亮", "高橋和大", "衛本楓河",
        "野沢響", "室伏夕", "湯浅華", "佐々木信", "韓国"
    ]
    selected_sales = st.sidebar.multiselect("担当営業を選択", sales_options, default=sales_options)
    
    order_periods = df["受注期"].dropna().unique()
    delivery_periods = df["納品期"].dropna().unique()
    all_periods = sorted(list(set(order_periods) | set(delivery_periods)))
    
    latest_period_index = len(all_periods) - 1 if all_periods else 0
    selected_period = st.sidebar.selectbox("営業期を選択", all_periods, index=latest_period_index)
    
    sales_col_1 = '担当者' 
    sales_col_2 = '営業担当' 

    base_filter = (
        (df["商流"].isin(selected_shoryu)) &
        (df["案件フェーズ"].isin(selected_phase)) &
        (df[sales_col_1].isin(selected_sales) | df[sales_col_2].isin(selected_sales))
    )

    # --- ▼▼▼ グラフ生成ロジックを修正 ▼▼▼ ---
    def create_full_period_df(period_str):
        """ '第X期' からその期の12ヶ月分のDataFrameを作成する """
        if not isinstance(period_str, str) or "第" not in period_str:
            return None
        period_num = int(period_str.replace('第','').replace('期',''))
        start_year = 2022 + period_num
        start_date = pd.Timestamp(year=start_year, month=4, day=1)
        # 12ヶ月分の月を生成
        months = [start_date + relativedelta(months=i) for i in range(12)]
        return pd.DataFrame({'月': months})

    # グラフ描画
    # 1. 受注月ごとの売上・粗利推移（棒グラフ）
    st.subheader(f"{selected_period} 受注月ごとの売上・粗利推移")
    
    df_order_filtered = df[base_filter & (df["受注期"] == selected_period)]

    # 選択された期の12ヶ月分の空のDataFrameを作成
    full_period_order_df = create_full_period_df(selected_period)
    
    if full_period_order_df is not None and not df_order_filtered.empty:
        df_order_grouped = df_order_filtered.set_index('受注月').groupby(pd.Grouper(freq='M'))[['売上（税抜）', '粗利（税抜）']].sum().reset_index()
        df_order_grouped.rename(columns={'受注月': '月'}, inplace=True)
        
        # 12ヶ月分のデータと実績データを結合
        merged_df_order = pd.merge(full_period_order_df, df_order_grouped, on='月', how='left').fillna(0)
        
        df_order_melted = merged_df_order.melt(id_vars='月', value_vars=['売上（税抜）', '粗利（税抜）'], var_name='指標', value_name='合計値')
        
        fig_order = px.bar(
            df_order_melted, x='月', y='合計値', color='指標',
            barmode='group', title="受注ベース 売上・粗利",
            template="plotly_white", color_discrete_map={'売上（税抜）': '#3b82f6', '粗利（税抜）': '#2dd4bf'}
        )
        fig_order.update_layout(
            xaxis_title="受注月", yaxis_title="合計金額", title_font_size=22,
            xaxis_tickformat='%Y-%m', yaxis_tickformat=',.0f'
        )
        fig_order.update_yaxes(rangemode="tozero")
        st.plotly_chart(fig_order, use_container_width=True)
    else:
        st.info(f"{selected_period}の受注データはありません。")


    # 2. 納品月ごとの売上・粗利推移（折れ線グラフ）
    st.subheader(f"{selected_period} 納品月ごとの売上・粗利推移")

    df_delivery_filtered = df[base_filter & (df["納品期"] == selected_period)]
    
    full_period_delivery_df = create_full_period_df(selected_period)

    if full_period_delivery_df is not None and not df_delivery_filtered.empty:
        df_delivery_grouped = df_delivery_filtered.set_index('納品月').groupby(pd.Grouper(freq='M'))[['売上（税抜）', '粗利（税抜）']].sum().reset_index()
        df_delivery_grouped.rename(columns={'納品月': '月'}, inplace=True)

        merged_df_delivery = pd.merge(full_period_delivery_df, df_delivery_grouped, on='月', how='left').fillna(0)
        
        df_delivery_melted = merged_df_delivery.melt(id_vars='月', value_vars=['売上（税抜）', '粗利（税抜）'], var_name='指標', value_name='合計値')

        fig_delivery = px.line(
            df_delivery_melted, x='月', y='合計値', color='指標',
            title="納品ベース 売上・粗利", markers=True,
            template="plotly_white", color_discrete_map={'売上（税抜）': '#636EFA', '粗利（税抜）': '#f472b6'}
        )
        fig_delivery.update_layout(
            xaxis_title="納品月", yaxis_title="合計金額", title_font_size=22,
            xaxis_tickformat='%Y-%m', yaxis_tickformat=',.0f'
        )
        fig_delivery.update_yaxes(rangemode="tozero")
        st.plotly_chart(fig_delivery, use_container_width=True)
    else:
        st.info(f"{selected_period}の納品データはありません。")

except Exception as e:
    st.error(f"データの読み込み中または処理中にエラーが発生しました: {e}")
    st.info("以下の点をご確認ください：\n"
            "1. Streamlit CloudのSecrets設定は正しいですか？\n"
            "2. Googleスプレッドシート名（'営業成績データ'）は正しいですか？\n"
            "3. サービスアカウントにスプレッドシートの閲覧権限が付与されていますか？\n"
            "4. スプレッドシートのヘッダー名（列名）は、コード内の指定と完全に一致していますか？")
