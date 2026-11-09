# Regole di produzione (aggiornate il 9 nov 2026, non si cambiano senza Matteo)

Queste regole valgono per ogni episodio scritto dalla sessione programmata di Claude.

## 0. Pubblico e obiettivo
- Pubblico: **dai 16 anni in su, tutti i generi, lavoratori e studenti, in tutto il mondo**. Molti non sono madrelingua inglesi
  (i mercati principali di "history for sleep" sono Vietnam, Brasile, Pakistan, India e Stati Uniti): inglese chiaro e semplice,
  frasi brevi, niente modi di dire oscuri, niente riferimenti che capisce solo chi vive negli USA.
- Promessa del canale: storie vere, calme e documentate, **per dormire, studiare o rilassarsi**. Mai contenuti per bambini
  (made for kids = no), mai toni scioccanti.

## 1. Calendario delle uscite
- **Almeno 1 video lungo a settimana, normalmente 2**: martedì e venerdì alle **00:00 UTC**
  (= lunedì e giovedì 19:00 a New York, 00:00 a Londra, 01:00 a Roma d'inverno). È la fascia dei canali leader della nicchia:
  il video è indicizzato quando in America e in Europa la gente va a letto.
- **Shorts: 3 a settimana** (mercoledì, sabato e domenica) alle **17:00 UTC** (12:00 New York, 18:00 Roma, 22:30 India):
  pausa pranzo in America, sera in Europa e Asia, il momento in cui studenti e lavoratori scorrono gli Shorts.
- In `episode.yaml` e `shorts.yaml` il campo `publish_at` si scrive **in UTC con la Z finale**: `"2026-12-01T00:00Z"`.

## 2. Quale episodio scrivere
- Apri `episodes/queue.yaml`. Prendi la prima voce con `status: scelto` in ordine di `publish_at`.
- Scrivi solo episodi che escono tra almeno 10 giorni: il margine serve alla sessione della domenica.
- Se non ci sono voci `scelto`, non inventare argomenti: gli argomenti li sceglie Matteo. Chiudi segnalandolo.

## 3. Cartella e file
`episodes/<data di publish_at>-<slug-inglese>/` con:
- `episode.yaml`: vedi `episodes/_test/episode.yaml` come modello. Campi obbligatori: `status`, `pillar` (history|science),
  `publish_at`, `keyword`, `title`, `description`, `tags`, `hashtags`, `thumbnail.text`, `thumbnail.image`, `sources`,
  `localizations` (es, pt, fr, de, it).
- `script.md`: la narrazione (formato nel README).
- `shorts.yaml`: 3 Shorts, ognuno con `title`, `description`, `publish_at`, `images`, `text`, `localizations`.

## 4. SEO: come ci trova l'algoritmo
**Ricerca parole chiave (prima di scrivere)**: due chiamate vidIQ `vidiq_keyword_research` (5 crediti ciascuna; budget del mese
150 crediti, quindi max 2 per episodio): una sull'argomento ("ancient rome for sleep"), una sulla variante a domanda o
"facts" ("what was life like in ancient rome"). Scegli la `keyword` principale: alto volume, concorrenza sotto 60,
coerente col contenuto. Annota nel commento in cima a `episode.yaml` le 3-5 parole chiave secondarie usate.

**Titolo** (max 70 caratteri, il più importante):
- Struttura: `<promessa curiosa con la keyword> | History for Sleep` oppure `| Science for Sleep`.
- Formule che funzionano nella nicchia: "What Was Life Really Like in …?", "The ENTIRE Story of …",
  "Fall Asleep to …", "100 Sleepy Facts About …", "How Did … Really …?".
- Una sola parola in MAIUSCOLO al massimo, niente clickbait falso, niente emoji.

**Descrizione**:
- Riga 1-2 (quello che si vede nella ricerca, circa 150 caratteri): la keyword esatta + la promessa
  ("Fall asleep to the calm story of … — real history, softly told, for sleep, study or relaxation.").
- Poi 2 paragrafi calmi con 3-5 parole chiave secondarie scritte in modo naturale.
- Capitoli, fonti, crediti e firma del canale li aggiunge il sistema.

**Tag**: 10-15, dal più specifico al più generico: argomento ("ancient rome"), argomento + sleep ("ancient rome for sleep"),
formato ("history for sleep", "sleep history", "history to fall asleep", "learn history while you sleep" per la storia;
"facts to fall asleep to", "fall asleep to science", "science for sleep" per la scienza), poi "sleep documentary", "calm narration".
Niente nomi di altri canali.

**Hashtag**: 3, l'ultimo sempre `#historyforsleep` o `#scienceforsleep`.

**Traduzioni (`localizations`)**: titolo e prime 2-3 righe di descrizione tradotti in **spagnolo, portoghese, francese,
tedesco e italiano**. Così il video compare anche nelle ricerche in quelle lingue. Traduzioni naturali, non letterali,
mantenendo "| History for Sleep" tradotto (es. "| Historia para dormir", "| História para dormir", "| Histoire pour dormir",
"| Geschichte zum Einschlafen", "| Storia per dormire").

**Miniatura**: `thumbnail.text` 2-4 parole che completano il titolo senza ripeterlo; `thumbnail.image` il dipinto più forte,
con un soggetto chiaro. Quella definitiva la facciamo nella sessione della domenica.

**Durata**: nella nicchia i video vincenti durano 1h30-3h. Fase 1: 60-75 min; dalla Fase 2: 90-120 min.

## 5. Lo script
- Lingua: inglese semplice e caldo, frasi brevi, ritmo lento. Il pubblico ascolta a occhi chiusi per addormentarsi.
- Durata Fase 1: **60-75 minuti** = **7.500-9.000 parole** (la voce legge circa 120 parole al minuto).
  Dalla Fase 2 (marzo 2027): 90-120 minuti, 11.000-14.500 parole.
- Struttura: 8-12 capitoli (`# Titolo`, che diventano i capitoli del video: titoli chiari e cercabili).
  Il primo è un'introduzione calma di circa 150 parole: benvenuto, invito a mettersi comodi, di cosa parliamo stasera,
  con la keyword detta a voce nei primi 30 secondi. Un solo invito gentile a iscriversi a metà episodio, una frase.
- Tono: racconto, non lezione. Dettagli sensoriali e vita quotidiana, poche date per frase, niente cliffhanger,
  niente violenza descritta nel dettaglio, niente toni allarmistici (vale soprattutto per guerre e disastri naturali).
- Chiusura: gli ultimi 2-3 minuti rallentano ancora, immagini pacifiche, buonanotte. Nessun invito all'azione.
- Fatti: solo fatti verificati su almeno due fonti affidabili (libri accademici, enciclopedie, musei, università,
  NASA/USGS/ESA per la scienza). Dove gli storici non sono d'accordo, dirlo ("historians still debate…").
  Niente numeri inventati: se una cifra è incerta, usare espressioni come "perhaps", "around".
- Originalità: ogni episodio è scritto da zero. Mai riusare paragrafi di altri episodi, mai frasi fatte ripetute
  in ogni video. È la condizione per restare monetizzabili.

## 6. Le immagini
- Una `@image` ogni 100-160 parole. Episodio da 8.000 parole = circa 60-70 immagini.
- Preferisci `commons:File:...` con file precisi trovati durante la ricerca (dipinti, incisioni, affreschi,
  stampe ukiyo-e, mappe antiche, foto NASA/ESA). Verifica che il file esista su Wikimedia Commons e che la licenza
  sia pubblico dominio o CC0/CC BY/CC BY-SA.
- `search:` va bene come riserva: aggiungi sempre il tipo di opera ("painting", "engraving", "fresco", "woodblock print")
  per evitare foto moderne con turisti.
- Per la scienza usa `nasa:` per pianeti, spazio e Terra vista dallo spazio.
- Mai immagini di persone reali vive, mai immagini di vittime o distruzione.

## 7. Gli Shorts
- 3 per episodio, 110-130 parole ciascuno (circa 45-55 secondi). Il fatto più sorprendente dell'episodio,
  detto con energia calma. **Prima frase = gancio in meno di 2 secondi** (una domanda o un fatto incredibile).
  Ultima frase: "The full calm story is on our channel."
- Titolo Short: max 60 caratteri, curiosità + parola chiave, poi `#shorts` non serve. Descrizione: 1 frase + 3 hashtag.
- `publish_at`: mercoledì, sabato e domenica successivi all'uscita del video lungo, alle 17:00 UTC.
- 2-4 immagini ciascuno (verticali o con soggetto centrale).
- `localizations` anche per gli Shorts: solo il titolo nelle 5 lingue.

## 8. Prima di chiudere
1. `python -m studio.check episodes/<cartella>` deve dare OK.
2. Imposta `status: ready` in `episode.yaml` e `status: scritto` nella voce di `queue.yaml`.
3. Commit con messaggio `Episodio: <titolo>` e push su main. GitHub Actions fa il resto.
