import os
import re
import json
import time
import webbrowser
import urllib.parse
import urllib.request
import ctypes
from dotenv import load_dotenv

import telebot
import pyautogui
import pygetwindow as gw
import pyperclip
from google import genai
from google.genai import types

# Memuat konfigurasi dari file .env (menggunakan path absolut agar selalu terbaca)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))

# ==========================================
# 1. KONFIGURASI BOT & GEMINI API
# ==========================================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("⚠️ TELEGRAM_BOT_TOKEN belum diset di file .env!")
bot = telebot.TeleBot(TOKEN)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("⚠️ GEMINI_API_KEY belum diset di file .env!")
client = genai.Client(api_key=GEMINI_API_KEY)


# ==========================================
# 2. FUNGSI KENDALI GOOGLE CHROME
# ==========================================
def fokus_chrome():
    """Membawa jendela Chrome ke fokus paling depan tanpa crash oleh bug Windows."""
    try:
        chrome_windows = [w for w in gw.getWindowsWithTitle('Chrome') if w.visible]
        if chrome_windows:
            win = chrome_windows[0]
            try:
                if win.isMinimized:
                    win.restore()
            except Exception:
                pass

            # Coba activate, tangani bug khas pygetwindow di Windows
            try:
                win.activate()
            except Exception:
                try:
                    ctypes.windll.user32.ShowWindow(win._hWnd, 9)  # SW_RESTORE
                    ctypes.windll.user32.SetForegroundWindow(win._hWnd)
                except Exception:
                    pass

            time.sleep(0.3)
            return True
    except Exception as e:
        print(f"⚠️ Peringatan fokus Chrome: {e}")
    return False

def buka_di_chrome(url):
    """Membuka atau mengganti URL pada tab aktif Chrome."""
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    if not fokus_chrome():
        webbrowser.open(url)
        return

    # Copy URL ke clipboard lalu tempel ke Address Bar (Alt + D)
    pyperclip.copy(url)
    pyautogui.hotkey('alt', 'd')
    time.sleep(0.2)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.1)
    pyautogui.press('enter')

def cari_video_id_youtube(query):
    """Mencari video ID teratas di YouTube agar langsung memutar videonya (autoplay)."""
    try:
        query_encoded = urllib.parse.quote(query)
        url_search = f"https://www.youtube.com/results?search_query={query_encoded}"
        req = urllib.request.Request(
            url_search,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        html = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
        video_ids = re.findall(r"watch\?v=(\S{11})", html)
        if video_ids:
            return f"https://www.youtube.com/watch?v={video_ids[0]}"
    except Exception as e:
        print(f"⚠️ Gagal mencari direct URL YouTube: {e}")
    return f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"

def putar_youtube(query_atau_url):
    """Memutar video YouTube langsung ke halaman video pemutaran."""
    if "youtube.com/watch" in query_atau_url or "youtu.be" in query_atau_url:
        url_tujuan = query_atau_url
    else:
        url_tujuan = cari_video_id_youtube(query_atau_url)

    buka_di_chrome(url_tujuan)

def aksi_shortcut_chrome(perintah):
    """Mengendalikan navigasi tab Chrome dengan tombol keyboard."""
    ada_chrome = fokus_chrome()

    perintah = (perintah or "").upper()
    if perintah == "TAB_BARU":
        if ada_chrome:
            pyautogui.hotkey('ctrl', 't')
        else:
            webbrowser.open('https://google.com')
    elif perintah == "TUTUP_TAB":
        if ada_chrome:
            pyautogui.hotkey('ctrl', 'w')
    elif perintah == "REFRESH":
        if ada_chrome:
            pyautogui.press('f5')
    elif perintah == "SCROLL_DOWN":
        if ada_chrome:
            pyautogui.press('pagedown')
    elif perintah == "SCROLL_UP":
        if ada_chrome:
            pyautogui.press('pageup')
    return True


# ==========================================
# 3. ANALISIS PERINTAH DENGAN GEMINI AI
# ==========================================
def analisa_perintah_gemini(teks_user):
    prompt = f"""
Kamu adalah asisten kontrol PC Windows dan pengendali Google Chrome.
Analisis maksud/instruksi pengguna berikut: "{teks_user}"

Kategori Action yang tersedia:
1. BUKA_URL: Jika meminta membuka website/link (contoh: "buka youtube", "buka chatgpt", "buka detik.com", "buka https://...")
   - Isi 'target_url' dengan URL yang valid.
2. PUTAR_YOUTUBE: Jika meminta memutar/mendengarkan musik/video tertentu (contoh: "putar lagu lofi", "tonton tutorial python", "stel video X")
   - Isi 'target_url' dengan judul video/lagu atau link YouTube.
3. KENDALI_CHROME: Jika meminta aksi navigasi Chrome:
   - "tutup tab" -> sub_action: "TUTUP_TAB"
   - "buka tab baru" -> sub_action: "TAB_BARU"
   - "refresh / muat ulang" -> sub_action: "REFRESH"
   - "scroll ke bawah" -> sub_action: "SCROLL_DOWN"
   - "scroll ke atas" -> sub_action: "SCROLL_UP"
4. MATIKAN_LAPTOP: Jika meminta shutdown / matikan laptop.
5. RESTART_LAPTOP: Jika meminta restart / nyalakan ulang laptop.
6. BATALKAN_SHUTDOWN: Jika meminta batal matikan / cancel shutdown.
7. CHAT_BIASA: Jika hanya menyapa atau mengobrol biasa. Isi 'balasan_chat'.

Format Respon JSON Wajib:
{{
  "action": "BUKA_URL | PUTAR_YOUTUBE | KENDALI_CHROME | MATIKAN_LAPTOP | RESTART_LAPTOP | BATALKAN_SHUTDOWN | CHAT_BIASA",
  "target_url": "",
  "sub_action": "",
  "balasan_chat": ""
}}
"""
    try:
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=1024
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"⚠️ Error Gemini API: {e}")
        # Fallback manual jika API ada kendala
        teks = teks_user.lower()
        if "mati" in teks or "shutdown" in teks:
            return {"action": "MATIKAN_LAPTOP"}
        elif "restart" in teks:
            return {"action": "RESTART_LAPTOP"}
        elif "batal" in teks:
            return {"action": "BATALKAN_SHUTDOWN"}
        elif "buka" in teks:
            url = teks.replace("buka", "").strip()
            return {"action": "BUKA_URL", "target_url": url}
        return {"action": "CHAT_BIASA", "balasan_chat": "Maaf, sistem AI sedang offline sebentar."}


# ==========================================
# 4. HANDLER TELEGRAM (TANPA TRIGGER)
# ==========================================
@bot.message_handler(func=lambda message: True)
def handle_semua_pesan(message):
    teks = (message.text or "").strip()
    if not teks:
        return

    print(f"\n[Pesan Diterima]: {teks}")
    try:
        hasil = analisa_perintah_gemini(teks)

        # Tangani jika Gemini memberikan multi-aksi (list) atau aksi tunggal (dict)
        daftar_aksi = hasil if isinstance(hasil, list) else [hasil]

        for item in daftar_aksi:
            if not isinstance(item, dict):
                continue

            aksi = item.get("action")
            target_url = item.get("target_url", "")
            sub_action = item.get("sub_action", "")
            balasan = item.get("balasan_chat", "")
            print(f"[Aksi Dipilih]: {aksi} (Detail: {target_url or sub_action})")

            # --- KONTROL SISTEM LAPTOP ---
            if aksi == "MATIKAN_LAPTOP":
                bot.reply_to(message, "🔌 *Laptop akan dimatikan dalam 30 detik!* \nKetik `batal` untuk membatalkan.", parse_mode="Markdown")
                os.system("shutdown /s /t 30")

            elif aksi == "RESTART_LAPTOP":
                bot.reply_to(message, "🔄 *Laptop akan di-restart dalam 10 detik...*", parse_mode="Markdown")
                os.system("shutdown /r /t 10")

            elif aksi == "BATALKAN_SHUTDOWN":
                os.system("shutdown /a")
                bot.reply_to(message, "✅ *Proses shutdown/restart berhasil dibatalkan!*")

            # --- KENDALI CHROME ---
            elif aksi == "PUTAR_YOUTUBE":
                bot.reply_to(message, f"🎬 *YouTube:* Memutar `{target_url}`...", parse_mode="Markdown")
                putar_youtube(target_url)

            elif aksi == "BUKA_URL":
                bot.reply_to(message, f"🌐 *Chrome:* Membuka `{target_url}`...", parse_mode="Markdown")
                buka_di_chrome(target_url)

            elif aksi == "KENDALI_CHROME":
                aksi_shortcut_chrome(sub_action)
                bot.reply_to(message, f"⚡ *Chrome:* Aksi `{sub_action}` dieksekusi.")

            # --- CHAT BIASA ---
            elif aksi == "CHAT_BIASA":
                bot.reply_to(message, balasan if balasan else "Ada yang bisa saya bantu?")
    except Exception as e:
        print(f"❌ Error saat memproses pesan: {e}")
        bot.reply_to(message, f"⚠️ Maaf, ada kendala: {e}")


# ==========================================
# 5. MENJALANKAN BOT
# ==========================================
if __name__ == "__main__":
    print("===================")
    print("Bot Sistem Standby!")
    print("===================")

    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=30, skip_pending=True)
        except KeyboardInterrupt:
            print("\n[Sistem]: Bot dihentikan (Ctrl+C).")
            break
        except Exception as e:
            print(f"⚠️ Terjadi error: {e}. Menghubungkan ulang dalam 5 detik...")
            time.sleep(5)