import os, sys, tempfile
os.environ["PL_DB"] = tempfile.mktemp(suffix=".db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server, plants as P, import_off as I
for raw, k in [("UE IT 03 74", "IT 3 74"), ("it 3-74 ce", "IT 3 74"), ("IT 10 40 CE", "IT 10 40"), ("UE IT L2K7A", "IT L2K7A"),
               ("IT L2K7A CE", "IT L2K7A"), ("UE IT 1238 L", "IT 1238 L"), ("DE BY 1 EG", None), ("", None), (None, None)]:
    assert P.canon(raw) == k, (raw, P.canon(raw))
assert I.plant_code("IT 03 74 CE") == "IT 3 74 CE" and I.plant_code("IT L2K7A CE") == "IT L2K7A CE"
assert I.plant_code("made in Italy") is None and I.plant_code("IT 3 74") is None
here = os.path.dirname(os.path.abspath(__file__))
rows = list(P.parse(os.path.join(here, "sanco_sample.html")))
assert len(rows) == 5 and rows[0]["name"] == "CASA MONTALBANO S.R.L.", rows[:1]
P.load([os.path.join(here, "sanco_sample.html")])
assert P.lookup("IT 1299 CE")["sections"] == "8,11"        # stesso stabilimento, due sezioni -> unito
with server.conn() as c:
    server.insert(c, dict(name="Gamberi", barcode="1", plant_code="IT 1299 CE"))
    server.insert(c, dict(name="Altro", barcode="2", plant_code="IT 999 CE"))
    server.insert(c, dict(name="Gia", barcode="3", plant_code="IT 10 40 CE", manufacturer="Mio"))
P.link()
with server.conn() as c:
    g = lambda b: c.execute("select manufacturer from products where barcode=?", (b,)).fetchone()[0]
    assert g("1") == "D'APOTE MARE S.R.L. SEMPLIFICATA" and g("2") is None and g("3") == "Mio"
print("OK")
