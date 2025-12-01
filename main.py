import csv
import datetime
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Scraper Modülleri
from scrapers.migros import scrape_migros
from scrapers.a101 import scrape_a101


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
    V4.0: Multipack (4x1), Yumurta ve Gramaj hesaplama motoru.
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
            # print(f"   🔢 Multipack: {product_name} -> {count}x{amount} = {total_amount} Birim")
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


def save_to_csv(data):
    """Verileri CSV dosyasına kaydeder."""
    file_exists = False
    try:
        with open('market_data.csv', 'r', encoding='utf-8') as f:
            file_exists = True
    except FileNotFoundError:
        pass

    with open('market_data.csv', 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Dosya yoksa başlıkları yaz
        if not file_exists:
            writer.writerow(["Tarih", "Market", "Kategori", "Ürün Adı", "Raf Fiyatı", "Birim Fiyat (TL/Kg-L)", "Birim"])

        for row in data:
            writer.writerow(row)
    print(f"\n💾 Toplam {len(data)} satır veri 'market_data.csv' dosyasına eklendi.")


# --- ANA PROGRAM BAŞLANGICI ---
if __name__ == "__main__":

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")

    # EAGER MODE: Sayfanın %100 yüklenmesini bekleme, HTML gelince başla (Hızlandırır)
    options.page_load_strategy = 'eager'

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(45)  # 45 sn zaman aşımı

    all_products = []
    today = datetime.date.today().strftime("%Y-%m-%d")

    try:

        try:
            scrape_migros(driver, all_products, clean_price, extract_unit_price, today)
        except Exception as e:
            print(f"❌ Migros Hatası: {e}")


        #try:
            #scrape_a101(driver, all_products, clean_price, extract_unit_price, today)
        #except Exception as e:
            #print(f"❌ A101 Hatası: {e}")

    except Exception as main_e:
        print(f"❌ Genel Hata: {main_e}")

    finally:
        driver.quit()

        if all_products:
            save_to_csv(all_products)
            print("✅ İşlem Başarıyla Tamamlandı.")
        else:
            print("⚠️ Hiç veri toplanmadı.")