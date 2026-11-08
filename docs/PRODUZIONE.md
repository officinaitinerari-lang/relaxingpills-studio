# Regole di produzione (decise l'8 nov 2026, non si cambiano senza Matteo)

Queste regole valgono per ogni episodio scritto dalla sessione programmata di Claude.

## 1. Quale episodio scrivere
- Apri `episodes/queue.yaml`. Prendi la prima voce con `status: scelto` in ordine di `publish_at`.
- Scrivi solo episodi che escono tra almeno 10 giorni: il margine serve alla sessione della domenica.
- Se non ci sono voci `scelto`, non inventare argomenti: gli argomenti li sceglie Matteo. Chiudi segnalandolo.

## 2. Cartella e file
`episodes/<publish_at data>-<slug-inglese>/` con:
- `episode.yaml`: vedi `episodes/_test/episode.yaml` come modello. Campi obbligatori: `status`, `pillar` (history|science),
  `publish_at` (ora di Roma, martedì 02:00 nella Fase 1), `title`, `description`, `tags`, `hashtags`, `thumbnail.text`,
  `thumbnail.image`, `sources`.
- `script.md`: la narrazione (formato nel README).
- `shorts.yaml`: 3 Shorts.

## 3. Lo script
- Lingua: inglese semplice e caldo, frasi brevi, ritmo lento. Il pubblico ascolta a occhi chiusi per addormentarsi.
- Durata Fase 1: **60-75 minuti** = **7.500-9.000 parole** (la voce legge circa 120 parole al minuto).
  Dalla Fase 2 (marzo 2027): 90-120 minuti, 11.000-14.500 parole.
- Struttura: 8-12 capitoli (`# Titolo`). Il primo è un'introduzione calma di circa 150 parole:
  benvenuto, invito a mettersi comodi, di cosa parliamo stasera. Niente richieste di iscrizione all'inizio.
  Un solo invito gentile a iscriversi a metà episodio, una frase.
- Tono: racconto, non lezione. Dettagli sensoriali e vita quotidiana, poche date per frase, niente cliffhanger,
  niente violenza descritta nel dettaglio, niente toni allarmistici (vale soprattutto per guerre e disastri naturali).
- Chiusura: gli ultimi 2-3 minuti rallentano ancora, immagini pacifiche, buonanotte. Nessun invito all'azione.
- Fatti: solo fatti verificati su almeno due fonti affidabili (libri accademici, enciclopedie, musei, università,
  NASA/USGS/ESA per la scienza). Dove gli storici non sono d'accordo, dirlo ("historians still debate…").
  Niente numeri inventati: se una cifra è incerta, usare espressioni come "perhaps", "around".
- Originalità: ogni episodio è scritto da zero. Mai riusare paragrafi di altri episodi, mai frasi fatte ripetute
  in ogni video. È la condizione per restare monetizzabili.

## 4. Le immagini
- Una `@image` ogni 100-160 parole. Episodio da 8.000 parole = circa 60-70 immagini.
- Preferisci `commons:File:...` con file precisi trovati durante la ricerca (dipinti, incisioni, affreschi,
  stampe ukiyo-e, mappe antiche, foto NASA/ESA). Verifica che il file esista su Wikimedia Commons e che la licenza
  sia pubblico dominio o CC0/CC BY/CC BY-SA.
- `search:` va bene come riserva: aggiungi sempre il tipo di opera ("painting", "engraving", "fresco", "woodblock print")
  per evitare foto moderne con turisti.
- Per la scienza usa `nasa:` per pianeti, spazio e Terra vista dallo spazio.
- Mai immagini di persone reali vive, mai immagini di vittime o distruzione.

## 5. Metadati
- Titolo: max 70 caratteri, formato `<Argomento evocativo> | History for Sleep` oppure `| Science for Sleep`.
- Descrizione: 2 paragrafi calmi (cosa si ascolta, per chi è) + una riga "Perfect for sleep, study or quiet evenings."
  Capitoli, fonti, crediti e firma del canale li aggiunge il sistema.
- `tags`: 8-12, specifici dell'argomento. `hashtags`: 3.
- `thumbnail.text`: 2-4 parole, maiuscolo, evocativo (es. "A DAY IN ROME"). `thumbnail.image`: il dipinto più bello.
- `sources`: 4-8 fonti reali con URL quando c'è.

## 6. Gli Shorts
- 3 per episodio, 110-130 parole ciascuno (circa 45-55 secondi). Il fatto più sorprendente dell'episodio,
  detto con energia calma. Prima frase = gancio. Ultima frase: "The full calm story is on our channel."
- `publish_at`: mercoledì, venerdì e domenica successivi all'uscita del video lungo, ore 15:00.
- 2-4 immagini ciascuno (verticali o con soggetto centrale).

## 7. Prima di chiudere
1. `python -m studio.check episodes/<cartella>` deve dare OK.
2. Imposta `status: ready` in `episode.yaml` e `status: scritto` nella voce di `queue.yaml`.
3. Commit con messaggio `Episodio: <titolo>` e push su main. GitHub Actions fa il resto.
