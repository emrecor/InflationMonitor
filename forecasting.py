import pandas as pd
from prophet import Prophet
import psycopg2


def get_product_data(product_name, db_params):
    """
    Seçilen ürünün geçmiş fiyat verilerini veritabanından çeker.
    Prophet formatına (ds: tarih, y: değer) uygun hale getirir.
    """
    try:
        conn = psycopg2.connect(**db_params)
        # SQL Injection riskine karşı parametreli sorgu
        query = "SELECT date, price FROM prices WHERE product_name = %s ORDER BY date"
        df = pd.read_sql(query, conn, params=(product_name,))
        conn.close()

        if df.empty:
            return None

        # Prophet sütun isimlerini 'ds' (tarih) ve 'y' (hedef) olarak ister
        df = df.rename(columns={"date": "ds", "price": "y"})
        df["ds"] = pd.to_datetime(df["ds"])
        return df
    except Exception as e:
        print(f"Hata: {e}")
        return None


def predict_price(product_name, days, db_params):
    """
    Verilen ürün için Prophet modelini eğitir ve 'days' kadar sonrasını tahmin eder.
    """
    df = get_product_data(product_name, db_params)

    # 1. Veri Kontrolü: Modelin çalışması için en azından 5-10 günlük veri lazım
    if df is None or len(df) < 5:
        return None, "⚠️ Yetersiz Veri: Tahmin için bu ürüne ait en az 5 günlük geçmiş veri gerekiyor."

    # 2. Modeli Başlat ve Eğit
    try:
        # daily_seasonality=True: Günlük verimiz olduğu için açıyoruz
        model = Prophet(daily_seasonality=True, yearly_seasonality=False, weekly_seasonality=False)
        model.fit(df)

        # 3. Gelecek Tarihleri Oluştur
        future = model.make_future_dataframe(periods=days)

        # 4. Tahmin Yap
        forecast = model.predict(future)

        # Sadece ihtiyacımız olan sütunları döndür
        return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']], None

    except Exception as e:
        return None, f"Model Hatası: {e}"