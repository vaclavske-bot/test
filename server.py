"""Private Label Finder - server (solo libreria standard, SQLite)."""
import json, sqlite3, os, re, urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB = os.environ.get("PL_DB", os.path.join(os.path.dirname(__file__), "pl.db"))
STATIC = os.path.join(os.path.dirname(__file__), "static")

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY, barcode TEXT UNIQUE, name TEXT NOT NULL, brand TEXT,
  line TEXT, retailer TEXT, is_private_label INTEGER DEFAULT 0, category TEXT,
  size TEXT, price_eur REAL, price_per_unit REAL, unit TEXT,
  ingredients TEXT,
  raw_material_origin TEXT,        -- testo dichiarato in etichetta
  origin_status TEXT DEFAULT 'non_dichiarata', -- italia|ue|extra_ue|misto|non_dichiarata
  packaged_in TEXT,                -- paese di confezionamento
  manufacturer TEXT, manufacturer_address TEXT, plant_code TEXT, -- bollo CE / stabilimento
  processed_in TEXT,               -- paese di lavorazione
  nutriscore TEXT, nova INTEGER,   -- A-E (calcolato da Open Food Facts), 1-4
  kcal_100g REAL, fat_100g REAL, saturated_fat_100g REAL, carbs_100g REAL, sugars_100g REAL,
  fiber_100g REAL, proteins_100g REAL, salt_100g REAL, additives TEXT, allergens TEXT,
  fao_area TEXT, species TEXT, fishing_method TEXT, fish_note TEXT,
  verification TEXT DEFAULT 'da_verificare', -- verificato|da_verificare|segnalato_utente
  source_url TEXT, source_note TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS ix_prod_man ON products(manufacturer, category);
CREATE INDEX IF NOT EXISTS ix_prod_plant ON products(plant_code);
CREATE TABLE IF NOT EXISTS plants (
  key TEXT PRIMARY KEY, approval TEXT, name TEXT, vat TEXT, tax_code TEXT, address TEXT, sections TEXT, activities TEXT);
CREATE TABLE IF NOT EXISTS fish_ratings (
  id INTEGER PRIMARY KEY, species TEXT NOT NULL, fao_area TEXT NOT NULL, method TEXT,
  rating TEXT NOT NULL CHECK (rating IN ('consigliato','accettabile','sconsigliato')),
  source TEXT NOT NULL, source_url TEXT, rated_on TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS missing (
  id INTEGER PRIMARY KEY, query TEXT, barcode TEXT, retailer TEXT, note TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP, resolved INTEGER DEFAULT 0);
"""
NUTRITION = ["nutriscore","nova","kcal_100g","fat_100g","saturated_fat_100g","carbs_100g","sugars_100g",
 "fiber_100g","proteins_100g","salt_100g","additives","allergens"]
NEW_COLS = {"processed_in": "TEXT", "fishing_method": "TEXT", **{k: ("TEXT" if k in ("nutriscore","additives","allergens") else "INTEGER" if k == "nova" else "REAL") for k in NUTRITION}}
FIELDS = ["barcode","name","brand","line","retailer","is_private_label","category","size",
 "price_eur","price_per_unit","unit","ingredients","raw_material_origin","origin_status",
 "packaged_in","processed_in","fishing_method","nutriscore","nova","kcal_100g","fat_100g","saturated_fat_100g","carbs_100g","sugars_100g","fiber_100g","proteins_100g","salt_100g","additives","allergens","manufacturer","manufacturer_address","plant_code","fao_area","species",
 "fish_note","verification","source_url","source_note"]

# Aree FAO di pesca: nome ufficiale. Il giudizio sulla sostenibilità dipende da specie+area+attrezzo:
# NON è codificato qui; va inserito con fonte (MSC, GFCM/STECF, Good Fish Guide, ecc.).
FAO_AREAS = {"21":"Atlantico nord-occidentale","27":"Atlantico nord-orientale","31":"Atlantico centro-occidentale",
 "34":"Atlantico centro-orientale","37":"Mediterraneo e Mar Nero (37.1 occ., 37.2 centr., 37.3 or.)",
 "41":"Atlantico sud-occidentale","47":"Atlantico sud-orientale","51":"Oceano Indiano occidentale",
 "57":"Oceano Indiano orientale","61":"Pacifico nord-occidentale","67":"Pacifico nord-orientale",
 "71":"Pacifico centro-occidentale","77":"Pacifico centro-orientale","81":"Pacifico sud-occidentale",
 "87":"Pacifico sud-orientale"}

def conn():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; c.execute("pragma journal_mode=wal"); return c

def init():
    with conn() as c:
        c.executescript(SCHEMA)
        have = {r["name"] for r in c.execute("pragma table_info(products)")}   # migrazione di DB creati prima
        for col, typ in NEW_COLS.items():
            if col not in have: c.execute(f"alter table products add column {col} {typ}")
        if c.execute("select count(*) from products").fetchone()[0] == 0:
            seed(c)

def seed(c):
    """Solo dati con fonte verificata. Aggiungere altri tramite import/segnalazioni."""
    rows = [dict(name="Latte parzialmente scremato biologico 1 L", brand="Conad", line="Verso Natura Bio",
      retailer="Conad", is_private_label=1, category="latte", size="1 L",
      manufacturer="Granarolo S.p.A.", manufacturer_address="Via Cadriano 27/2, Bologna",
      verification="verificato",
      source_url="https://spesaonline.conad.it/p/conad-verso-natura-latte-parzialmente-scremato-biologico-1-l--401468",
      source_note="Scheda Conad: 'Prodotto per Conad S.C., Bologna - da Granarolo S.p.A., Via Cadriano 27/2'. Origine materia prima e bollo CE da leggere in etichetta."),
     dict(name="Latte parzialmente scremato biologico 1 L", brand="Granarolo", line="Bio",
      retailer="(multi-insegna)", is_private_label=0, category="latte", size="1 L",
      manufacturer="Granarolo S.p.A.", manufacturer_address="Via Cadriano 27/2, Bologna",
      verification="da_verificare",
      source_note="Marchio del produttore. Dati di etichetta (bollo, origine latte, prezzo) da inserire.")]
    for r in rows: insert(c, r)

def insert(c, d):
    d = {k: d.get(k) for k in FIELDS if d.get(k) not in (None, "")}
    if d.get("is_private_label") in (None, "") and d.get("retailer") and d.get("brand"):
        import brands   # marchio proprio dell'insegna? (elenco da verificare in brands.py)
        b = d["brand"].lower()
        d["is_private_label"] = int(any(b == x or b.startswith(x + " ") for x in brands.OWN_BRANDS.get(d["retailer"], [])))
    if d.get("plant_code"):
        import plants   # import locale: plants importa server
        d["plant_code"] = plants.display(plants.canon(d["plant_code"])) or d["plant_code"]
    cols = ",".join(d); q = ",".join("?" * len(d))
    cur = c.execute(f"insert into products ({cols}) values ({q})", list(d.values()))
    return cur.lastrowid

def norm(s): return re.sub(r"[^a-z0-9àèéìòù ]", " ", (s or "").lower())

def search(q):
    q = norm(q).split()
    if not q: return []
    with conn() as c:
        rows = c.execute("select * from products").fetchall()
    out = []
    for r in rows:
        hay = norm(" ".join(str(r[k] or "") for k in ("name","brand","line","retailer","manufacturer","category","barcode","plant_code")))
        if all(t in hay for t in q): out.append(dict(r))
    return [enrich(p) for p in out[:50]]

def fish_rating(p):
    """Giudizio più specifico (zona FAO più precisa, poi metodo) per specie+zona+metodo del prodotto; None se non c'è."""
    if not (p.get("species") and p.get("fao_area")): return None
    with conn() as c:
        rows = [dict(r) for r in c.execute("select * from fish_ratings")]
    best, best_score = None, -1
    for r in rows:
        if norm(r["species"]).split() != norm(p["species"]).split(): continue
        ra, pa = r["fao_area"].strip(), p["fao_area"].strip()
        if not (pa == ra or pa.startswith(ra + ".")): continue
        if r["method"] and norm(r["method"]).split() != norm(p.get("fishing_method")).split(): continue
        score = len(ra) * 10 + (1 if r["method"] else 0)
        if score > best_score: best, best_score = r, score
    return best

def enrich(p):
    p = with_plant(p)
    if p.get("species"): p["fish_rating"] = fish_rating(p)
    return p

def with_plant(p):
    """Aggiunge lo stabilimento dal registro ufficiale (se caricato e se il bollo è noto)."""
    if p.get("plant_code"):
        import plants
        with conn() as c:
            r = c.execute("select name, vat, address, sections from plants where key=?", (plants.canon(p["plant_code"]),)).fetchone()
        p["plant"] = dict(r) if r else None
    return p

_LEGAL = re.compile(r"(?<!\w)(s\.?\s?p\.?\s?a\.?|s\.?\s?r\.?\s?l\.?\s?s?\.?|scarl|soc\.?|societa'?|società|cooperativa|coop\.?)(?!\w)")

def man_key(s):
    """Ragione sociale senza forma giuridica: 'GRANAROLO S.p.A.' == 'Granarolo spa'."""
    return " ".join(norm(_LEGAL.sub(" ", (s or "").lower())).split())

def _plant_key(p):
    if not p.get("plant_code"): return None
    import plants
    return plants.canon(p["plant_code"])

def verdict(a, b):
    """Confronto dei dati di fabbricazione tra due schede -> (livello, testo)."""
    ka, kb = _plant_key(a), _plant_key(b)
    name = lambda p: man_key(p.get("manufacturer") or (p.get("plant") or {}).get("name"))   # dichiarato, o dal registro
    same_man = bool(name(a) and name(a) == name(b))
    va, vb = (a.get("plant") or {}).get("vat"), (b.get("plant") or {}).get("vat")
    same_man = same_man or bool(va and va == vb)
    if ka and kb:
        if ka == kb: return "stesso_stabilimento", f"Stesso stabilimento: bollo identico ({ka} CE). Prodotti fabbricati nello stesso sito."
        if same_man: return "stesso_produttore", "Stesso produttore ma stabilimenti diversi: lavorazione e ricetta possono differire."
        return "diversi", "Stabilimenti e produttori diversi."
    if same_man: return "da_confermare", "Stesso produttore dichiarato, ma manca il bollo per confermare lo stabilimento."
    return None, None

def confidence(a, b, lvl, ident):
    """Livello alta/media/bassa del 'sono lo stesso prodotto?' (regola della Scheda dati)."""
    if lvl == "stesso_stabilimento":
        if ident: return "alta", "Stesso codice stabilimento e ingredienti identici."
        if ident is False: return "media", "Stesso codice stabilimento ma ricetta diversa."
        return "media", "Stesso codice stabilimento; ingredienti non confrontabili (dati mancanti)."
    if lvl == "stesso_produttore": return "media", "Stesso produttore ma stabilimenti diversi."
    if "segnalato_utente" in (a.get("verification"), b.get("verification")):
        return "bassa", "Produttore solo segnalato da utenti: non verificato."
    return "media", "Produttore dedotto dalla sola dichiarazione, senza bollo che lo confermi."

def producer_status(p):
    if p.get("plant"): return "registro"        # identificato dal registro ufficiale tramite bollo
    if p.get("manufacturer"): return "dichiarato"
    return "sconosciuto"

def compare(pid):
    """Prodotti dello stesso stabilimento/produttore: stessa categoria in 'matches', altre in 'other_categories'."""
    with conn() as c:
        row = c.execute("select * from products where id=?", (pid,)).fetchone()
        if not row: return None
        everything = [dict(r) for r in c.execute("select * from products where id!=?", (pid,))]
    p = enrich(dict(row)); res, other = [], []
    for r in everything:
        r = enrich(r); lvl, txt = verdict(p, r)
        if not lvl or lvl == "diversi": continue
        if r["category"] != p["category"]:
            other.append({"id": r["id"], "name": r["name"], "brand": r["brand"], "retailer": r["retailer"],
                          "category": r["category"], "level": lvl}); continue
        same = bool(p["ingredients"] and r["ingredients"])
        ident = norm(p["ingredients"]).split() == norm(r["ingredients"]).split() if same else None
        cl, ct = confidence(p, r, lvl, ident)
        res.append({"product": r, "level": lvl, "verdict": txt, "identical_ingredients": ident,
                    "confidence": cl, "confidence_text": ct})
    order = {"stesso_stabilimento": 0, "stesso_produttore": 1, "da_confermare": 2}
    res.sort(key=lambda m: (order[m["level"]], {"alta": 0, "media": 1, "bassa": 2}[m["confidence"]])); other.sort(key=lambda m: order[m["level"]])
    return {"product": p, "producer_status": producer_status(p), "matches": res, "other_categories": other}

def lines_overview():
    """Mappa private label: linee note per insegna + quanto c'è nel database."""
    import brands
    out = []
    with conn() as c:
        for name in brands.RETAILERS.values():
            q = lambda sql: c.execute(sql, (name,)).fetchone()[0]
            found = [r[0] for r in c.execute("select distinct line from products where retailer=? and line is not null order by line", (name,))]
            out.append({"retailer": name, "known_lines": brands.LINES_TEXT.get(name, ""), "lines_in_db": found,
                        "products": q("select count(*) from products where retailer=?"),
                        "private_label": q("select count(*) from products where retailer=? and is_private_label=1"),
                        "with_producer": q("select count(*) from products where retailer=? and (manufacturer is not null or plant_code is not null)")})
        stats = {"products": c.execute("select count(*) from products").fetchone()[0],
                 "with_plant": c.execute("select count(*) from products where plant_code is not null").fetchone()[0],
                 "plants_registry": c.execute("select count(*) from plants").fetchone()[0],
                 "fish_ratings": c.execute("select count(*) from fish_ratings").fetchone()[0]}
    return {"lines": out, "stats": stats}

def add_fish_rating(d):
    import datetime
    for k in ("species", "fao_area", "rating", "source"):
        if not str(d.get(k) or "").strip(): return None, f"{k} richiesto"
    if d["rating"] not in ("consigliato", "accettabile", "sconsigliato"): return None, "rating non valido"
    if d["fao_area"].split(".")[0] not in FAO_AREAS: return None, "zona FAO non valida (es. 37 o 37.2)"
    with conn() as c:
        cur = c.execute("insert into fish_ratings(species,fao_area,method,rating,source,source_url,rated_on) values (?,?,?,?,?,?,?)",
                        (d["species"].strip(), d["fao_area"].strip(), (d.get("method") or "").strip() or None, d["rating"],
                         d["source"].strip(), d.get("source_url") or None, d.get("rated_on") or datetime.date.today().isoformat()))
    return cur.lastrowid, None

def off_lookup(code):
    """Open Food Facts (se la rete lo consente). Restituisce dict pronto per insert o None."""
    url = f"https://world.openfoodfacts.org/api/v2/product/{urllib.parse.quote(code)}.json"
    req = urllib.request.Request(url, headers={"User-Agent": "PrivateLabelFinder/0.1"})
    try:
        j = json.load(urllib.request.urlopen(req, timeout=10))
    except Exception as e:
        return {"error": str(e)}
    if j.get("status") != 1: return None
    import import_off   # stesso mapping dell'import in blocco (bollo normalizzato, nutrizione, ecc.)
    p = dict(j["product"]); p.setdefault("code", code)
    return import_off.map_product(p) or {"error": "prodotto senza nome su Open Food Facts"}

class H(BaseHTTPRequestHandler):
    def send(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or "{}")
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); qs = urllib.parse.parse_qs(u.query)
        if u.path == "/api/search": return self.send(search(qs.get("q", [""])[0]))
        if u.path == "/api/barcode":
            with conn() as c:
                r = c.execute("select * from products where barcode=?", (qs.get("code", [""])[0],)).fetchone()
            return self.send(dict(r) if r else None)
        m = re.fullmatch(r"/api/compare/(\d+)", u.path)
        if m:
            r = compare(int(m[1])); return self.send(r, 200 if r else 404)
        if u.path == "/favicon.ico": self.send_response(204); return self.end_headers()
        if u.path == "/api/fao": return self.send(FAO_AREAS)
        if u.path == "/api/lines": return self.send(lines_overview())
        if u.path == "/api/fish":
            with conn() as c: return self.send([dict(r) for r in c.execute("select * from fish_ratings order by species, fao_area")])
        if u.path == "/api/missing":
            with conn() as c: return self.send([dict(r) for r in c.execute("select * from missing where resolved=0 order by id desc")])
        path = "index.html" if u.path == "/" else u.path.lstrip("/")
        f = os.path.normpath(os.path.join(STATIC, path))
        if f.startswith(STATIC) and os.path.isfile(f):
            b = open(f, "rb").read(); self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8" if f.endswith(".html") else "application/octet-stream")
            self.end_headers(); return self.wfile.write(b)
        self.send({"error": "not found"}, 404)
    def do_POST(self):
        d = self.body()
        if self.path == "/api/product":
            if not d.get("name"): return self.send({"error": "name richiesto"}, 400)
            d.setdefault("verification", "segnalato_utente")
            with conn() as c:
                try: pid = insert(c, d)
                except sqlite3.IntegrityError: return self.send({"error": "barcode già presente"}, 409)
                if d.get("barcode"): c.execute("update missing set resolved=1 where barcode=?", (d["barcode"],))
            return self.send({"id": pid}, 201)
        if self.path == "/api/fish":
            rid, err = add_fish_rating(d)
            return self.send({"error": err} if err else {"id": rid}, 400 if err else 201)
        if self.path == "/api/missing":
            with conn() as c:
                c.execute("insert into missing(query,barcode,retailer,note) values (?,?,?,?)",
                          (d.get("query"), d.get("barcode"), d.get("retailer"), d.get("note")))
            return self.send({"ok": True}, 201)
        if self.path == "/api/import-off":
            r = off_lookup(d.get("barcode", ""))
            if r is None: return self.send({"error": "non trovato su Open Food Facts"}, 404)
            if "error" in r: return self.send(r, 502)
            return self.send(r)   # precompila il form; l'utente conferma con POST /api/product
        self.send({"error": "not found"}, 404)
    def log_message(self, *a): pass

if __name__ == "__main__":
    init()
    port = int(os.environ.get("PORT", 8000))
    print(f"http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
