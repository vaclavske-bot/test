"""Fase 3 - Registro stabilimenti (bollo CE) del Ministero della Salute.

  python3 plants.py download            # scarica l'elenco ufficiale (tutte le sezioni, ~25 MB) in data/
  python3 plants.py load data/*.html    # carica uno o più file HTML nel DB
  python3 plants.py link                # compila 'produttore' dei prodotti dal loro bollo
  python3 plants.py lookup "IT 3 74 CE" # cerca uno stabilimento

Fonte: https://www.salute.gov.it/portale/temi/trasferimento_PROD.jsp (Reg. CE 853/2004, aggiornato ogni giorno).
Il registro dà l'OPERATORE dello stabilimento (ragione sociale, P.IVA, indirizzo): è chi ha prodotto/confezionato
lì. Può essere un terzista (co-packer) e non coincidere col marchio in etichetta: è proprio l'informazione utile.
"""
import html, os, re, sys, urllib.request
import server

BASE = "https://www.salute.gov.it/consultazioneStabilimenti/ConsultazioneStabilimentiServlet?ACTION=gestioneSingolaCategoria&idNormativa=2"
SCHEMA = """CREATE TABLE IF NOT EXISTS plants (
  key TEXT PRIMARY KEY,            -- 'IT 3 74' (senza UE/CE, zeri iniziali tolti)
  approval TEXT, name TEXT, vat TEXT, tax_code TEXT, address TEXT,
  sections TEXT,                   -- sezioni di riconoscimento, es. '9,10'
  activities TEXT);"""

def canon(raw):
    """Qualsiasi forma di bollo ('UE IT 03 74', 'it 3-74 ce', 'IT L2K7A CE') -> 'IT 3 74'; None se non è un bollo IT."""
    m = re.search(r"\bIT[\s.\-]*([A-Z0-9][A-Z0-9\s/.\-]*?)(?:\s*\bCE\b|$)", (raw or "").upper())
    if not m: return None
    toks = [t for t in re.split(r"[\s/.\-]+", m.group(1)) if t]
    toks = [str(int(t)) if t.isdigit() else t for t in toks]
    return "IT " + " ".join(toks) if toks else None

def display(key): return key + " CE" if key else None

def _text(c): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()

def parse(path):
    b = open(path, "rb").read()
    try: h = b.decode("utf-8")
    except UnicodeDecodeError: h = b.decode("cp1252", "replace")
    for r in re.finditer(r"<tr[^>]*>(.*?)</tr>", h, flags=re.S | re.I):
        cells = [_text(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r.group(1), flags=re.S | re.I)]
        if len(cells) < 7 or not re.match(r"UE\s+IT\b", cells[0]): continue
        key = canon(cells[0])
        if key: yield dict(key=key, approval=cells[0], name=cells[1], vat=cells[2], tax_code=cells[3],
                           address=cells[4], section=cells[5], activities=cells[6])

def load(paths):
    server.init(); n = 0
    with server.conn() as c:
        c.executescript(SCHEMA)
        for p in paths:
            for d in parse(p):
                old = c.execute("select sections, activities from plants where key=?", (d["key"],)).fetchone()
                sec = sorted(set(filter(None, (old[0].split(",") if old else []) + [d["section"]])), key=lambda x: (len(x), x))
                act = sorted(set(filter(None, (old[1].split(",") if old else []) + [d["activities"]])))
                c.execute("insert or replace into plants values (?,?,?,?,?,?,?,?)",
                          (d["key"], d["approval"], d["name"], d["vat"], d["tax_code"], d["address"], ",".join(sec), ",".join(act)))
                n += 1
        total = c.execute("select count(*) from plants").fetchone()[0]
    print(f"righe lette: {n} | stabilimenti unici nel DB: {total}")

def link():
    """Compila manufacturer/indirizzo dei prodotti col bollo noto. Non tocca i valori già presenti."""
    server.init(); done = miss = 0
    with server.conn() as c:
        c.executescript(SCHEMA)
        for p in c.execute("select id, plant_code, manufacturer, source_note from products where plant_code is not null").fetchall():
            pl = c.execute("select * from plants where key=?", (canon(p["plant_code"]),)).fetchone()
            if not pl: miss += 1; continue
            if p["manufacturer"]: continue
            note = ((p["source_note"] or "") + " Produttore dal registro ufficiale stabilimenti (Min. Salute) tramite bollo "
                    + display(pl["key"]) + ".").strip()
            c.execute("update products set manufacturer=?, manufacturer_address=?, source_note=?, updated_at=CURRENT_TIMESTAMP where id=?",
                      (pl["name"], pl["address"], note, p["id"])); done += 1
    print(f"collegati: {done} | bollo non presente nel registro: {miss}")

def lookup(code):
    server.init()
    with server.conn() as c:
        c.executescript(SCHEMA)
        r = c.execute("select * from plants where key=?", (canon(code),)).fetchone()
    return dict(r) if r else None

def download(outdir="data"):
    os.makedirs(outdir, exist_ok=True); dst = os.path.join(outdir, "sanco_tutte_le_sezioni.html")
    req = urllib.request.Request(BASE, headers={"User-Agent": "PrivateLabelFinder/0.1 (studio personale)"})
    with urllib.request.urlopen(req, timeout=300) as r, open(dst, "wb") as f:
        while (b := r.read(1 << 20)): f.write(b)
    print("scaricato:", dst, os.path.getsize(dst) // 1024, "KB"); return dst

if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["download"]: download()
    elif a[:1] == ["load"] and len(a) > 1: load(a[1:])
    elif a[:1] == ["link"]: link()
    elif a[:1] == ["lookup"] and len(a) > 1: print(lookup(" ".join(a[1:])) or "non trovato")
    else: print(__doc__)
