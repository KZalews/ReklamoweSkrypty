import requests
import os
import json
import re
import csv
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from datetime import datetime, timedelta, UTC
import time

API_VERSION = "v19.0"
TOKEN_PATH = r"access_token.txt"
INPUT_FILE = "input2.txt"
FINAL_OUTPUT_FILE = "output_final.txt"

# 🔥 Przełącznik - ustaw na False aby pominąć Selenium (domyślnie True)
RUN_SELENIUM = True


def get_date_14_days_ago():
    today = datetime.now(UTC)
    two_weeks_ago = today - timedelta(days=14)
    return two_weeks_ago.strftime("%Y-%m-%d")

# ---------- Token ----------
def load_access_token():
    if not os.path.exists(TOKEN_PATH):
        raise FileNotFoundError(f"Nie znaleziono pliku z tokenem: {TOKEN_PATH}")

    with open(TOKEN_PATH, "r", encoding="utf-8") as f:
        token = f.read().strip()

    if not token:
        raise ValueError("Plik z tokenem jest pusty")

    print("🔑 Token wczytany")
    return token


# ---------- Ad Library Search z retry na 500 ----------
def search_ad_library(profile_name, access_token, max_retries=3):
    url = f"https://graph.facebook.com/{API_VERSION}/ads_archive"
    date_min = get_date_14_days_ago()
    params = {
        "search_terms": profile_name,
        "ad_type": "ALL",
        "ad_reached_countries": '["PL"]',
        "ad_active_status": "ACTIVE",
        "fields": "page_id,page_name",
        "ad_delivery_date_min": date_min,
        "limit":1300,
        "access_token": access_token
    }

    print(f"\n🔎 Szukam: \"{profile_name}\"")

    for attempt in range(max_retries):
        try:
            r = requests.get(url, params=params)
            print(f"STATUS: {r.status_code} (attempt {attempt + 1}/{max_retries})")

            if r.status_code == 500:
                print("⚠️  ERROR 500 - czekam 1s i próbuję ponownie...")
                time.sleep(1)
                continue

            try:
                print("Odpowiedź skrócona:",
                      json.dumps(r.json().get("data", []), indent=2)[:500])
            except:
                print(r.text)

            r.raise_for_status()

            pages = {}
            for ad in r.json().get("data", []):
                page_id = ad.get("page_id")
                page_name = ad.get("page_name")
                if page_id and page_name:
                    pages[page_id] = page_name

            return pages

        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                print(f"⚠️  Błąd {str(e)[:50]} - próbuję ponownie za 1s...")
                time.sleep(1)
            else:
                print(f"❌ Maksymalna liczba prób ({max_retries}) przekroczona")
                return {}

    return {}


# ---------- Normalizacja nazw ----------
def normalize_name(name):
    name = name.lower()
    name = re.sub(r'[\s\-_]', '', name)
    return name


def is_exact_match(input_name, found_name):
    n1 = normalize_name(input_name)
    n2 = normalize_name(found_name)
    print(f"   🔍 Porównanie: {n1} vs {n2}")
    return n1 == n2


# ---------- Selenium funkcje ----------
def get_base_image_url(full_url):
    if not full_url:
        return ""
    clean_url = re.sub(r'^\[|\]$', '', full_url.strip())
    base_url = clean_url.split('?')[0].strip()
    base_url = ''.join(base_url.split())
    return base_url


def process_profile(args):
    name, profile_url, input_avatar_url, driver = args

    try:
        print(f"Processing {name}: {profile_url}")
        driver.get(profile_url)
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)

        page_avatar_url = None

        selectors = [
            "//div[contains(@class,'x15sbx0n')]//svg//*[local-name()='image'][contains(@xlink:href,'scontent')]",
            "//div[contains(@class,'x1jx94hy')]//svg//*[local-name()='image']",
            "//*[local-name()='svg' and contains(@style,'168px')]//*[local-name()='image']",
            "//a[contains(@aria-label,'Forum') or contains(@aria-label,'Profile')]//svg//*[local-name()='image']"
        ]

        for selector in selectors:
            try:
                img_elem = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                page_avatar_url = img_elem.get_attribute('xlink:href') or img_elem.get_attribute('href')
                if page_avatar_url:
                    print(f"  ✓ XPath found: {selector[:40]}...")
                    break
            except:
                continue

        if not page_avatar_url:
            page_avatar_urls = driver.execute_script("""
                var svgs = document.querySelectorAll('svg[style*="168px"] image[xlink\\:href*="scontent"], 
                                                     svg[style*="168px"] image[href*="scontent"]');
                return Array.from(svgs).map(img => 
                    img.getAttribute('xlink:href') || img.getAttribute('href')).filter(Boolean);
            """)

            if page_avatar_urls:
                page_avatar_url = page_avatar_urls[0]
                print(f"  ✓ JS SVG 168px found!")

        if not page_avatar_url:
            all_images = driver.execute_script("""
                var imgs = document.querySelectorAll('svg image[xlink\\:href*="scontent"], 
                                                     svg image[href*="scontent"], 
                                                     img[src*="scontent"]');
                return Array.from(imgs).map(img => 
                    img.getAttribute('xlink:href') || img.getAttribute('href') || img.getAttribute('src'))
                    .filter(url => url && url.includes('scontent'));
            """)
            page_avatar_url = all_images[0] if all_images else None
            if page_avatar_url:
                print(f"  ✓ Universal scontent found!")

        if not page_avatar_url:
            print(f"  ❌ NO AVATAR for {name}")
            return None

        print(f"  📸 Found RAW:  {repr(page_avatar_url)[:120]}...")
        print(f"  📸 Input RAW:  {repr(input_avatar_url)[:120]}...")

        base_page = get_base_image_url(page_avatar_url)
        base_input = get_base_image_url(input_avatar_url)

        print(f"  🔍 Page clean:  {repr(base_page)[-80:]}")
        print(f"  🔍 Input clean: {repr(base_input)[-80:]}")
        print(f"  🔍 Lengths:     {len(base_page)} vs {len(base_input)}")

        if base_page == base_input:
            print(f"  ✅ EXACT MATCH!")
            return profile_url
        elif (abs(len(base_page) - len(base_input)) <= 2 and
              base_page.replace('_n.jpg', '') == base_input.replace('_n.jpg', '')):
            print(f"  ✅ FUZZY MATCH! (len diff)")
            return profile_url
        elif base_page[-20:] == base_input[-20:]:
            print(f"  ✅ END MATCH! (tail)")
            return profile_url
        else:
            print(f"  ❌ No match")
            return None

    except Exception as e:
        print(f"  ❌ Error {name}: {str(e)[:50]}")
        return None


# ---------- GŁÓWNA FUNKCJA ----------
def main():
    print("🚀 === URUCHOMIENIE POŁĄCZONEGO SKRYPTU ===")
    print(f"🔧 RUN_SELENIUM = {RUN_SELENIUM}")

    # CZĘŚĆ 1: Facebook API Search (ZAWSZE się wykonuje)
    print("\n📡 CZĘŚĆ 1: Wyszukiwanie przez Facebook Ads API")
    access_token = load_access_token()

    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(f"Nie znaleziono pliku: {INPUT_FILE}")

    all_results = {}
    temp_output_file = "output2_temp.txt"

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                profile_name, avatar_link = line.split(",", 1)
                profile_name = profile_name.strip()
                avatar_link = avatar_link.strip()

                pages = search_ad_library(profile_name, access_token)

                for page_id, page_name in pages.items():
                    if is_exact_match(profile_name, page_name):
                        all_results[page_id] = (page_name, avatar_link)
                    else:
                        print("   ❌ Odrzucono – nazwa różna")

            except ValueError:
                print(f"⚠ Błędny format linii: {line}")

    # Zapis wyników części 1
    with open(temp_output_file, "w", encoding="utf-8") as out:
        for page_id, (page_name, avatar_link) in all_results.items():
            profile_url = f"https://www.facebook.com/profile.php?id={page_id}"
            out.write(f"{page_name},{profile_url},{avatar_link}\n")

    print(f"\n✅ CZĘŚĆ 1: Znaleziono {len(all_results)} profili → {temp_output_file}")

    # 🔥 CZĘŚĆ 2: Selenium verification (WARUNKOWO)
    if RUN_SELENIUM:
        print("\n🔍 CZĘŚĆ 2: Weryfikacja awatarów przez Selenium")

        # Ładowanie profili z tymczasowego pliku
        profiles = []
        with open(temp_output_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                parts = line.split(',', 2)
                if len(parts) == 3:
                    profiles.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))
                else:
                    print(f"⚠️ Skip line {line_num}: {line[:50]}...")

        print(f"✅ Załadowano {len(profiles)} profili do weryfikacji")

        # Konfiguracja Chrome
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-images')
        options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-plugins')
        options.add_argument('--log-level=3')

        driver = webdriver.Chrome(options=options)
        matching_profiles = []

        for i, profile in enumerate(profiles, 1):
            print(f"\n[{i}/{len(profiles)}] ", end="")
            result = process_profile((profile[0], profile[1], profile[2], driver))
            if result:
                matching_profiles.append(result)
            time.sleep(1.2)

        driver.quit()

        # Finałowy zapis (po Selenium) - czysty URL
        with open(FINAL_OUTPUT_FILE, 'w', encoding='utf-8') as f:
            for url in matching_profiles:
                f.write(url + '\n')

        print(f"\n🎉 === KOŃCOWY WYNIK (Selenium) === ")
        print(f"📊 {len(matching_profiles)}/{len(profiles)} matchy potwierdzonych!")
        print(f"💾 Zapisano do: {FINAL_OUTPUT_FILE}")

    else:
        # Jeśli Selenium wyłączone - zapisuj z markdown linkami (krótki text)
        print("\n⏭️  CZĘŚĆ 2: POMINIĘTA (RUN_SELENIUM=False)")
        print(f"💾 Zapis wyników części 1 z linkami → {FINAL_OUTPUT_FILE}")

        with open(FINAL_OUTPUT_FILE, 'w', encoding='utf-8') as f:
            for page_id, (page_name, avatar_link) in all_results.items():
                profile_url = f"https://www.facebook.com/profile.php?id={page_id}"
                f.write(profile_url + '\n')

        print(f"✅ Zakończono - {len(all_results)} profili z API → {FINAL_OUTPUT_FILE}")

    # Czyszczenie tymczasowego pliku
    if os.path.exists(temp_output_file):
        os.remove(temp_output_file)
        print(f"🧹 Usunięto plik tymczasowy: {temp_output_file}")


if __name__ == "__main__":
    main()
