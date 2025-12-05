import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
from thefuzz import process
# YENİ: Forecasting modülünü ekledik
from forecasting import predict_price

import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Veritabanı bilgilerini ortam değişkenlerinden al
DB_PARAMS = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}
st.set_page_config(
    page_title="Enflasyon Monitörü Pro",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .block-container {padding-top: 1.5rem; padding-bottom: 1rem;}
    [data-testid="stMetricValue"] {font-size: 2rem; color: #00CC96;}
</style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# 2. VERİ YÜKLEME
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        query = "SELECT * FROM prices"
        df = pd.read_sql(query, conn)
        conn.close()

        if df.empty: return pd.DataFrame()

        df = df.rename(columns={
            "date": "Tarih", "market": "Market", "category": "Kategori",
            "product_name": "Ürün Adı", "price": "Raf Fiyatı",
            "unit_price": "Birim Fiyat (TL/Kg-L)", "unit": "Birim"
        })
        df["Tarih"] = pd.to_datetime(df["Tarih"])
        return df
    except Exception as e:
        st.error(f"Veritabanı Hatası: {e}")
        return pd.DataFrame()


df = load_data()

# -----------------------------------------------------------------------------
# 3. YAN PANEL
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("🎛️ Kontrol Paneli")
    if not df.empty:
        category_list = ["Tümü"] + list(df["Kategori"].unique())
        selected_category = st.selectbox("Kategori Seç:", category_list, index=1)
        market_list = df["Market"].unique()
        selected_market = st.multiselect("Market:", market_list, default=market_list)
        st.caption(f"📅 Son Veri: {df['Tarih'].max().strftime('%d-%m-%Y')}")
    else:
        st.warning("Veri yok.")

# -----------------------------------------------------------------------------
# 4. ANA EKRAN
# -----------------------------------------------------------------------------
if df.empty: st.stop()

if selected_category == "Tümü":
    filtered_df = df[df["Market"].isin(selected_market)]
    page_title = "Genel Piyasa Özeti"
else:
    filtered_df = df[(df["Kategori"] == selected_category) & (df["Market"].isin(selected_market))].copy()
    page_title = f"{selected_category} Analizi"

st.title(f"📊 {page_title}")

# KPI
if not filtered_df.empty:
    avg_price = filtered_df["Birim Fiyat (TL/Kg-L)"].mean()
    min_row = filtered_df.loc[filtered_df["Birim Fiyat (TL/Kg-L)"].idxmin()]

    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam Ürün", len(filtered_df), "Adet")
    c2.metric("Ortalama Birim Fiyat", f"{avg_price:.2f} ₺")
    c3.metric("En Ucuz", f"{min_row['Birim Fiyat (TL/Kg-L)']:.2f} ₺", min_row['Ürün Adı'][:20] + "...")

st.markdown("---")

# -----------------------------------------------------------------------------
# 5. ANALİZ SEKMELERİ (YENİ SEKME EKLENDİ)
# -----------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["🔮 Gelecek Tahmini (AI)", "🔍 Akıllı Karşılaştırma", "📈 Trend", "📋 Veri"])

# --- TAB 1: GELECEK TAHMİNİ (PROPHET) ---
with tab1:
    st.subheader("📈 Yapay Zeka ile Fiyat Tahmini")
    st.info("Bu modül, Facebook Prophet algoritmasını kullanarak seçilen ürünün gelecekteki fiyatını tahmin eder.")

    # Ürün Seçimi
    product_list = filtered_df["Ürün Adı"].unique()
    forecast_product = st.selectbox("Tahmin Yapılacak Ürünü Seçin:", product_list)

    # Gün Seçimi
    days_to_predict = st.radio("Kaç gün sonrasını görmek istersiniz?", [7, 30, 90], horizontal=True)

    if st.button("🚀 Tahmini Başlat"):
        with st.spinner('Yapay zeka verileri analiz ediyor...'):
            # Forecasting.py'deki fonksiyonu çağır
            forecast_df, error = predict_price(forecast_product, days_to_predict, DB_PARAMS)

            if error:
                st.error(error)
            else:
                # Grafiği Çiz
                fig = go.Figure()

                # 1. Gerçek Veriler
                real_data = df[df["Ürün Adı"] == forecast_product].sort_values("Tarih")
                fig.add_trace(go.Scatter(
                    x=real_data['Tarih'], y=real_data['Raf Fiyatı'],
                    mode='lines+markers', name='Gerçek Fiyat',
                    line=dict(color='blue')
                ))

                # 2. Tahmin Verileri (Gelecek)
                # Sadece bugünden sonrasını çizdirelim ki karışmasın
                future_forecast = forecast_df[forecast_df['ds'] > real_data['Tarih'].max()]

                fig.add_trace(go.Scatter(
                    x=future_forecast['ds'], y=future_forecast['yhat'],
                    mode='lines', name='Tahmin (AI)',
                    line=dict(color='red', dash='dash')
                ))

                # 3. Güven Aralığı (Alt ve Üst sınır)
                fig.add_trace(go.Scatter(
                    x=future_forecast['ds'], y=future_forecast['yhat_upper'],
                    mode='lines', line=dict(width=0), showlegend=False
                ))
                fig.add_trace(go.Scatter(
                    x=future_forecast['ds'], y=future_forecast['yhat_lower'],
                    mode='lines', line=dict(width=0), fill='tonexty',
                    fillcolor='rgba(255, 0, 0, 0.2)', name='Güven Aralığı'
                ))

                fig.update_layout(title=f"{forecast_product} - {days_to_predict} Günlük Tahmin", xaxis_title="Tarih",
                                  yaxis_title="Fiyat (TL)")
                st.plotly_chart(fig, use_container_width=True)

                # Tahmin Özeti
                last_price = real_data.iloc[-1]['Raf Fiyatı']
                predicted_price = future_forecast.iloc[-1]['yhat']
                change = ((predicted_price - last_price) / last_price) * 100

                c1, c2, c3 = st.columns(3)
                c1.metric("Şu Anki Fiyat", f"{last_price:.2f} TL")
                c2.metric(f"{days_to_predict} Gün Sonra (Tahmin)", f"{predicted_price:.2f} TL")
                c3.metric("Beklenen Değişim", f"%{change:.1f}", delta_color="inverse")

# --- TAB 2: KARŞILAŞTIRMA (ESKİ KODUN AYNISI) ---
with tab2:
    st.subheader("🤖 Farklı Marketlerdeki Benzer Ürünleri Bul")
    selected_product_name = st.selectbox("Baz Ürün Seçiniz (Kıyaslama):", filtered_df["Ürün Adı"].unique())

    if selected_product_name:
        base_product = filtered_df[filtered_df["Ürün Adı"] == selected_product_name].iloc[0]
        base_market = base_product["Market"]
        base_price = base_product["Birim Fiyat (TL/Kg-L)"]

        st.info(f"📍 Seçilen: **{selected_product_name}** ({base_market}) -> **{base_price:.2f} TL** (Birim)")

        other_markets = df[df["Market"] != base_market]["Market"].unique()
        comparison_results = []

        for m in other_markets:
            rival_products_df = df[(df["Market"] == m) & (df["Kategori"] == base_product["Kategori"])]
            rival_names = rival_products_df["Ürün Adı"].tolist()

            if rival_names:
                match, score = process.extractOne(selected_product_name, rival_names)
                if score > 50:
                    rival_row = rival_products_df[rival_products_df["Ürün Adı"] == match].iloc[0]
                    rival_price = rival_row["Birim Fiyat (TL/Kg-L)"]
                    diff_ratio = ((rival_price - base_price) / base_price) * 100 if base_price > 0 else 0

                    comparison_results.append({
                        "Market": m, "Eşleşen Ürün": match, "Benzerlik Skoru": score,
                        "Birim Fiyat": rival_price, "Fark (%)": diff_ratio
                    })

        if comparison_results:
            cols = st.columns(len(comparison_results))
            for idx, row in enumerate(comparison_results):
                with cols[idx]:
                    color = "normal" if row["Birim Fiyat"] < base_price else "inverse"
                    st.metric(label=f"{row['Market']}", value=f"{row['Birim Fiyat']:.2f} TL",
                              delta=f"%{row['Fark (%)']:.1f}", delta_color=color)
                    st.caption(f"Eşleşme: {row['Eşleşen Ürün']}")
        else:
            st.warning("Benzer ürün bulunamadı.")

# --- TAB 3: TREND ---
with tab3:
    st.subheader("📅 Fiyat Değişim Trendi")
    df_trend = filtered_df.groupby(['Tarih', 'Market'])[['Birim Fiyat (TL/Kg-L)']].mean().reset_index()
    if len(df_trend['Tarih'].unique()) > 1:
        fig_trend = px.line(df_trend, x='Tarih', y='Birim Fiyat (TL/Kg-L)', color='Market', markers=True)
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("Trend grafiği için en az 2 günlük veri gerekir.")

# --- TAB 4: VERİ ---
with tab4:
    st.dataframe(filtered_df, use_container_width=True)