import streamlit as st
import gspread
import pandas as pd
import plotly.express as px

st.subheader("デバッグ情報")
try:
    creds_from_secrets = st.secrets["gcp_service_account"]
    st.write("✅ Secretsの読み込みに成功しました。")
    st.write("情報の型:", type(creds_from_secrets))
    st.write("キーの一覧:", creds_from_secrets.keys())
except Exception as e:
    st.write("🚨 Secretsの読み込みに失敗しました。")
    st.error(e)

# カスタムCSS（全体フォント・サイドバーのモダン化）
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

# 1. ページ設定
st.set_page_config(page_title="営業成績ダッシュボード", layout="wide")

# 2. アプリの最上部に見出しと説明文
st.title("営業成績ダッシュボード")
st.markdown("""
#### 営業成績データを可視化・分析するダッシュボードです。
サイドバーのフィルターで条件を絞り込み、売上推移をグラフで確認できます。
""")

# データ取得・フィルター処理
@st.cache_data
def load_gsheet_to_df(sheet_name: str) -> pd.DataFrame:
    creds_dict = st.secrets.to_dict()
    gc = gspread.service_account_from_dict(creds_dict)
    sh = gc.open(sheet_name)
    worksheet = sh.get_worksheet(0)
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return df

df = load_gsheet_to_df('営業成績データ')

st.sidebar.header("フィルター")
shoryu_options = df["商流"].dropna().unique().tolist()
selected_shoryu = st.sidebar.multiselect("商流を選択", shoryu_options, default=shoryu_options)
sales_options = df["担当営業"].dropna().unique().tolist()
selected_sales = st.sidebar.multiselect("担当営業を選択", sales_options, default=sales_options)
period_options = df["営業期"].dropna().unique().tolist()
selected_period = st.sidebar.selectbox("営業期を選択", period_options, index=0)
filtered_df = df[
    df["商流"].isin(selected_shoryu) &
    df["担当営業"].isin(selected_sales) &
    (df["営業期"] == selected_period)
]

st.dataframe(filtered_df)

# 日付列をdatetime型に変換
filtered_df["受注日"] = pd.to_datetime(filtered_df["受注日"], errors="coerce")
filtered_df["納品日"] = pd.to_datetime(filtered_df["納品日"], errors="coerce")

# 1. 受注月ごとの売上推移（棒グラフ）
if not filtered_df["受注日"].isnull().all():
    st.subheader("受注月ごとの売上推移")
    df_order = filtered_df.dropna(subset=["受注日"]).copy()
    df_order["受注月"] = df_order["受注日"].dt.to_period("M").dt.to_timestamp()
    order_monthly = df_order.groupby("受注月")["金額"].sum().reset_index()
    fig_order = px.bar(
        order_monthly,
        x="受注月",
        y="金額",
        title="受注月ごとの売上推移",
        template="plotly_white",
        color_discrete_sequence=px.colors.sequential.Teal,
    )
    fig_order.update_layout(
        xaxis_title="受注月",
        yaxis_title="合計金額",
        title_font_size=22,
        plot_bgcolor="#f9f9f9",
        paper_bgcolor="#f9f9f9",
    )
    st.plotly_chart(fig_order, use_container_width=True)

# 2. 納品月ごとの売上推移（折れ線グラフ）
if not filtered_df["納品日"].isnull().all():
    st.subheader("納品月ごとの売上推移")
    df_delivery = filtered_df.dropna(subset=["納品日"]).copy()
    df_delivery["納品月"] = df_delivery["納品日"].dt.to_period("M").dt.to_timestamp()
    delivery_monthly = df_delivery.groupby("納品月")["金額"].sum().reset_index()
    fig_delivery = px.line(
        delivery_monthly,
        x="納品月",
        y="金額",
        title="納品月ごとの売上推移",
        template="plotly_white",
        color_discrete_sequence=["#636EFA"],
        markers=True
    )
    fig_delivery.update_layout(
        xaxis_title="納品月",
        yaxis_title="合計金額",
        title_font_size=22,
        plot_bgcolor="#f9f9f9",
        paper_bgcolor="#f9f9f9",
    )
    st.plotly_chart(fig_delivery, use_container_width=True) 
    
