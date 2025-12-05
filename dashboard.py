import streamlit as st
import pandas as pd
import plotly.express as px
import psycopg2
from thefuzz import process  # Fuzzy Matching kütüphanesi

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
DB_PARAMS = {
    "dbname": "inflation_monitor",
    "user": "postgres",
    "password": "admin",
    "host": "localhost",
    "port": "5432"
}

# Özel CSS
st.markdown("""
<style>
    .block-container {padding-top: 1.5rem; padding-bottom: 1rem;}
    [data-testid="stMetricValue"] {font-size: 2rem; color: #00CC96;}
    thead tr th:first-child {display:none}
    tbody th {display:none}
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
# 3. YAN PANEL (SIDEBAR)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("🎛️ Kontrol Paneli")
    st.markdown("---")
    if not df.empty:
        category_list = ["Tümü"] + list(df["Kategori"].unique())
        selected_category = st.selectbox("Kategori Seç:", category_list, index=1)
        market_list = df["Market"].unique()
        selected_market = st.multiselect("Market:", market_list, default=market_list)
        st.caption(f"📅 Son Veri: {df['Tarih'].max().strftime('%d-%m-%Y')}")
    else:
        st.warning("Veri yok.")

# -----------------------------------------------------------------------------
# 4. ANA EKRAN MANTIĞI
# -----------------------------------------------------------------------------
if df.empty: st.stop()

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

    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam Ürün", len(filtered_df), "Adet")
    c2.metric("Ortalama Birim Fiyat", f"{avg_price:.2f} ₺")
    c3.metric("En Ucuz Ürün", f"{min_row['Birim Fiyat (TL/Kg-L)']:.2f} ₺", min_row['Ürün Adı'][:20] + "...")

st.markdown("---")

# -----------------------------------------------------------------------------
# 5. GELİŞMİŞ ANALİZ SEKMELERİ
# -----------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["🔍 Akıllı Ürün Karşılaştırma (NLP)", "📈 Zaman Trendi", "📋 Veri Seti"])

with tab1:
    st.subheader("🤖 Farklı Marketlerdeki Benzer Ürünleri Bul")
    st.markdown("Bir ürün seçin, yapay zeka diğer marketlerdeki **en benzer** ürünü bulup fiyatını kıyaslasın.")

    # Sadece seçili kategorideki ürünleri listele
    unique_products = filtered_df["Ürün Adı"].unique()
    selected_product_name = st.selectbox("Baz Ürün Seçiniz:", unique_products)

    if selected_product_name:
        # Seçilen ürünün detaylarını al
        base_product = filtered_df[filtered_df["Ürün Adı"] == selected_product_name].iloc[0]
        base_market = base_product["Market"]
        base_price = base_product["Birim Fiyat (TL/Kg-L)"]

        st.info(f"Seçilen: **{selected_product_name}** ({base_market}) -> {base_price:.2f} ₺")

        # Rakip Marketleri Bul
        other_markets = df[df["Market"] != base_market]["Market"].unique()

        comparison_results = []

        # Her rakip market için en benzer ürünü ara
        for m in other_markets:
            # O marketin ve o kategorinin ürünlerini filtrele
            rival_products = df[
                (df["Market"] == m) &
                (df["Kategori"] == base_product["Kategori"])
                ]["Ürün Adı"].tolist()

            if rival_products:
                # Fuzzy Matching (En iyi eşleşmeyi bul)
                match, score = process.extractOne(selected_product_name, rival_products)

                # Sadece benzerlik oranı %50'nin üzerindeyse göster (Alakasızları ele)
                if score > 50:
                    rival_price_row = df[(df["Ürün Adı"] == match) & (df["Market"] == m)].iloc[0]
                    rival_price = rival_price_row["Birim Fiyat (TL/Kg-L)"]

                    diff_ratio = ((rival_price - base_price) / base_price) * 100

                    comparison_results.append({
                        "Market": m,
                        "Eşleşen Ürün": match,
                        "Benzerlik Skoru": score,
                        "Fiyat": rival_price,
                        "Fark (%)": diff_ratio
                    })

        # Sonuçları Göster
        if comparison_results:
            st.write("👇 **Bulunan Muadiller:**")
            comp_df = pd.DataFrame(comparison_results)

            # Renkli Metric Kartları
            cols = st.columns(len(comparison_results))
            for idx, row in enumerate(comparison_results):
                with cols[idx]:
                    color = "normal" if row["Fiyat"] < base_price else "inverse"
                    st.metric(
                        label=f"{row['Market']}",
                        value=f"{row['Fiyat']:.2f} ₺",
                        delta=f"%{row['Fark (%)']:.1f}",
                        delta_color=color
                    )
                    st.caption(f"Eşleşme: {row['Eşleşen Ürün']} (Skor: {row['Benzerlik Skoru']})")
        else:
            st.warning("Diğer marketlerde yeterince benzer bir ürün bulunamadı.")

with tab2:
    st.subheader("📅 Enflasyon Trendi")
    # Tarih ve Market bazında ortalama fiyatı hesapla
    df_trend = filtered_df.groupby(['Tarih', 'Market'])[['Birim Fiyat (TL/Kg-L)']].mean().reset_index()

    if len(df_trend['Tarih'].unique()) > 1:
        fig_trend = px.line(
            df_trend, x='Tarih', y='Birim Fiyat (TL/Kg-L)', color='Market', markers=True,
            title="Ortalama Birim Fiyat Değişimi"
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("Trend grafiği için veritabanında en az 2 farklı güne ait veri birikmesi gerekir.")

with tab3:
    st.dataframe(filtered_df, use_container_width=True)