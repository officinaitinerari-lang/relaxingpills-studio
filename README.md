# Relaxing Pills Studio

Produzione automatica del canale YouTube **Relaxing Pills — Calm History & Science for Sleep**.
Piano completo: https://claude.ai/artifact/Tt1GxEYzFcDn1EVLx6CBya

## Come funziona
1. **Domenica**: Matteo sceglie gli argomenti → `episodes/queue.yaml`.
2. **Claude** (sessione programmata) scrive l'episodio due settimane prima dell'uscita:
   `episodes/<data>-<slug>/episode.yaml`, `script.md`, `shorts.yaml`, poi imposta `status: ready` e fa push.
3. **GitHub Actions** (`.github/workflows/render.yml`) al push:
   immagini di pubblico dominio (Wikimedia Commons, NASA) → voce Kokoro (`am_michael`) → musica ambient generata →
   video 16:9 + 3 Shorts 9:16 + miniatura → controlli di qualità → caricamento programmato su YouTube.
   Lo stato finisce in `published.json`; se un controllo fallisce il video non parte e GitHub manda una mail.
4. Le anteprime (miniature, Shorts, primi 3 minuti) restano 14 giorni negli artifact del workflow.

## Formato dello script
```
# Titolo capitolo
@image commons:File:Nome_preciso.jpg      ← Wikimedia Commons (pubblico dominio / CC0 / CC BY / CC BY-SA)
@image aic:27992                          ← Art Institute of Chicago (CC0)
@image cma:135382                         ← Cleveland Museum of Art (CC0)
@image nasaid:PIA21973                    ← NASA
@image local:images/nome.jpg              ← file nella cartella dell'episodio
Paragrafo di narrazione…

@pause 2                                   ← pausa in secondi
```
Una `@image` ogni 60-90 parole, scelta una per una dalle griglie della **Ricerca immagini**
(`image_queries.yaml` → workflow `candidates.yml` → branch `candidati`). Vedi docs/PRODUZIONE.md, sezione 6.

## Comandi locali
```
pip install -r requirements.txt
python -m studio.run --episode _test --offline --no-upload   # prova senza rete
```

## Setup
Vedi [docs/SETUP.md](docs/SETUP.md).
