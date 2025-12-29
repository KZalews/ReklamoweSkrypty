from urllib.parse import urlparse

# Pliki wejścia i wyjścia
INPUT_FILE = "poprawne.txt"
OUTPUT_FILE = "output.txt"

def extract_base_url(url):
    """
    Pobiera protokół + domenę z linku.
    Np.: https://example.com/abcd?x=1 -> h
ttps://example.com
    """
    parsed = urlparse(url.strip())
    return f"{parsed.scheme}://{parsed.netloc}"

def main():
    seen_domains = set()

    with open(INPUT_FILE, "r", encoding="utf-8") as f_in, \
         open(OUTPUT_FILE, "w", encoding="utf-8") as f_out:

        for line in f_in:
            url = line.strip()
            if not url:
                continue

            base = extract_base_url(url)

            if base not in seen_domains:
                seen_domains.add(base)
                f_out.write(url + "\n")  # zapisuje pełny link pierwszy raz

    print("Gotowe! Wynik zapisany do output.txt")

if __name__ == "__main__":
    main()
