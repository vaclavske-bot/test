"""Insegne e linee a marchio. Elenco di partenza DA VERIFICARE e completare (le linee cambiano spesso)."""
# tag OFF dell'insegna -> nome visualizzato
RETAILERS = {"conad": "Conad", "coop": "Coop", "esselunga": "Esselunga",
             "eurospin": "Eurospin", "top-supermercati": "Top Supermercati", "lidl": "Lidl"}
# marchi propri per insegna, in minuscolo: servono a riconoscere un private label dal marchio in etichetta
OWN_BRANDS = {
 "Conad": ["conad", "verso natura", "sapori & dintorni", "sapori e dintorni", "percorsi di qualità", "percorso qualità", "io conad", "la bottega del gusto", "conad bio"],
 "Coop": ["coop", "vivi verde", "fior fiore", "crescendo", "assieme", "bene.sì", "bene sì", "club 4-14", "origine"],
 "Esselunga": ["esselunga", "esselunga bio", "esselunga top", "naturama", "equilibrio", "smart", "top"],
 "Eurospin": ["eurospin", "tre mulini", "alimentari", "land", "mi piace"],
 "Top Supermercati": ["top", "top supermercati"],
 "Lidl": ["lidl", "italiamo", "deluxe", "bio organic", "milbona", "cien", "vemondo", "combino", "pilos", "chef select", "freeway", "bioland", "nixe"],
}
# linee note da mostrare nella "Mappa private label" (testo libero, stato sempre 'da verificare')
LINES_TEXT = {
 "Conad": "Verso Natura (bio), Sapori & Dintorni, Percorsi di Qualità, Conad (base)",
 "Coop": "Vivi Verde (bio), Fior fiore, Crescendo, Assieme, Coop (base)",
 "Esselunga": "Esselunga Bio, Esselunga Top, Naturama, Equilibrio, Esselunga (base)",
 "Eurospin": "Linee a marchio Eurospin (elenco da completare)",
 "Top Supermercati": "Linee a marchio Top (elenco da completare)",
 "Lidl": "Italiamo, Deluxe, Bio Organic, Milbona, Cien, Vemondo",
}
