# CorsaScore App

Algoritmo per misurazione efficienza aerobica nelle corse.

## Funzionalità

- Analisi del punteggio CorsaScore 2.0 basato su potenza, frequenza cardiaca e decoupling aerobico
- Caricamento dati da file JSON (Polar/Garmin)
- Integrazione con Strava API per importare attività direttamente

## Pubblicazione su Streamlit Cloud

1. **Rendi il repository pubblico** su GitHub (se privato)
2. **Aggiungi secrets** (raccomandato per Strava):
   - Vai su Streamlit Cloud > App Settings > Secrets
   - Aggiungi:
     ```
     [strava]
     client_id = "your_client_id"
     client_secret = "your_client_secret"
     redirect_uri = "https://your-app-name.streamlit.app"
     ```
   - Il `redirect_uri` deve corrispondere esattamente a quello impostato nell'app Strava
3. **Deploy**:
   - Vai su [share.streamlit.io](https://share.streamlit.io)
   - Collega il tuo repository GitHub
   - Seleziona il branch main e il file app.py
   - Clicca Deploy

## Configurazione Strava

### Per Utenti Finali (Consigliato)
Ogni utente può connettere il proprio account Strava personale:

1. **Crea la tua app Strava**: Vai su [https://www.strava.com/settings/api](https://www.strava.com/settings/api)
2. **Configura l'app**:
   - Application Name: "CorsaScore Personale"
   - Website: `https://corsaappalpha.streamlit.app`
   - Authorization Callback Domain: `corsaappalpha.streamlit.app`
3. **Inserisci nell'app**: Client ID e Client Secret dalla tua app Strava
4. **Connetti**: Clicca "🔗 Connetti Strava" per autorizzare l'accesso

### Per Sviluppatori (Deployment Ufficiale)
Aggiungi secrets in Streamlit Cloud per un'app Strava condivisa che tutti possono usare.

## Icona Personalizzata

Per usare un'icona personalizzata:
1. Metti la tua immagine (PNG, ICO, etc.) nella cartella `assets/`
2. Rinominala come `icon.png` (o modifica il codice in `app.py` per usare il tuo nome file)
3. L'app la caricherà automaticamente al prossimo deploy

## Esecuzione Locale

```bash
pip install -r requirements.txt
streamlit run app.py
```
