# Setup una tantum (circa 45 minuti)

Da fare una volta sola. Dopo, il processo gira da solo.

## 1. Verifica il canale col telefono (2 min)
Apri https://www.youtube.com/verify con l'account del canale Relaxing Pills e conferma con un SMS.
Senza questa verifica YouTube non accetta video più lunghi di 15 minuti né miniature personalizzate.

## 2. Progetto Google Cloud e YouTube Data API (5 min)
1. Apri https://console.cloud.google.com e crea un progetto chiamato `relaxingpills-studio`.
2. Menu → API e servizi → Libreria → cerca **YouTube Data API v3** → Abilita.

## 3. Schermata di consenso OAuth (5 min)
1. API e servizi → **Schermata di consenso OAuth** (o "Google Auth Platform").
2. Tipo utente: **Esterno**. Nome app: `Relaxing Pills Studio`. Email di supporto e del developer: la tua.
3. Nella sezione Pubblico / Utenti di test aggiungi la tua email.
4. Premi **Pubblica app** e porta lo stato su **In produzione**.
   Serve perché in modalità "Test" la chiave scade ogni 7 giorni. Non serve la verifica di Google: per uso personale basta.

## 4. Credenziali OAuth (3 min)
1. API e servizi → Credenziali → **Crea credenziali → ID client OAuth**.
2. Tipo: **Applicazione web**. Nome: `studio`.
3. URI di reindirizzamento autorizzati: aggiungi `https://developers.google.com/oauthplayground`
4. Crea e copia **ID client** e **Client secret**.

## 5. Chiave di caricamento (refresh token) con OAuth Playground (5 min)
1. Apri https://developers.google.com/oauthplayground
2. Ingranaggio in alto a destra → spunta **Use your own OAuth credentials** → incolla ID client e Client secret.
3. A sinistra, nel campo in basso "Input your own scopes", incolla:
   `https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube https://www.googleapis.com/auth/youtube.force-ssl`
4. **Authorize APIs** → scegli l'account **del canale Relaxing Pills** (se il canale è un account brand, sceglilo nella lista).
   Al messaggio "Google non ha verificato questa app" → Avanzate → Vai a Relaxing Pills Studio → Consenti.
5. **Exchange authorization code for tokens** → copia il **Refresh token**.

## 6. Secret nel repository GitHub (3 min)
Repository `relaxingpills-studio` → Settings → Secrets and variables → Actions → **New repository secret**, tre volte:

| Nome | Valore |
| --- | --- |
| `YT_CLIENT_ID` | ID client |
| `YT_CLIENT_SECRET` | Client secret |
| `YT_REFRESH_TOKEN` | Refresh token |

## 7. Verifica API di YouTube (10 min, da fare insieme)
I progetti non verificati caricano i video solo come **privati**. Per togliere il blocco si compila il modulo
"YouTube API Services – Audit and Quota Extension Form": https://support.google.com/youtube/contact/yt_api_form
Lo compiliamo insieme nella sessione della domenica. Finché Google non risponde (circa 10-20 giorni), i video si caricano privati e la pubblicazione la programmo io da YouTube Studio.

## Dopo il setup
Avviso Claude: lancio dal workflow "Manutenzione canale" le operazioni `verify`, `playlists`, `branding` e `unlist-old`.
