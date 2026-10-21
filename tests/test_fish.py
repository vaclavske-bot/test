import os, sqlite3, sys, tempfile
os.environ["PL_DB"] = tempfile.mktemp(suffix=".db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# migrazione: DB creato con lo schema vecchio (senza processed_in / fishing_method)
old = sqlite3.connect(os.environ["PL_DB"])
old.execute("create table products (id integer primary key, barcode text unique, name text not null, brand text, line text, retailer text, is_private_label integer default 0, category text, size text, price_eur real, price_per_unit real, unit text, ingredients text, raw_material_origin text, origin_status text default 'non_dichiarata', packaged_in text, manufacturer text, manufacturer_address text, plant_code text, fao_area text, species text, fish_note text, verification text default 'da_verificare', source_url text, source_note text, created_at text default current_timestamp, updated_at text default current_timestamp)")
old.execute("insert into products(name) values ('vecchio')"); old.commit(); old.close()
import server
server.init()
with server.conn() as c:
    assert {"processed_in", "fishing_method"} <= {r["name"] for r in c.execute("pragma table_info(products)")}
    assert c.execute("select name from products where name='vecchio'").fetchone()
    p = server.insert(c, dict(name="Tonno", species="Thunnus albacares", fao_area="37.2", fishing_method="Rete a strascico"))
assert server.enrich(dict(server.search("tonno")[0]))["fish_rating"] is None          # nessun giudizio inventato
assert server.add_fish_rating({"species": "x", "fao_area": "99", "rating": "consigliato", "source": "s"})[1]   # zona non valida
assert server.add_fish_rating({"species": "x", "fao_area": "37", "rating": "ottimo", "source": "s"})[1]
assert server.add_fish_rating({"species": "x", "fao_area": "37", "rating": "consigliato", "source": ""})[1]    # fonte obbligatoria
g, e = server.add_fish_rating({"species": "thunnus albacares", "fao_area": "37", "rating": "accettabile", "source": "Fonte A"}); assert not e
s, e = server.add_fish_rating({"species": "Thunnus albacares", "fao_area": "37.2", "method": "rete a strascico", "rating": "sconsigliato", "source": "Fonte B", "rated_on": "2026-01-01"}); assert not e
r = server.search("tonno")[0]["fish_rating"]
assert r["rating"] == "sconsigliato" and r["source"] == "Fonte B"                      # il più specifico (sottozona+metodo) vince
with server.conn() as c: c.execute("update products set fishing_method='Palangaro' where id=?", (p,))
assert server.search("tonno")[0]["fish_rating"]["source"] == "Fonte A"                 # metodo diverso -> ricade sulla zona generale
with server.conn() as c: c.execute("update products set fao_area='27' where id=?", (p,))
assert server.search("tonno")[0]["fish_rating"] is None                                # altra zona -> nessun giudizio
L = server.lines_overview(); assert {l["retailer"] for l in L["lines"]} >= {"Conad", "Lidl"} and L["stats"]["fish_ratings"] == 2
print("OK")
with server.conn() as c:
    x = server.insert(c, dict(name="Pasta", brand="Conad", retailer="Conad")); y = server.insert(c, dict(name="Pasta", brand="Barilla", retailer="Conad"))
    z = server.insert(c, dict(name="Olio", brand="Verso Natura Bio", retailer="Conad"))
    q = lambda i: c.execute("select is_private_label from products where id=?", (i,)).fetchone()[0]
    assert (q(x), q(y), q(z)) == (1, 0, 1)
print("OK2")
