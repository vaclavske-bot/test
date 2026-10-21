"""Import in blocco da Open Food Facts -> pl.db.

Uso:
  python3 import_off.py --retailer conad --max-pages 5          # un'insegna
  python3 import_off.py --all --max-pages 20                    # tutte le insegne
  python3 import_off.py --fixture tests/off_fixture.json --dry-run   # prova offline
Opzioni: --dry-run (non scrive), --page-size N, --sleep SECONDI.
Login opzionale su Open Food Facts (le credenziali NON vanno scritte nel codice: il repo è pubblico):
  export OFF_USER=mio_utente OFF_PASSWORD='...'   # oppure --user mio_utente e la password viene chiesta da tastiera
  python3 import_off.py --retailer conad --user mio_utente
  --host it.openfoodfacts.org (predefinito) | world.openfoodfacts.org
Regole: non sovrascrive mai schede 'verificato'; completa solo i campi vuoti delle altre.
Dati OFF = collaborativi: tutto entra come 'da_verificare'.
"""
import argparse, getpass, http.cookiejar, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
import plants, server
from brands import RETAILERS, OWN_BRANDS

FIELDS = ("code,product_name,product_name_it,brands,stores,stores_tags,categories_tags,quantity,"
          "ingredients_text_it,ingredients_text,origins,origins_tags,manufacturing_places,emb_codes,link,countries_tags")

def plant_code(raw):
    """Bollo IT in forma canonica 'IT 3 74 CE' (anche alfanumerici, es. 'IT L2K7A CE'); None se assente.
    Richiede 'CE' esplicito per non scambiare altre sigle per un bollo."""
    if not re.search(r"\bIT\b.*\bCE\b", (raw or "").upper()): return None
    return plants.display(plants.canon(raw))

def origin_status(tags, text):
    t = {x.split(":")[-1] for x in (tags or [])}
    txt = (text or "").lower()
    if not t and not txt: return "non_dichiarata"
    eu = {"european-union", "ue", "eu"} & t or re.search(r"\b(ue|ue/non ue)\b|unione europea", txt)
    non = {"non-eu-agriculture", "non-eu", "non-ue"} & t or re.search(r"non[ -]?ue|extra[ -]?ue", txt)
    if eu and non: return "misto"
    if non: return "extra_ue"
    if t == {"italy"}: return "italia"
    if "italy" in t and len(t) > 1: return "misto"
    if eu: return "ue"
    # un solo paese UE diverso dall'Italia o altro: non classifico, lascio il testo
    return "non_dichiarata"

def retailer_of(p):
    tags = set(p.get("stores_tags") or [])
    for tag, name in RETAILERS.items():
        if tag in tags: return name
    low = (p.get("stores") or "").lower()
    for tag, name in RETAILERS.items():
        if name.lower() in low: return name
    return None

def map_product(p, retailer=None):
    code = (p.get("code") or "").strip()
    name = (p.get("product_name_it") or p.get("product_name") or "").strip()
    if not code or not name: return None
    retailer = retailer or retailer_of(p)
    brand = (p.get("brands") or "").split(",")[0].strip()
    own = OWN_BRANDS.get(retailer, [])
    is_pl = int(any(brand.lower() == b or brand.lower().startswith(b + " ") for b in own)) if retailer else 0
    cats = p.get("categories_tags") or []
    return dict(barcode=code, name=name, brand=brand or None, retailer=retailer, is_private_label=is_pl,
        category=cats[-1].split(":")[-1] if cats else None, size=p.get("quantity"),
        ingredients=p.get("ingredients_text_it") or p.get("ingredients_text"),
        raw_material_origin=p.get("origins"), origin_status=origin_status(p.get("origins_tags"), p.get("origins")),
        packaged_in=p.get("manufacturing_places"), plant_code=plant_code(p.get("emb_codes")),
        verification="da_verificare", source_url=f"https://world.openfoodfacts.org/product/{code}",
        source_note="Importato da Open Food Facts (collaborativo): verificare con l'etichetta. "
                    "Produttore da risalire dal bollo CE.")

def upsert(c, d):
    """-> 'new' | 'updated' | 'skipped'"""
    row = c.execute("select * from products where barcode=?", (d["barcode"],)).fetchone()
    if row is None:
        server.insert(c, d); return "new"
    if row["verification"] == "verificato": return "skipped"
    fill = {k: v for k, v in d.items() if v not in (None, "") and row[k] in (None, "", "non_dichiarata") and v != row[k]
            and k not in ("verification", "source_note")}
    if not fill: return "skipped"
    c.execute("update products set " + ",".join(f"{k}=?" for k in fill) + ", updated_at=CURRENT_TIMESTAMP where id=?",
              [*fill.values(), row["id"]])
    return "updated"

HOST = "it.openfoodfacts.org"
UA = {"User-Agent": "PrivateLabelFinder/0.1 (studio personale)"}
_opener = urllib.request.build_opener()   # sostituito da login() con uno che conserva i cookie di sessione

def login(host, user, password):
    """Accede a Open Food Facts (POST /cgi/session.pl) e conserva il cookie di sessione. -> True/False."""
    global _opener
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    body = urllib.parse.urlencode({"user_id": user, "password": password, ".submit": "Sign in"}).encode()
    try:
        op.open(urllib.request.Request(f"https://{host}/cgi/session.pl", data=body, headers=UA), timeout=30).read()
    except urllib.error.HTTPError as e:
        print(f"login rifiutato (HTTP {e.code})", file=sys.stderr); return False
    except Exception as e:
        print(f"login non riuscito: {e}", file=sys.stderr); return False
    if not any(c.name == "session" and c.value for c in jar):
        print("login non riuscito: utente o password errati", file=sys.stderr); return False
    _opener = op; return True

def fetch_page(store_tag, page, size):
    qs = urllib.parse.urlencode({"stores_tags": store_tag, "countries_tags_en": "italy", "fields": FIELDS,
                                 "page": page, "page_size": size, "sort_by": "unique_scans_n"})
    req = urllib.request.Request(f"https://{HOST}/api/v2/search?" + qs, headers=UA)
    for attempt in range(3):
        try: return json.load(_opener.open(req, timeout=30)).get("products", [])
        except Exception as e:
            print(f"  errore pagina {page}: {e} (tentativo {attempt+1}/3)", file=sys.stderr); time.sleep(5 * (attempt + 1))
    return None

def run(products_iter, dry):
    server.init(); stats = {"new": 0, "updated": 0, "skipped": 0, "invalid": 0}; withplant = 0
    with server.conn() as c:
        for p, ret in products_iter:
            d = map_product(p, ret)
            if not d: stats["invalid"] += 1; continue
            withplant += bool(d["plant_code"])
            if dry:
                exists = c.execute("select 1 from products where barcode=?", (d["barcode"],)).fetchone()
                stats["skipped" if exists else "new"] += 1
            else: stats[upsert(c, d)] += 1
    print(stats, f"| con bollo CE: {withplant}", "(dry-run)" if dry else "")

def main():
    global HOST
    a = argparse.ArgumentParser()
    a.add_argument("--retailer", choices=RETAILERS); a.add_argument("--all", action="store_true")
    a.add_argument("--max-pages", type=int, default=5); a.add_argument("--page-size", type=int, default=100)
    a.add_argument("--sleep", type=float, default=7, help="pausa tra richieste (OFF: max ~10 ricerche/minuto)")
    a.add_argument("--fixture"); a.add_argument("--dry-run", action="store_true")
    a.add_argument("--host", default=HOST); a.add_argument("--user", default=os.environ.get("OFF_USER"),
                   help="utente Open Food Facts (o variabile OFF_USER)")
    a = a.parse_args()
    HOST = a.host
    if a.user and not a.fixture:
        pw = os.environ.get("OFF_PASSWORD") or getpass.getpass(f"Password Open Food Facts per {a.user}: ")
        if not login(a.host, a.user, pw): sys.exit(1)
        print(f"login effettuato come {a.user}")
    if a.fixture:
        data = json.load(open(a.fixture)); return run(((p, None) for p in data["products"]), a.dry_run)
    if not (a.retailer or a.all): sys.exit("Specifica --retailer X oppure --all")
    def gen():
        for tag in (RETAILERS if a.all else [a.retailer]):
            print(f"== {RETAILERS[tag]}")
            for pg in range(1, a.max_pages + 1):
                ps = fetch_page(tag, pg, a.page_size)
                if ps is None: print("  interrotto: rete/OFF non raggiungibile", file=sys.stderr); return
                if not ps: break
                print(f"  pagina {pg}: {len(ps)} prodotti")
                for p in ps: yield p, RETAILERS[tag]
                time.sleep(a.sleep)
    run(gen(), a.dry_run)

if __name__ == "__main__": main()
