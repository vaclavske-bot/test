import os, sys, tempfile
os.environ["PL_DB"] = tempfile.mktemp(suffix=".db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server, plants as P
assert server.man_key("GRANAROLO S.p.A.") == server.man_key("Granarolo spa") == "granarolo"
assert server.man_key("D'Apote Mare S.R.L. semplificata") != server.man_key("Granarolo")
server.init()
with server.conn() as c:
    c.executescript(P.SCHEMA); c.execute("delete from products")   # via i dati di esempio
    for k, n, v in [("IT 3 74", "GRANAROLO S.P.A.", "111"), ("IT 5 99", "GRANAROLO S.P.A.", "111"), ("IT 7 7", "ALTRA SRL", "222")]:
        c.execute("insert into plants values (?,?,?,?,?,?,?,?)", (k, "UE " + k, n, v, v, "VIA X 1, BOLOGNA (BO)", "9", "PP"))
    a = server.insert(c, dict(name="Latte bio", brand="Conad", category="latte", plant_code="IT 03 74 CE", ingredients="latte"))
    b = server.insert(c, dict(name="Latte bio", brand="Granarolo", category="latte", plant_code="IT 3 74 CE", ingredients="Latte"))
    d = server.insert(c, dict(name="Latte bio", brand="Altro", category="latte", plant_code="IT 5 99 CE", ingredients="latte e panna"))
    e = server.insert(c, dict(name="Latte x", brand="Terzo", category="latte", manufacturer="Granarolo SPA"))
    f = server.insert(c, dict(name="Yogurt", brand="Granarolo", category="yogurt", plant_code="IT 5 99 CE"))
    g = server.insert(c, dict(name="Latte y", brand="Estraneo", category="latte", plant_code="IT 7 7 CE"))
r = server.compare(a)
lv = {m["product"]["id"]: m["level"] for m in r["matches"]}
assert lv[b] == "stesso_stabilimento" and lv[d] == "stesso_produttore" and lv[e] == "da_confermare" and g not in lv, lv
assert [m["level"] for m in r["matches"]] == ["stesso_stabilimento", "stesso_produttore", "da_confermare"]   # ordinati per affidabilità
assert [m["identical_ingredients"] for m in r["matches"][:2]] == [True, False]
conf = {m["product"]["id"]: m["confidence"] for m in r["matches"]}
assert conf[b] == "alta" and conf[d] == "media" and conf[e] == "media", conf       # alta = stesso stabilimento + stessi ingredienti
assert r["producer_status"] == "registro"
with server.conn() as c:
    h = server.insert(c, dict(name="Latte z", brand="Utente", category="latte", manufacturer="Granarolo spa", verification="segnalato_utente"))
assert {m["product"]["id"]: m["confidence"] for m in server.compare(e)["matches"]}[h] == "bassa"   # solo segnalato da utente
with server.conn() as c: nope = server.insert(c, dict(name="Misterioso", category="latte"))
assert server.compare(nope)["producer_status"] == "sconosciuto" and server.compare(nope)["matches"] == []
assert [o["id"] for o in r["other_categories"]] == [f] and r["other_categories"][0]["level"] == "stesso_produttore"
assert r["product"]["plant"]["name"] == "GRANAROLO S.P.A."
assert server.compare(99999) is None
print("OK")
