@echo off
:: 1. Proje klasörüne git (Burayı kendi bilgisayarındaki yolla değiştirmen gerekecek)
cd /d "C:\Users\emrec\PycharmProjects\InflationMonitor"

:: 2. Sanal ortamdaki Python ile main.py'yi çalıştır
:: Eğer venv klasörün projenin içindeyse yol şöyledir:
".venv\Scripts\python.exe" main.py

:: Hata varsa pencere kapanmasın, görelim (Opsiyonel)
timeout /t 10