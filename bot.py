import os
import time
from playwright.sync_api import sync_playwright
import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SAVED_COURSES_FILE = "saved_courses.txt"

# --- KULLANICI AYARLARI ---
# Aramak istediğin kursların anahtar kelimelerini buraya yaz (küçük/büyük harf duyarsız arar)
KEYWORDS = ["KALORİFER", "HAVUZ"] 

# Filtrelemek istediğin şehirleri buraya yaz (birebir tablodaki gibi yazılmalı)
TARGET_CITIES = ["İstanbul", "Eskişehir"]
# --------------------------

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials not found. Skipping message.")
        return
    
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Telegram API hatasi: {e}")

def get_saved_courses():
    if not os.path.exists(SAVED_COURSES_FILE):
        return set()
    with open(SAVED_COURSES_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

def save_course(course_id):
    with open(SAVED_COURSES_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{course_id}\n")

def main():
    saved_courses = get_saved_courses()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True) # MEB sertifika hatalarını yok say
        page = context.new_page()
        
        print("e-Yaygın sitesine bağlanılıyor...")
        # Site zaman zaman yavaş olabilir, timeout'u yüksek tutuyoruz
        page.goto("https://e-yaygin.meb.gov.tr/pageKurslar.aspx", timeout=60000)
        
        for keyword in KEYWORDS:
            print(f"\nAranan Anahtar Kelime: {keyword}")
            # Arama kutusuna kelimeyi yaz
            page.fill("input[name='txtKursAdi']", keyword)
            
            # Kursları Listele butonuna tıkla
            print("Kurslar listeleniyor...")
            page.click("button[name='btnSearch']")
            
            # Yükleme ekranının bitmesini bekle (RadAjaxManager div'inin güncellenmesi)
            time.sleep(5) # AJAX'ın bitmesi için güvenli bir bekleme süresi
            
            # Tabloyu oku
            rows = page.locator("table#rgKurslar_ctl00 tbody tr")
            count = rows.count()
            
            if count == 0 or (count == 1 and "bulunamadı" in rows.nth(0).inner_text().lower()):
                print(f"'{keyword}' için hiçbir kurs bulunamadı.")
                continue
                
            print(f"'{keyword}' için toplam {count} kayıt bulundu. Şehirlere göre filtreleniyor...")
            
            for i in range(count):
                row = rows.nth(i)
                cells = row.locator("td")
                
                # Sütun yapısı: 
                # 0: SNo, 1: Kurs No, 2: Kurs Adı, 3: İl, 4: İlçe, 5: Kurum, 6: Eğitim Şekli, 
                # 7: Yer, 8: Başlama, 9: Bitiş, 10: Süre, 11: Kontenjan, 12: Ders Planı, 13: Şartlar
                if cells.count() < 12:
                    continue
                    
                kurs_no = cells.nth(1).inner_text().strip()
                kurs_adi = cells.nth(2).inner_text().strip()
                il = cells.nth(3).inner_text().strip()
                ilce = cells.nth(4).inner_text().strip()
                kurum = cells.nth(5).inner_text().strip()
                egitim_sekli = cells.nth(6).inner_text().strip()
                baslama = cells.nth(8).inner_text().strip()
                bitis = cells.nth(9).inner_text().strip()
                kontenjan = cells.nth(11).inner_text().strip()
                
                # Hedef şehirlerden birinde mi?
                if il in TARGET_CITIES:
                    # Yeni bir kurs mu?
                    if kurs_no not in saved_courses:
                        print(f"YENİ KURS BULUNDU! ({il}) - {kurs_adi}")
                        
                        mesaj = (
                            f"🚨 <b>YENİ KURS BULUNDU!</b> 🚨\n\n"
                            f"📌 <b>{kurs_adi}</b>\n\n"
                            f"📍 <b>İl/İlçe:</b> {il} / {ilce}\n"
                            f"🏢 <b>Kurum:</b> {kurum}\n"
                            f"📅 <b>Tarih:</b> {baslama} - {bitis}\n"
                            f"👥 <b>Kontenjan:</b> {kontenjan}\n"
                            f"🏫 <b>Eğitim:</b> {egitim_sekli}\n"
                            f"🔢 <b>Kurs No:</b> {kurs_no}\n\n"
                            f"🔗 <a href='https://e-yaygin.meb.gov.tr/pageKurslar.aspx'>e-Yaygın Sistemine Git</a>"
                        )
                        
                        send_telegram_message(mesaj)
                        save_course(kurs_no)
                        saved_courses.add(kurs_no)
                    else:
                        print(f"Kurs zaten bildirilmiş (No: {kurs_no})")
        
        browser.close()

if __name__ == "__main__":
    main()
