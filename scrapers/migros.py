import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def scrape_migros(driver, products_list, clean_price_func, unit_price_func, today_date):
    print("\n🟠 --- MİGROS TARANIYOR (Tam Liste & Çoklu Sayfa) ---")

    CATEGORIES = [
        {"name": "Süt", "url": "https://www.migros.com.tr/sut-c-6c"},
        {"name": "Ayçiçek Yağı", "url": "https://www.migros.com.tr/aycicek-yagi-c-42d"},
        {"name": "Yumurta", "url": "https://www.migros.com.tr/yumurta-c-70"},
        {"name": "Tavuk Eti", "url": "https://www.migros.com.tr/pilic-c-3fe"},
        {"name": "Dana Eti", "url": "https://www.migros.com.tr/dana-eti-c-3fa"},
        {"name": "Balık", "url": "https://www.migros.com.tr/mevsim-baliklari-c-402"},
        {"name": "Bebek Bezi", "url": "https://www.migros.com.tr/bebek-bezleri-c-1117a"},
        {"name": "Bakliyat", "url": "https://www.migros.com.tr/bakliyat-c-428"},
        {"name": "Çay", "url": "https://www.migros.com.tr/dokme-cay-c-28c1"},
    ]

    for cat in CATEGORIES:
        try:
            print(f"   🌍 Gidiliyor: {cat['name']}")
            page = 1

            while True:
                # DÜZELTME 1: URL yapısı '?sayfa=' olmalı
                target_url = f"{cat['url']}?sayfa={page}"
                driver.get(target_url)

                print(f"      📄 Sayfa {page} taranıyor...")

                try:
                    # Kartların yüklenmesini bekle
                    WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.TAG_NAME, "mat-card")))
                    time.sleep(2)  # Sayfanın oturması için
                except:
                    print(f"      🏁 {cat['name']} tamamlandı (Sayfa {page}'de ürün yok).")
                    break

                # DÜZELTME 2: 'cards' tanımlandıktan sonra işlem yapılıyor
                cards = driver.find_elements(By.TAG_NAME, "mat-card")

                if len(cards) == 0:
                    print(f"      🏁 Ürün kalmadı, diğer kategoriye geçiliyor.")
                    break

                print(f"      📍 {len(cards)} ürün bulundu.")

                for card in cards:
                    try:
                        name = card.find_element(By.CSS_SELECTOR, "h3, h4, .product-name").text.strip()

                        price_text = ""
                        try:
                            price_text = card.find_element(By.CSS_SELECTOR, ".sale-price").text
                        except:
                            try:
                                price_text = card.find_element(By.CSS_SELECTOR, ".amount, .price").text
                            except:
                                continue

                        price = clean_price_func(price_text)
                        if not price: continue

                        unit_price = unit_price_func(name, price)
                        products_list.append([today_date, "Migros", cat['name'], name, price, unit_price, "TL"])
                    except:
                        continue

                # DÜZELTME 3: Sayfa sayısını artırıyoruz!
                page += 1

        except Exception as e:
            print(f"   ⚠️ Hata: {e}")