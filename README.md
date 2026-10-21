# Private Label Finder (prototipo)

Scopri chi produce davvero un prodotto di supermercato e confrontalo con quello di marca.

## Avvio
    python3 server.py          # poi apri http://localhost:8000   (PORT=9000 per cambiare porta)

Serve solo Python 3. Il database è SQLite (file pl.db, creato al primo avvio; `PL_DB=/percorso/altro.db` per cambiarlo).

## Popolare il database da Open Food Facts
    python3 import_off.py --retailer conad --max-pages 5
    python3 import_off.py --all --max-pages 20
    python3 import_off.py --retailer lidl --dry-run
    # con login Open Food Facts (credenziali mai nel codice):
    export OFF_USER=mio_utente; export OFF_PASSWORD='...'   # oppure --user mio_utente (password chiesta da tastiera)

## Test
    PYTHONPATH=. python3 tests/test_import.py

## Note
- I dati importati sono "da verificare" (fonte collaborativa).
- Il produttore si ricava dal bollo CE (prossimo step: tabella dei bolli).
- La scansione con fotocamera richiede un browser con BarcodeDetector (Chrome su Android).

## Schermate (come nel mock-up su artifact)
- **Confronto**: cerca/scansiona, schede affiancate (stabilimento, ingredienti, confezionato/lavorato/materia prima, prezzo), verdetto con confidenza alta/media/bassa. Esempi dimostrativi inventati, solo nel browser.
- **Mappa private label**: linee note per insegna (`brands.py`, da verificare) + conteggi reali del database.
- **Scheda dati**: struttura del database e cosa è già implementato.
- **Ittico**: giudizi specie + zona FAO + metodo, solo con fonte e data (nessun giudizio precompilato).

## Fase 3 - Produttore dal bollo CE
    python3 plants.py download         # elenco ufficiale Min. Salute (~25 MB, aggiornato ogni giorno)
    python3 plants.py load data/sanco_tutte_le_sezioni.html
    python3 plants.py link             # compila il produttore dei prodotti importati
    python3 plants.py lookup "IT 3 74 CE"
Il registro indica l'operatore dello stabilimento (può essere un terzista, non il marchio).
Test: PYTHONPATH=. python3 tests/test_plants.py
