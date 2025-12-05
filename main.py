import psycopg2
import datetime
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Scraper Modülleri
# Not: scrapers klasöründeki migros.py ve a101.py dosyalarınızın yanına dokunmanıza gerek yok.
from scrapers.migros import scrape_migros
from scrapers.a101 import scrape_a101
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

# --- YARDIMCI FONKSİYONLAR ---

def clean_price(price_text):
    """Metin halindeki fiyatı (120,50 TL) sayıya çevirir."""
    if not price_text: return None
    try:
        # TL, ₺, boşluklar temizle
        clean = price_text.replace("TL", "").replace("₺", "").replace("\n", "").strip()
        clean = clean.replace(".", "")  # Binlik ayracı sil (1.200 -> 1200)
        clean = clean.replace(",", ".")  # Ondalık virgülü noktaya çevir (12,50 -> 12.50)
        return float(clean)
    except ValueError:
        return None


def extract_unit_price(product_name, price):
    """
    Birim fiyat hesaplama motoru.
    Multipack (4x1), Yumurta ve Gramaj hesaplar.
    """
    name_lower = product_name.lower().replace("İ", "i").replace("I", "ı").replace(" ", "").replace(",", ".")

    # 1. MULTIPACK KURALI (Örn: 4x1 L, 6*200 ml)
    # Regex: Rakam + (x veya *) + Rakam + Birim
    multipack = re.search(r"(\d+)\s*[\*xX]\s*(\d*\.?\d+)\s*(kg|gr|g|l|ml|lt)", name_lower)

    if multipack:
        count = float(multipack.group(1))
        amount = float(multipack.group(2))
        unit = multipack.group(3)

        # Gramaj dönüşümü (ml/gr -> L/kg)
        if unit in ["gr", "g", "ml"]: amount /= 1000.0

        total_amount = count * amount
        if total_amount > 0:
            return round(price / total_amount, 2)

    # 2. YUMURTA KURALI (Adet hesabı)
    if "yumurta" in name_lower:
        # 15'li, 30lu vb.
        match = re.search(r"(\d+)\s*['’]?\s*[l][ıiIuÜ]", name_lower)
        if match: return round(price / float(match.group(1)), 2)

        # 30 adet vb.
        match_adet = re.search(r"(\d+)\s*adet", name_lower)
        if match_adet: return round(price / float(match_adet.group(1)), 2)

    # 3. STANDART GRAMAJ (1 kg, 500 gr vb.)
    # Kalibre koruması (400/600 gr levrek gibi ifadeleri bölmesin)
    if "/" in name_lower and any(x in name_lower for x in ['levrek', 'cipura', 'somon', 'uskumru']):
        return price

    match = re.search(r"(\d+)(kg|gr|g|l|ml|lt)", name_lower)
    if match:
        try:
            amount = float(match.group(1))
            unit = match.group(2)
            if unit in ["gr", "g", "ml"]: amount /= 1000.0

            if amount > 0:
                u_p = price / amount
                # Güvenlik: 5 TL altı birim fiyat (Su/Soda hariç) genelde hatadır, bölme.
                if u_p < 5.0 and "su" not in name_lower and "soda" not in name_lower: return price
                return round(u_p, 2)
        except:
            return price

    return price


# --- POSTGRESQL VERİTABANI İŞLEMLERİ ---

def init_db():
    """PostgreSQL tablosunu oluşturur (Eğer yoksa)."""
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        # PostgreSQL'de AUTOINCREMENT yerine SERIAL kullanılır
        cur.execute('''
                    CREATE TABLE IF NOT EXISTS prices
                    (
                        id
                        SERIAL
                        PRIMARY
                        KEY,
                        date
                        DATE,
                        market
                        VARCHAR
                    (
                        50
                    ),
                        category VARCHAR
                    (
                        100
                    ),
                        product_name TEXT,
                        price NUMERIC
                    (
                        10,
                        2
                    ),
                        unit_price NUMERIC
                    (
                        10,
                        2
                    ),
                        unit VARCHAR
                    (
                        20
                    )
                        )
                    ''')
        conn.commit()
        cur.close()
        conn.close()
        print("🐘 PostgreSQL veritabanı bağlantısı başarılı ve tablo hazır.")
    except Exception as e:
        print(f"❌ Veritabanı Bağlantı Hatası: {e}")
        print(
            "💡 İPUCU: pgAdmin'den 'inflation_monitor' adında bir veritabanı oluşturduğuna ve şifrenin doğru olduğuna emin ol.")


def save_to_db(data):
    """Verileri PostgreSQL veritabanına kaydeder."""
    if not data:
        return

    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        # PostgreSQL placeholder'ı %s dir. SQLite'taki ? çalışmaz.
        query = '''
                INSERT INTO prices (date, market, category, product_name, price, unit_price, unit)
                VALUES (%s, %s, %s, %s, %s, %s, %s) \
                '''

        # executemany ile toplu ve hızlı kayıt
        cur.executemany(query, data)

        conn.commit()
        cur.close()
        conn.close()
        print(f"\n🚀 Toplam {len(data)} satır veri PostgreSQL veritabanına başarıyla eklendi.")
    except Exception as e:
        print(f"❌ Kayıt Hatası: {e}")


# --- ANA PROGRAM BAŞLANGICI ---
if __name__ == "__main__":

    # 1. Veritabanını Başlat / Kontrol Et
    init_db()

    options = webdriver.ChromeOptions()
    # Headless Mod: Tarayıcıyı ekranda açmaz, arka planda çalışır (Daha hızlı ve profesyonel)
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")

    # Anti-Bot: Gerçek kullanıcı gibi görünmek için User-Agent
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    # EAGER MODE: Sayfa yüklenmesini bekleme stratejisi
    options.page_load_strategy = 'eager'

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(45)  # 45 sn zaman aşımı

    all_products = []
    today = datetime.date.today().strftime("%Y-%m-%d")

    try:
        # Migros Taraması
        try:
            scrape_migros(driver, all_products, clean_price, extract_unit_price, today)
        except Exception as e:
            print(f"❌ Migros Hatası: {e}")


        try:

            scrape_a101(driver, all_products, clean_price, extract_unit_price, today)
        except Exception as e:
            print(f"❌ A101 Hatası: {e}")

    except Exception as main_e:
        print(f"❌ Genel Hata: {main_e}")

    finally:
        driver.quit()

        if all_products:
            save_to_db(all_products)  # Artık CSV değil, DB'ye kaydediyoruz
            print("✅ İşlem Başarıyla Tamamlandı.")
        else:
            print("⚠️ Hiç veri toplanmadı.")