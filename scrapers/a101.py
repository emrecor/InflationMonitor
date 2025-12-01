import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def scrape_a101(driver, products_list, clean_price_func, unit_price_func, today_date):
    print("\n🟠 --- A101 TARANIYOR (Tam Liste & Adım Adım Scroll) ---")

    # 1. KATEGORİ LİSTESİ DÜZELTİLDİ
    # Not: Python listesi içinde """...""" kullanırsanız o bir string eleman olur ve kodunuz patlar.
    # Bu yüzden pasif kategorileri '#' ile yorum satırı yaptım veya aktif bıraktım.
    CATEGORIES = [
        {"name": "Süt", "url": "https://www.a101.com.tr/kapida/search?query=s%C3%BCt"},
        {"name": "Ayçiçek Yağı",
         "url": "https://www.a101.com.tr/kapida/search?query=Ay%C3%A7i%C3%A7ek%20Ya%C4%9F%C4%B1"},
        {"name": "Yumurta", "url": "https://www.a101.com.tr/kapida/search?query=yumurta"},
        {"name": "Tavuk Eti", "url": "https://www.a101.com.tr/kapida/search?query=Beyaz%20Et"},
        {"name": "Dana Eti", "url": "https://www.a101.com.tr/kapida/search?query=K%C4%B1rm%C4%B1z%C4%B1%20Et"},
        {"name": "Balık", "url": "https://www.a101.com.tr/kapida/search?query=Deniz%20%C3%9Cr%C3%BCnleri"},
        {"name": "Bebek Bezi", "url": "https://www.a101.com.tr/kapida/search?query=Bebek%20Bezi"},
        {"name": "Bakliyat", "url": "https://www.a101.com.tr/kapida/search?query=Bakliyat"},
        {"name": "Çay", "url": "https://www.a101.com.tr/kapida/search?query=%C3%87ay"}
    ]

    # Aynı ürünleri tekrar eklememek için bir havuz (Set) oluşturuyoruz
    added_product_names = set()

    for cat in CATEGORIES:
        # Hata önleyici: Eğer liste içinde string kalmışsa atla
        if not isinstance(cat, dict):
            continue

        try:
            print(f"   🌍 Gidiliyor: {cat['name']}")
            driver.get(cat['url'])

            # İlk ürünlerin yüklenmesini bekle
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.w-full.border.cursor-pointer.rounded-2xl"))
                )
            except:
                print(f"      ⚠️ {cat['name']} kategorisinde ürün bulunamadı veya geç yüklendi.")
                continue

            # --- DÖNGÜ BAŞLANGICI ---
            # Sayfa sonuna kadar yavaş yavaş inip toplayacağız
            while True:
                # 1. Şu an ekranda (ve DOM'da) olan kartları bul
                cards = driver.find_elements(By.CSS_SELECTOR, "div.w-full.border.cursor-pointer.rounded-2xl")

                for card in cards:
                    try:
                        # İsim Alma
                        name = card.find_element(By.CSS_SELECTOR, "div.line-clamp-3").text.strip()

                        # DUPLICATE KONTROLÜ: Eğer bu ürünü zaten eklediysek atla
                        if name in added_product_names:
                            continue

                        # Fiyat Alma
                        try:
                            price_text = card.find_element(By.CSS_SELECTOR,
                                                           ".text-md.absolute.bottom-0.font-medium").text
                        except:
                            continue  # Fiyat yoksa (stokta yok vs.) atla

                        price = clean_price_func(price_text)
                        if not price: continue

                        # Birim Fiyat
                        unit_price = unit_price_func(name, price)

                        # LİSTEYE EKLE
                        # Not: "Migros" yazmışsınız, burası A101 fonksiyonu olduğu için "A101 Kapıda" yaptım.
                        products_list.append([today_date, "A101 Kapıda", cat['name'], name, price, unit_price, "TL"])

                        # Set'e kaydet ki bir daha eklemeyelim
                        added_product_names.add(name)
                        print(f"      ✅ Eklendi ({len(added_product_names)}): {name} - {price} TL")

                    except Exception as e:
                        # Tekil kart hatası (reklam bannerı vs.)
                        continue

                # 2. SCROLL İŞLEMİ (Aşağı Doğru Kaydır)
                # Sayfa sonunu kontrol et
                prev_height = driver.execute_script("return document.body.scrollHeight")
                current_scroll = driver.execute_script("return window.pageYOffset + window.innerHeight")

                # Eğer sayfanın en altındaysak döngüyü kır
                if current_scroll >= prev_height:
                    print(f"   🏁 {cat['name']} bitti. Toplam ürün: {len(added_product_names)}")
                    break

                # Değilse, 500 piksel aşağı kaydır ve bekle
                driver.execute_script("window.scrollBy(0, 500);")
                time.sleep(1.5)  # Yükleme süresi (İnternet yavaşsa 2.5 yapın)

            # Bir sonraki kategoriye geçerken duplicate havuzunu temizlemek isterseniz:
            # added_product_names.clear()
            # (Tavsiye: Temizlemeyin, böylece farklı kategorilerde çıkan aynı ürünleri tekrar eklemezsiniz)

        except Exception as e:
            print(f"   ⚠️ Kategori Genel Hatası ({cat.get('name', 'Bilinmiyor')}): {e}")