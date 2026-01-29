# 🏃‍♂️ SCORE 4.0 Lab

Web app avanzata per l'analisi delle performance di corsa, basata sull'algoritmo **SCORE 4.0** e integrata con **Strava**, **Open-Meteo** e **Google Gemini AI**.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://scorerun.streamlit.app/)

## 🚀 Funzionalità

- **Analisi OAuth Strava**: Importazione sicura delle attività.
- **SCORE 4.0 Engine**: Algoritmo proprietario che valuta l'efficienza bio-meccanica normalizzata per pendenza, peso e meteo.
- **Riegel Benchmark**: Confronto dinamico della prestazione rispetto al Record del Mondo sulla specifica distanza.
- **AI Coach (Gemini)**: Analisi qualitativa automatica basata su Zone di Potenza e Disaccoppiamento aerobico.
- **Deep Dive**: Grafici interattivi (Altair) per distribuzione zone, scatter plot HR/Power e deriva cardiaca.

## 🛠 Tech Stack

- **Frontend/Backend**: Python, Streamlit
- **Data Science**: Pandas, NumPy
- **Visualization**: Altair
- **External Services**:
  - Strava API v3 (Auth & Data Streams)
  - Open-Meteo API (Historical Weather)
  - Google Gemini 1.5 Flash (Generative AI Analysis)

## 📂 Struttura Modulare

Il progetto segue un'architettura pulita:
- `engine/`: Logica matematica pura (RunMetrics, ScoreEngine).
- `services/`: Gestione API esterne e caching.
- `ui/`: Componenti di visualizzazione e grafici.
- `app.py`: Controller principale dell'applicazione.
