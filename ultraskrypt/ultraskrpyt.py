from typing import List
import requests
from datetime import datetime, timedelta
import time
import os
import tldextract
import json


ignored_count = 0
not_in_hole = 0

def load_config(config_file):
    """
    Wczytuje konfigurację z pliku JSON.
    """
    with open(config_file, 'r', encoding='utf-8') as file:
        return json.load(file)

def fetch_domains_from_virustotal_v3(api_key, ip_address):
    all_domains = []
    cursor = ""
    limit = 40
    zilu = 9999

    today = datetime.now()
    yesterday = today - timedelta(days=zilu)

    print(f"\n=== Virustotal: Fetching domains for IP {ip_address} ===")

    while True:
        headers = {"x-apikey": api_key}
        url = f"https://www.virustotal.com/api/v3/ip_addresses/{ip_address}/resolutions"
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor

        try:
            response = requests.get(url, headers=headers, params=params)

            if response.status_code == 200:
                result = response.json()
                data = result.get("data", [])

                if not data:
                    print("\nVirustotal: No more results found.")
                    break

                # Filter domains by date range
                for entry in data:
                    hostname = entry.get("attributes", {}).get("host_name", "")
                    if hostname:
                        all_domains.append(hostname)

                print(f"\nVirustotal: Fetched {len(all_domains)} domains so far...")

                # Next cursor?
                cursor = result.get("meta", {}).get("cursor")
                if not cursor:
                    print("\nVirustotal: Reached end of results - no more cursor.")
                    break

                time.sleep(0.5)  # API rate limiting

            elif response.status_code == 404:
                print("\nVirustotal: No data for this IP.")
                break
            elif response.status_code == 429:
                print("\n !!!! Virustotal: Rate limit exceeded. Breaking cycle... !!!!")
                time.sleep(1)
                break
            else:
                print(f"\nVirustotal: Request failed: {response.status_code} - {response.text}")
                break

        except requests.RequestException as e:
            print(f"\nVirustotal: Request failed: {e}")
            break

    print(f"\n=== VirusTotal: Total domains found for {ip_address}: {len(all_domains)} ===")
    if all_domains:
        return all_domains


def save_domains(urlscan_domains,virustotal_domains,ignored):
    all_domains = urlscan_domains + virustotal_domains
    global ignored_count
    global not_in_hole

    # Save all domains
    with open("all_v3.txt", "a", encoding="utf-8") as file:
        for domain in all_domains:
            file.write(domain + "\n")

    # Save new (non-listed) domains
    cert_polska_list = fetch_cert_polska_list()
    headers = {
        'Accept': 'application/json',
    }
    cert_polska_tlds = {extract_tld(domain) for domain in cert_polska_list}
    written_tlds = set()
    with open("new_v3.txt", "a", encoding="utf-8") as file:
        for domain in all_domains:
            tld = extract_tld(domain)
            if tld not in cert_polska_tlds and tld not in written_tlds:
                not_in_hole += 1
                if domain not in ignored:
                    file.write(f"{domain}\n")
                    written_tlds.add(tld)
                else:
                    ignored_count += 1





def fetch_results_urlscan(api_key_url: str, ip_address: str, search_after: str = None):
    """
    Pobiera wyniki z API URLScan dla danego IP.
    Wykorzystuje datasource "hostnames" oraz filtr tagów (apexdomain) i IP.
    """
    url = f'https://urlscan.io/api/v1/search?datasource=hostnames&q=tags%3Aapexdomain%20AND%20ip%3A%22{ip_address}%22'
    headers = {"API-Key": api_key_url}
    if search_after:
        full_url = f'{url}&search_after={search_after}&size=10000'
    else:
        full_url = f'{url}&size=10000'
    response = requests.get(full_url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"UrlScan: Error fetching results: {response.status_code}")
        return None

def fetch_domains_from_urlscan(urlscan_api_key,ip):
    all_domains = []

    print(f"\n=== UrlScan: Fetching domains for IP {ip} ===")
    while True:
        data = fetch_results_urlscan(urlscan_api_key, ip)
        if not data:
            print(f"\n=== UrlScan: No more data ===")
            break
        results = data.get("results", [])
        if not results:
            print("UrlScan: No results")
            break
        for item in results:
            domain = item.get("domain")
            if domain:
                all_domains.append(domain)
        if data.get("has_more") and data.get("search_after"):
            print(f"\nUrlScan: Fetech {len(all_domains)} domains so far...")
            search_after = data.get("search_after")
        else:
            break
    print(f"\n === UrlScan: Total domains retrieved: {len(all_domains)} === ")
    return all_domains




def fetch_cert_polska_list() -> List[str]:
    try:
        response = requests.get("https://hole.cert.pl/domains/v2/domains.txt", timeout=15)
        response.raise_for_status()
        return response.text.split("\n")
    except requests.RequestException:
        print("Failed to fetch CERT Polska domain list.")
        return []



def read_ignore_file():
    ignored = []
    try:
        with open("ignore.txt", "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line.startswith("http://") or line.startswith("https://"):
                    line = line.split("//")[1]
                ignored.append(line)
    except FileNotFoundError:
        print("ignore.txt not found — continuing without ignore list.")
    return ignored

def extract_tld(domain):
    ext = tldextract.extract(domain)
    return f"{ext.domain}.{ext.suffix}"


def read_ip_list(filename="ips.txt"):
    ips = []
    try:
        with open(filename, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith("#"):  # ignore empty lines and comments
                    ips.append(line)
    except FileNotFoundError:
        print(f"{filename} not found! Please create it and add IP addresses (one per line).")
    return ips


def main():
    config = load_config("../scripts_config.json")
    api_key_VT = config['api_key_VT']
    api_key_SC = config['api_key_SC']

    ignore = read_ignore_file()
    ip_list = read_ip_list()

    if not ip_list:
        print("No IPs to check. Exiting.")
        return

    # Clear output files before writing
    if os.path.exists("all_v3.txt"):
        os.remove("all_v3.txt")
    if os.path.exists("new_v3.txt"):
        os.remove("new_v3.txt")

    for ip in ip_list:
        print(f"\n=== Checking IP {ip} ===")
        VTdomains = fetch_domains_from_virustotal_v3(api_key_VT, ip)
        USdomains = fetch_domains_from_urlscan(api_key_SC,ip)
        save_domains(VTdomains,USdomains,ignore)
        print(f"Finished IP {ip}\n{'-'*50}")

    print(f"\nAll IPs processed. Ignored domains total: {ignored_count}")
    print("Results saved to all_v3.txt and new_v3.txt.")
    print(f"{not_in_hole} domen nieobecnych na liście CERT.")
    print("Pozostalo do sprawdzenia: ", (not_in_hole - ignored_count))


if __name__ == "__main__":
    main()
