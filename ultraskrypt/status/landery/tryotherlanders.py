"""
/cHcxw3pK?fbclid=IwY2xjawNkZlFleHRuA2FlbQIxMABicmlkETBTdUI0VVRpaXVuUVVvNHRCAR7sEJidQxpI7Ye9WungWvVg55NEigK9UYCZM7FICIF8b19uyOfHUibswFpWEQ_aem_ckHMpnRUBXFQN4rJsM2vcg&utm_campaign=247-PLPL2+-+FCS2&utm_source=fb&utm_placement={{placement}}&campaign_id={{campaign.id}}&adset_id={{adset.id}}&ad_id={{ad.id}}&adset_name={{adset.name}}&pixel=693638059872696&ad_name={{ad.name}}&utm_medium=Kashtan&utm_content=creo_news&funnel=FCS&utm_term=pl
/?media_type=video&pixel=3351623111635855&campaign_name=pl.palm1146.plmx%2Fs%2F&utm_source=120234185995440030&utm_content=pl7&ad_id=120234185995450030&placement=Facebook_Desktop_Feed&ad_campaign_id=mx1+-+Copy+2&access_token=EAAK96IsB0WoBPto1HPfEOFewOUiShsKZBkYZBHe4eUttAEA0KiYf5PXebQbL9DCdxb2L7jOksaYTZBi0vsXGcTg7R2xEvO2bEccnEUUYQVNyYmi1ZA4XndPPER2lOmH5DcSWjCBXnfKuT9t3GZB7UhHAXsvD8kkl1m1GBYzeMvsdQ7OfJ4dP4q4PodnKe6pXEgAZDZD&utm_medium=paid&utm_id=120234185891610030&utm_term=120234185995440030&utm_campaign=120234185891610030&fbclid=IwY2xjawNldNhleHRuA2FlbQEwAGFkaWQBqyha6_Y5HmJyaWQRME9vNVllOHdGMzZsaTFnZHkBHrg8KZUUnEn0dkYDrXUeSdkQzrsZBGD57OvCueuL_5lHTuFNx_48O1so-zpw_aem_P3gdZfN_N7hDhUp520Y1RQ
/?utm_creative={{ad.name}}&utm_campaign={{campaign.name}}&utm_source={{site_source_name}}&adset_name={{adset.name}}&pfb=1299449921377425&affid=LUX&utm_placement={{placement}}&fbclid=IwY2xjawNlf2xleHRuA2FlbQIxMABicmlkETB2WHJPODVzV2M0TTBZQlV2AR6UI7QDrBy075igIJjeK2w5mjS2f331f1Ps9vLKgyQ-xDwBym1n3dRlmrhkug_aem_W8_1r-CGHXksYQqumUtTBg
/lander/kwas-pensia-1_1762778285/index.html
/nKp5kz/
"""


import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from urllib.parse import urlparse

referer = ""

log_file_path = '../nf.txt'
OUTPUT_FILE = "poprawne.txt"
OUTPUT_FILE2 = "zblokowane.txt"
OUTPUT_FILE3 = "redirect.txt"
OUTPUT_FILE4 = "nf.txt"
aditional_urls = []

def check_url(index, url):
    """Sprawdza pojedynczy URL bez podążania za redirectami."""
    url = url.strip()
    blocked = False
    redirect = False
    nf = False
    global aditional_urls
    if not url:
        return None
    if not url.startswith("http"):
        url = "https://" + url  # dodaj protokół jeśli brakuje
    try:
        response = requests.get(url, timeout=5, allow_redirects=False, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            print(f"[{index}] [OK] {url}")
            return url, blocked, redirect, nf
        elif response.status_code == 403:
            print(f"[{index}] [Blocked] {url}")
            blocked = True
            return url, blocked, redirect, nf
        elif 300 <= response.status_code < 400:
            print(f"[{index}] [Redirect] {url} → {response.headers.get('Location', '')}")
            redirect = True
            return url, blocked, redirect, nf
        elif response.status_code == 404:
            print(f"[{index}] [Not Found] {url}")
            nf = True
            return url, blocked, redirect, nf
        else:
            print(f"[{index}] [!] {url} → status {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"[{index}] [X] {url} → błąd: {e}")
        return None

def read_urls_file(file_path):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
        uurls=[]
        urls = file.read().splitlines()
        for url in urls:
            uurls.append(to_base_url(url))
        return uurls

def read_referers_file(file_path):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
        referers = file.read().splitlines()
        return referers

def to_base_url(raw):
    raw = raw.strip()
    if not raw:
        return None

    # Dodaj https:// jeśli brak schematu, żeby urlparse zadziałał poprawnie
    has_scheme = "://" in raw
    to_parse = raw if has_scheme else "https://" + raw
    parsed = urlparse(to_parse)

    if not parsed.netloc:
        return None  # niepoprawny URL

    scheme = parsed.scheme or "https"
    netloc = parsed.netloc
    return f"{scheme}://{netloc}"

def main():
    # Path to your log file
    global log_file_path

    valid_urls = []
    blocked_url = []
    redirect_url = []
    nf_url = []

    # Clear output files at start
    if os.path.exists("poprawne.txt"):
        os.remove("poprawne.txt")
    if os.path.exists("zablokowane.txt"):
        os.remove("zablokowane.txt")
    if os.path.exists("redirect.txt"):
        os.remove("redirect.txt")
    if os.path.exists("nf.txt"):
        os.remove("nf.txt")

    # Extract and print the effective URLs
    urls2=[]
    urls = read_urls_file(log_file_path)
    print(urls)
    referers = read_referers_file("landers.txt")
    for referer in referers:
        #urls2 = [url + referer for url in urls]
        for url in urls:
            urls2.append(url+referer)

    if not urls2:
        print("❌ brak urli")
        return
    print(f"🔍 Sprawdzanie {len(urls)} adresów...")
    #return url, blocked, redirect, nf
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_url, i + 1, url): url for i, url in enumerate(urls2)}
        for future in as_completed(futures):
            result = future.result()
            if result and not result[1] and not result[2] and not result[3]:
                valid_urls.append(result[0])
            elif result and result[1] and not result[2] and not result[3]:
                blocked_url.append(result[0])
            elif result and not result[1] and result[2] and not result[3]:
                redirect_url.append(result[0])
            elif result and not result[1] and not result[2] and result[3]:
                nf_url.append(result[0])

    # Zapisz poprawne URL-e do pliku
    if valid_urls:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(valid_urls))
        print(f"\n✅ Zapisano {len(valid_urls)} poprawnych adresów do: {OUTPUT_FILE}")
    else:
        print("\n⚠️ Nie znaleziono żadnych poprawnych adresów.")

    if blocked_url:
        with open(OUTPUT_FILE2, "w", encoding="utf-8") as f:
            f.write("\n".join(blocked_url))
        print(f"\n✅ Zapisano {len(blocked_url)} zablokowanych adresów do: {OUTPUT_FILE2}")
    else:
        print("\n⚠️ Nie znaleziono żadnych zablokowanych adresów.")

    if nf_url:
        with open(OUTPUT_FILE4, "w", encoding="utf-8") as f:
            f.write("\n".join(nf_url))
        print(f"\n✅ Zapisano {len(nf_url)} not found do: {OUTPUT_FILE4}")
    else:
        print("\n⚠️ Nie znaleziono żadnych not found.")

    if redirect_url:
        with open(OUTPUT_FILE3, "w", encoding="utf-8") as f:
            f.write("\n".join(redirect_url))
        print(f"\n✅ Zapisano {len(redirect_url)} przekierowań do: {OUTPUT_FILE3}")
    else:
        print("\n⚠️ Nie znaleziono żadnych przekierowań.")

# Call the main function
if __name__ == "__main__":
    main()
