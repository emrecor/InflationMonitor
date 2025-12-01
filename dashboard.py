import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# -----------------------------------------------------------------------------
# 1. SAYFA KONFİGÜRASYONU VE STİL (CSS)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Enflasyon Monitörü Pro",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Özel CSS ile arayüzü güzelleştirme
st.markdown("""
<style>
    /* Ana başlık boşluğunu azalt */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1rem;
    }
    /* Metrik kartlarını özelleştir */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        color: #00CC96; /* Mint yeşili */
    }
    /* Tablo başlıklarını kalın yap */
    thead tr th:first-child {display:none}
    tbody th {display:none}
</style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# 2. VERİ YÜKLEME VE İŞLEME
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("market_data.csv")
        df.columns = [c.strip() for c in df.columns]
        return df
    except FileNotFoundError:
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
        selected_category = st.selectbox("Kategori Seç:", category_list,
                                         index=1)  # Varsayılan olarak ilk kategoriyi seç

        # Market Filtresi (İleride BİM/A101 eklenirse diye)
        market_list = df["Market"].unique()
        selected_market = st.multiselect("Market:", market_list, default=market_list)

        st.markdown("---")
        st.info("💡 **İpucu:** Grafikleri sağ üst köşesinden büyütebilir, üzerine gelerek detayları görebilirsiniz.")
        st.caption(f"Veri Son Güncelleme: {df['Tarih'].max()}")
    else:
        st.error("Veri dosyası bulunamadı.")

# -----------------------------------------------------------------------------
# 4. ANA EKRAN MANTIĞI
# -----------------------------------------------------------------------------
if df.empty:
    st.warning("⚠️ Lütfen önce 'migros_scraper.py' dosyasını çalıştırın.")
    st.stop()

# Filtreleme İşlemi
if selected_category == "Tümü":
    filtered_df = df[df["Market"].isin(selected_market)]
    page_title = "Genel Piyasa Özeti"
else:
    filtered_df = df[(df["Kategori"] == selected_category) & (df["Market"].isin(selected_market))].copy()
    page_title = f"{selected_category} Analizi"

# -----------------------------------------------------------------------------
# 5. DASHBOARD BAŞLIĞI VE KPI KARTLARI
# -----------------------------------------------------------------------------
st.title(f"📊 {page_title}")
st.markdown("Piyasadaki fiyat hareketlerini ve **Birim Fiyat (TL/Kg-L)** bazlı gerçek maliyetleri analiz edin.")

# İstatistik Hesaplamaları
if not filtered_df.empty:
    avg_price = filtered_df["Birim Fiyat (TL/Kg-L)"].mean()
    min_row = filtered_df.loc[filtered_df["Birim Fiyat (TL/Kg-L)"].idxmin()]
    max_row = filtered_df.loc[filtered_df["Birim Fiyat (TL/Kg-L)"].idxmax()]
    total_items = len(filtered_df)

    # 4 Kolonlu KPI Alanı
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(label="Toplam Ürün", value=total_items, delta="Adet")
    with col2:
        st.metric(label="Ortalama Birim Fiyat", value=f"{avg_price:.2f} ₺")
    with col3:
        st.metric(label="En Ucuz Ürün", value=f"{min_row['Birim Fiyat (TL/Kg-L)']:.2f} ₺",
                  delta=min_row['Ürün Adı'][:15] + "...", delta_color="normal")
    with col4:
        st.metric(label="En Pahalı Ürün", value=f"{max_row['Birim Fiyat (TL/Kg-L)']:.2f} ₺",
                  delta=max_row['Ürün Adı'][:15] + "...", delta_color="inverse")

    st.markdown("---")

# -----------------------------------------------------------------------------
# 6. GRAFİKLER VE ANALİZ (Tabs Yapısı)
# -----------------------------------------------------------------------------
tab_chart, tab_stat, tab_raw = st.tabs(["📈 Fiyat Grafikleri", "🧮 Z-Skoru Analizi (Fırsatlar)", "📋 Detaylı Veri"])

with tab_chart:
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("Ürün Bazlı Fiyat Sıralaması")
        # Bar Chart - Renkli ve Temiz
        fig_bar = px.bar(
            filtered_df.sort_values("Birim Fiyat (TL/Kg-L)"),
            x="Birim Fiyat (TL/Kg-L)",
            y="Ürün Adı",
            orientation='h',  # Yatay bar daha okunaklıdır
            color="Birim Fiyat (TL/Kg-L)",
            color_continuous_scale="Viridis_r",  # Koyu yeşil ucuz, sarı pahalı
            text_auto='.2f'
        )
        fig_bar.update_layout(xaxis_title="Birim Fiyat (TL)", yaxis_title="", showlegend=False, height=600)
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_right:
        st.subheader("Fiyat Dağılımı")
        # Histogram
        fig_hist = px.histogram(
            filtered_df,
            x="Birim Fiyat (TL/Kg-L)",
            nbins=15,
            color_discrete_sequence=['#636EFA']
        )
        fig_hist.update_layout(bargap=0.1)
        st.plotly_chart(fig_hist, use_container_width=True)

        st.info(
            "ℹ️ **Analiz:** Fiyatlar solda toplanıyorsa rekabet yüksek, sağa yayılıyorsa premium ürünler ağırlıkta demektir.")

with tab_stat:
    st.subheader("🎯 Z-Skoru ile Anomalileri Yakala")
    st.markdown("Bir ürünün fiyatı, ortalamadan ne kadar sapıyor? **Yeşil bölge** fırsat ürünlerini gösterir.")

    # Z-Score Hesaplama
    std_dev = filtered_df["Birim Fiyat (TL/Kg-L)"].std()
    if std_dev > 0:
        filtered_df["Z_Score"] = (filtered_df["Birim Fiyat (TL/Kg-L)"] - avg_price) / std_dev
    else:
        filtered_df["Z_Score"] = 0

    # Scatter Plot (Daha profesyonel görünüm)
    fig_scatter = px.scatter(
        filtered_df,
        x="Birim Fiyat (TL/Kg-L)",
        y="Z_Score",
        color="Z_Score",
        size="Raf Fiyatı",  # Baloncuk boyutu raf fiyatı olsun
        hover_name="Ürün Adı",
        color_continuous_scale="RdYlGn_r",  # Yeşil düşük Z-score (Fırsat)
        title="Fiyat vs. Sapma Analizi"
    )
    # Referans Çizgileri
    fig_scatter.add_hline(y=0, line_dash="dot", annotation_text="Ortalama")
    fig_scatter.add_hline(y=-1, line_dash="dash", line_color="green", annotation_text="Fırsat Sınırı")

    st.plotly_chart(fig_scatter, use_container_width=True)

with tab_raw:
    st.subheader("Veri Seti")

    # Streamlit'in yeni özelliği: Column Config ile Görsel Tablo
    st.dataframe(
        filtered_df[["Tarih", "Kategori", "Ürün Adı", "Raf Fiyatı", "Birim Fiyat (TL/Kg-L)"]],
        column_config={
            "Raf Fiyatı": st.column_config.NumberColumn(
                "Raf Fiyatı (₺)",
                format="%.2f ₺"
            ),
            "Birim Fiyat (TL/Kg-L)": st.column_config.ProgressColumn(
                "Birim Fiyat (Maliyet)",
                help="Birim fiyatın görece pahalılığı",
                format="%.2f ₺",
                min_value=0,
                max_value=filtered_df["Birim Fiyat (TL/Kg-L)"].max()
            ),
        },
        use_container_width=True,
        hide_index=True
    )