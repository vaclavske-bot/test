import os, tempfile, sys
os.environ["PL_DB"] = tempfile.mktemp(suffix=".db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server, import_off as I
assert I.plant_code("it 03 74 ce") == "IT 3 74 CE" and I.plant_code("IT 3 74 CE, DE 1") == "IT 3 74 CE" and I.plant_code("DE BY 1 EG") is None
assert I.origin_status(["en:italy"], "Italia") == "italia"
assert I.origin_status(["en:european-union","en:non-eu-agriculture"], "") == "misto"
assert I.origin_status([], "") == "non_dichiarata"
assert I.origin_status(["en:italy","en:france"], "") == "misto"
import json
prods = json.load(open(os.path.join(os.path.dirname(__file__), "off_fixture.json")))["products"]
d = I.map_product(prods[0]); assert d["is_private_label"] == 1 and d["retailer"] == "Conad" and d["plant_code"] == "IT 3 74 CE"
assert (d["nutriscore"], d["nova"], d["kcal_100g"], d["salt_100g"], d["additives"], d["allergens"]) == ("B", 1, 47.0, 0.1, "E300, E330", "latte")
assert d["fiber_100g"] is None                      # assente in origine -> None, non 0
n2 = I.map_product(prods[1]); assert n2["nutriscore"] is None and n2["nova"] is None and n2["kcal_100g"] is None and n2["additives"] is None
assert I.nutrition({"nutriscore_grade": "unknown", "nova_group": 9})["nutriscore"] is None and I.nutrition({"nova_group": 9})["nova"] is None
assert I.map_product(prods[2])["is_private_label"] == 0 and I.map_product(prods[2])["retailer"] == "Coop"
assert I.map_product(prods[3]) is None
server.init()
with server.conn() as c:
    server.insert(c, dict(name="Già verificato", barcode="8000000000000", verification="verificato", manufacturer="X"))
    r = [I.upsert(c, I.map_product(p)) for p in prods if I.map_product(p)]
    assert r == ["new","new","new","skipped"], r
    assert [I.upsert(c, I.map_product(p)) for p in prods[:3]] == ["skipped"]*3   # idempotente
    assert c.execute("select manufacturer from products where barcode='8000000000000'").fetchone()[0] == "X"
print("OK")
