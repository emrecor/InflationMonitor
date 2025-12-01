import streamlit as st
import pandas as pd
import plotly.express as px
import psycopg2

# -----------------------------------------------------------------------------
# 1. SAYFA VE VERİTABANI AYARLARI
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Enflasyon Monitörü Pro",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# PostgreSQL Bağlantı Bilgileri
# (main.py dosyasındaki ile aynı olmalı)
DB_PARAMS = {
    "dbname": "inflation_monitor",
    "user": "postgres",
    "password": "admin",
    "host": "localhost",
    "port": "5432"
}

# Özel CSS Tasarımı
st.markdown("""
<style>
    .block-container {padding-top: 1.5rem; padding-bottom: 1rem;}
    [data-testid="stMetricValue"] {font-size: 2rem; color: #00CC96;}
    thead tr th:first-child {display:none}
    tbody th {display:none}
</style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# 2. VERİ YÜKLEME (PostgreSQL'den Çekme)
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    try:
        conn = psycopg2.connect(**DB_PARAMS)

        # Veriyi çek
        query = "SELECT * FROM prices"
        df = pd.read_sql(query, conn)
        conn.close()

        if df.empty:
            return pd.DataFrame()

        # İngilizce sütun isimlerini Dashboard için Türkçeye çevir
        df = df.rename(columns={
            "date": "Tarih",
            "market": "Market",
            "category": "Kategori",
            "product_name": "Ürün Adı",
            "price": "Raf Fiyatı",
            "unit_price": "Birim Fiyat (TL/Kg-L)",
            "unit": "Birim"
        })

        # Tarih formatını düzelt
        df["Tarih"] = pd.to_datetime(df["Tarih"])
        return df

    except Exception as e:
        st.error(f"⚠️ Veritabanına bağlanılamadı: {e}")
        st.info("Lütfen 'main.py' dosyasını çalıştırıp veri kaydettiğinizden ve şifrenizin doğru olduğundan emin olun.")
        return pd.DataFrame()


df = load_data()

# -----------------------------------------------------------------------------
# 3. YAN PANEL (SIDEBAR)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("🎛️ Kontrol Paneli")
    st.markdown("---")

    if not df.empty:
        # Kategori Filtresi
        category_list = ["Tümü"] + list(df["Kategori"].unique())
        selected_category = st.selectbox("Kategori Seç:", category_list, index=1)

        # Market Filtresi
        market_list = df["Market"].unique()
        selected_market = st.multiselect("Market:", market_list, default=market_list)

        st.markdown("---")
        st.caption(f"📅 Son Veri: {df['Tarih'].max().strftime('%d-%m-%Y')}")
    else:
        st.warning("Veri bulunamadı.")

# -----------------------------------------------------------------------------
# 4. ANA EKRAN MANTIĞI
# -----------------------------------------------------------------------------
if df.empty:
    st.stop()

# Filtreleme
if selected_category == "Tümü":
    filtered_df = df[df["Market"].isin(selected_market)]
    page_title = "Genel Piyasa Özeti"
else:
    filtered_df = df[(df["Kategori"] == selected_category) & (df["Market"].isin(selected_market))].copy()
    page_title = f"{selected_category} Analizi"

st.title(f"📊 {page_title}")

# KPI Kartları
if not filtered_df.empty:
    avg_price = filtered_df["Birim Fiyat (TL/Kg-L)"].mean()
    min_row = filtered_df.loc[filtered_df["Birim Fiyat (TL/Kg-L)"].idxmin()]
    max_row = filtered_df.loc[filtered_df["Birim Fiyat (TL/Kg-L)"].idxmax()]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Ürün", len(filtered_df), "Adet")
    c2.metric("Ortalama Birim Fiyat", f"{avg_price:.2f} ₺")
    c3.metric("En Ucuz", f"{min_row['Birim Fiyat (TL/Kg-L)']:.2f} ₺", min_row['Ürün Adı'][:15] + "...",
              delta_color="normal")
    c4.metric("En Pahalı", f"{max_row['Birim Fiyat (TL/Kg-L)']:.2f} ₺", max_row['Ürün Adı'][:15] + "...",
              delta_color="inverse")

st.markdown("---")

# -----------------------------------------------------------------------------
# 5. GRAFİKLER (Zaman Serisi Eklendi)
# -----------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📈 Trend & Fiyatlar", "🧮 Fırsat Analizi", "📋 Veri Tablosu"])

with tab1:
    # 1. ZAMAN SERİSİ GRAFİĞİ (ENFLASYON TAKİBİ)
    st.subheader("📅 Fiyat Değişim Trendi")

    # Tarih ve Market bazında ortalama fiyatı hesapla
    df_trend = filtered_df.groupby(['Tarih', 'Market'])[['Birim Fiyat (TL/Kg-L)']].mean().reset_index()

    if len(df_trend['Tarih'].unique()) > 1:
        fig_trend = px.line(
            df_trend, x='Tarih', y='Birim Fiyat (TL/Kg-L)', color='Market', markers=True,
            title="Zaman İçindeki Ortalama Birim Fiyat Değişimi"
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info(
            "ℹ️ Trend grafiği için en az 2 farklı güne ait veri olması gerekir. Yarın veri çektiğinizde burası açılacak.")

    st.markdown("---")

    # 2. ÜRÜN BAZLI BAR CHART
    col_left, col_right = st.columns([2, 1])
    with col_left:
        st.subheader("Ürün Sıralaması")
        fig_bar = px.bar(
            filtered_df.sort_values("Birim Fiyat (TL/Kg-L)"),
            x="Birim Fiyat (TL/Kg-L)", y="Ürün Adı", orientation='h',
            color="Birim Fiyat (TL/Kg-L)", color_continuous_scale="Viridis_r"
        )
        fig_bar.update_layout(yaxis={'visible': True, 'showticklabels': False}, height=500)  # İsimler çok uzunsa gizle
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_right:
        st.subheader("Dağılım")
        fig_hist = px.histogram(filtered_df, x="Birim Fiyat (TL/Kg-L)", nbins=20)
        st.plotly_chart(fig_hist, use_container_width=True)

with tab2:
    st.subheader("🎯 Z-Skoru (Fiyat Sapması)")
    # Basit Z-Score Hesabı
    std = filtered_df["Birim Fiyat (TL/Kg-L)"].std()
    mean = filtered_df["Birim Fiyat (TL/Kg-L)"].mean()

    if std > 0:
        filtered_df["Z_Score"] = (filtered_df["Birim Fiyat (TL/Kg-L)"] - mean) / std

        fig_scatter = px.scatter(
            filtered_df, x="Birim Fiyat (TL/Kg-L)", y="Z_Score",
            color="Z_Score", size="Raf Fiyatı", hover_name="Ürün Adı",
            color_continuous_scale="RdYlGn_r",
            title="Yeşil Alan = Fırsat Ürünleri (Ortalamadan Ucuz)"
        )
        fig_scatter.add_hline(y=0, line_dash="dot", annotation_text="Ortalama")
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.warning("Yeterli veri çeşitliliği yok.")

with tab3:
    st.dataframe(
        filtered_df[["Tarih", "Market", "Kategori", "Ürün Adı", "Raf Fiyatı", "Birim Fiyat (TL/Kg-L)"]],
        use_container_width=True, hide_index=True
    )