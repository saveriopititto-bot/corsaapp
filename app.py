import streamlit as st
import json
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from stravalib import Client
import requests

# --- CONFIGURAZIONE PAGINA ---
# Usa icona personalizzata se disponibile, altrimenti emoji
import os
icon_path = "assets/icon.png"
if os.path.exists(icon_path):
    page_icon = icon_path
else:
    page_icon = "🏃‍♂️"

st.set_page_config(page_title="CorsaScore App", layout="wide", page_icon=page_icon)

st.title("🏃‍♂️ CorsaScore: Analisi Efficienza Aerobica")
st.markdown("""
Questa dashboard calcola il tuo **SCORE 2.0**.
Il sistema analizza la relazione tra la **Potenza (Watt)** e la **Frequenza Cardiaca**, 
penalizzando le sessioni dove si verifica un alto *Aerobic Decoupling* (deriva cardiaca).
""")

# --- SIDEBAR: PARAMETRI UTENTE ---
st.sidebar.header("⚙️ Parametri Atleta")
weight = st.sidebar.number_input("Peso (Kg)", value=74.0, step=0.1)
hr_rest = st.sidebar.number_input("BPM a Riposo", value=60)
hr_max = st.sidebar.number_input("BPM Massimi", value=185)
base_offset = st.sidebar.slider("Base Offset (Standard: 2.0)", 0.0, 5.0, 2.0, help="Sottrae un valore fisso per normalizzare il punteggio intorno allo zero o a una scala specifica.")

# --- SIDEBAR: INTEGRAZIONE STRAVA ---
st.sidebar.header("🏃‍♂️ Integrazione Strava")

# Controlla se i secrets sono configurati
strava_configured = 'strava' in st.secrets and 'client_id' in st.secrets['strava'] and 'client_secret' in st.secrets['strava']

if strava_configured:
    client_id = st.secrets['strava']['client_id']
    client_secret = st.secrets['strava']['client_secret']
    
    # Gestisci il flusso OAuth
    query_params = st.query_params
    
    if 'code' in query_params and not st.session_state.get('strava_token'):
        # Scambia il code per il token
        try:
            token_response = requests.post(
                'https://www.strava.com/oauth/token',
                data={
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'code': query_params['code'],
                    'grant_type': 'authorization_code'
                }
            )
            token_data = token_response.json()
            if 'access_token' in token_data:
                st.session_state['strava_token'] = token_data['access_token']
                st.success("✅ Connessione Strava riuscita!")
                # Pulisci i query params
                st.query_params.clear()
            else:
                st.error("Errore nell'autenticazione Strava.")
        except Exception as e:
            st.error(f"Errore: {e}")
    
    # Mostra stato connessione
    if 'strava_token' in st.session_state:
        st.sidebar.success("✅ Connesso a Strava")
        if st.sidebar.button("🔄 Aggiorna Dati Strava"):
            st.session_state['refresh_strava'] = True
            st.rerun()
    else:
        # Pulsante per connettere
        auth_url = f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri={st.secrets.get('strava', {}).get('redirect_uri', 'https://corsaappalpha.streamlit.app')}&scope=activity:read_all"
        st.sidebar.link_button("🔗 Connetti Strava", auth_url, help="Clicca per autorizzare l'accesso ai tuoi dati Strava")
        
else:
    st.sidebar.warning("⚠️ Integrazione Strava non configurata. Contatta l'amministratore.")

# Mediana Peer Group (Costante di riferimento)
MEDIAN_VAL = 1.40 

# --- FUNZIONE DI ELABORAZIONE ---
def process_running_file(file):
    try:
        data = json.load(file)
        
        # Check basic structure
        if 'DeviceLog' not in data or 'Samples' not in data['DeviceLog']:
            return None

        header = data['DeviceLog']['Header']
        
        # 1. Metadati Base
        date = pd.to_datetime(header.get('DateTime', pd.Timestamp.now()))
        ascent = header.get('Ascent', 0)
        distance = header.get('Distance', 0)
        duration_sec = header.get('Duration', 1)
        t_hours = duration_sec / 3600
        
        # Calcolo Pendenza (Grade)
        grade = ascent / distance if distance > 0 else 0
        
        # 2. Analisi Potenza
        samples = data['DeviceLog']['Samples']
        power_samples = [s['Power'] for s in samples if 'Power' in s]
        
        if not power_samples:
            return None # Skip files without power data
            
        avg_power = np.mean(power_samples)
        # Power Adjustment formula
        watt_adj = avg_power * (1 + grade)
        
        # 3. Analisi Cardiaca (R-R Intervals)
        rr_data = data['DeviceLog'].get('R-R', {}).get('Data', [])
        rr_data = [r for r in rr_data if r > 0] # Filter zeros
        
        if not rr_data:
            return None # Skip files without HR data

        avg_hr = 60000 / np.mean(rr_data)
        
        # %HRR (Heart Rate Reserve) calculation
        hrr_range = hr_max - hr_rest
        hrr_pct = (avg_hr - hr_rest) / hrr_range if hrr_range > 0 else 0
        
        # 4. Decoupling Calculation (Split Halves)
        # Split by time for HR (RR data is time-based)
        mid_time_ms = sum(rr_data) / 2
        curr_ms = 0
        h1_rr = []
        h2_rr = []
        
        for r in rr_data:
            if curr_ms < mid_time_ms:
                h1_rr.append(r)
            else:
                h2_rr.append(r)
            curr_ms += r
            
        hr1 = 60000 / np.mean(h1_rr) if h1_rr else avg_hr
        hr2 = 60000 / np.mean(h2_rr) if h2_rr else avg_hr
        
        # Split by samples for Power (Assuming 1Hz sampling approx)
        mid_p = len(power_samples) // 2
        p1 = np.mean(power_samples[:mid_p]) if power_samples else 0
        p2 = np.mean(power_samples[mid_p:]) if power_samples else 0
        
        # Efficiency Factors (EF)
        ef1 = p1 / hr1 if hr1 > 0 else 0
        ef2 = p2 / hr2 if hr2 > 0 else 0
        
        # Decoupling %
        decoupling = (ef1 - ef2) / ef1 if ef1 > 0 else 0
        
        # 5. FORMULA SCORE 2.0
        # Efficiency Ratio: (Watts/Kg) per %HRR unit
        w_kg = watt_adj / weight
        efficiency_ratio = w_kg / hrr_pct if hrr_pct > 0 else 0
        
        # Decoupling Penalty: normalized by duration (sqrt of hours)
        # Longer runs with low decoupling are rewarded more than short runs
        d_penalty = decoupling / np.sqrt(t_hours) if t_hours > 0 else 0
        
        # Final Score
        score = (efficiency_ratio - base_offset) * (1 - d_penalty)
        
        return {
            "Data": date,
            "Watt_Adj": round(watt_adj, 1), 
            "HR_Avg": round(avg_hr, 1),
            "%HRR": round(hrr_pct*100, 1),
            "Decoupling": round(decoupling*100, 2),
            "SCORE_2": round(score, 3),
            "Duration_Min": round(duration_sec/60, 0)
        }
    except Exception as e:
        st.error(f"Errore processando il file: {e}")
        return None

# --- FUNZIONE AUSILIARIA PER GESTIRE DURATE ---
def ensure_seconds(duration_obj):
    """Converte oggetti Duration di Strava, timedelta o altri tipi in float secondi."""
    if hasattr(duration_obj, 'total_seconds'):
        # Per timedelta
        return duration_obj.total_seconds()
    elif hasattr(duration_obj, 'seconds'):
        # Per oggetti Duration di stravalib
        return float(duration_obj.seconds)
    else:
        try:
            return float(duration_obj)
        except (TypeError, ValueError):
            return 0.0

# --- FUNZIONE PER ELABORARE ATTIVITÀ STRAVA ---
def process_strava_activity(activity, client):
    try:
        # Ottieni i dettagli dell'attività
        detailed_activity = client.get_activity(activity.id)
        
        # Ottieni i streams (dati di potenza, HR, etc.) - CRUCIALE per il decoupling
        streams = client.get_activity_streams(activity.id, types=['watts', 'heartrate', 'time'])
        
        # Verifica che abbiamo i dati necessari per il calcolo dello score
        has_power = 'watts' in streams and streams['watts'].data
        has_hr = 'heartrate' in streams and streams['heartrate'].data
        has_time = 'time' in streams and streams['time'].data
        
        if not (has_power and has_hr and has_time):
            st.warning(f"Attività di corsa {activity.name}: dati insufficienti (mancano power, HR o time streams)")
            return None
        
        # Simula la struttura JSON Polar/Garmin
        date = pd.to_datetime(activity.start_date)
        duration_sec = ensure_seconds(activity.elapsed_time)
        distance = activity.distance.num if hasattr(activity.distance, 'num') else float(activity.distance)  # in meters
        ascent = getattr(activity, 'total_elevation_gain', 0) or 0
        
        # Costruisci samples e rr_data dai streams
        samples = []
        rr_data = []
        
        time_stream = streams['time'].data
        power_data = streams['watts'].data
        hr_data = streams['heartrate'].data
        
        # Assumi che tutti i streams abbiano la stessa lunghezza
        min_length = min(len(time_stream), len(power_data), len(hr_data))
        
        for i in range(min_length):
            if i < len(power_data):
                samples.append({'Power': power_data[i]})
        
        # Converti HR in RR intervals (intervalli R-R)
        for i in range(1, min_length):
            if i < len(hr_data):
                # Calcola RR interval come tempo tra battiti (in ms)
                # Assumi frequenza di campionamento costante
                rr_interval = 1000.0 / ((hr_data[i-1] + hr_data[i]) / 2 / 60)  # ms
                rr_data.append(int(rr_interval))
        
        # Verifica che abbiamo dati sufficienti
        if not samples or not rr_data:
            st.warning(f"Attività di corsa {activity.name}: dati di power o HR insufficienti dopo elaborazione")
            return None
        
        # Costruisci la struttura dati simile a Polar/Garmin
        data = {
            'DeviceLog': {
                'Header': {
                    'DateTime': activity.start_date.isoformat(),
                    'Ascent': ascent,
                    'Distance': distance,
                    'Duration': duration_sec
                },
                'Samples': samples,
                'R-R': {'Data': rr_data}
            }
        }
        
        # Usa la stessa logica di process_running_file_from_data
        return process_running_file_from_data(data)
        
    except Exception as e:
        st.error(f"Errore elaborando attività Strava {getattr(activity, 'name', 'sconosciuta')}: {e}")
        return None

# --- FUNZIONE AUSILIARIA PER PROCESSARE DATI DIRETTAMENTE ---
def process_running_file_from_data(data):
    try:
        # Check basic structure
        if 'DeviceLog' not in data or 'Samples' not in data['DeviceLog']:
            return None

        header = data['DeviceLog']['Header']
        
        # 1. Metadati Base
        date = pd.to_datetime(header.get('DateTime', pd.Timestamp.now()))
        ascent = header.get('Ascent', 0)
        distance = header.get('Distance', 0)
        duration_sec = header.get('Duration', 1)
        t_hours = duration_sec / 3600
        
        # Calcolo Pendenza (Grade)
        grade = ascent / distance if distance > 0 else 0
        
        # 2. Analisi Potenza
        samples = data['DeviceLog']['Samples']
        power_samples = [s['Power'] for s in samples if 'Power' in s]
        
        if not power_samples:
            return None # Skip files without power data
            
        avg_power = np.mean(power_samples)
        # Power Adjustment formula
        watt_adj = avg_power * (1 + grade)
        
        # 3. Analisi Cardiaca (R-R Intervals)
        rr_data = data['DeviceLog'].get('R-R', {}).get('Data', [])
        rr_data = [r for r in rr_data if r > 0] # Filter zeros
        
        if not rr_data:
            return None # Skip files without HR data

        avg_hr = 60000 / np.mean(rr_data)
        
        # %HRR (Heart Rate Reserve) calculation
        hrr_range = hr_max - hr_rest
        hrr_pct = (avg_hr - hr_rest) / hrr_range if hrr_range > 0 else 0
        
        # 4. Decoupling Calculation (Split Halves)
        # Split by time for HR (RR data is time-based)
        mid_time_ms = sum(rr_data) / 2
        curr_ms = 0
        h1_rr = []
        h2_rr = []
        
        for r in rr_data:
            if curr_ms < mid_time_ms:
                h1_rr.append(r)
            else:
                h2_rr.append(r)
            curr_ms += r
            
        hr1 = 60000 / np.mean(h1_rr) if h1_rr else avg_hr
        hr2 = 60000 / np.mean(h2_rr) if h2_rr else avg_hr
        
        # Split by samples for Power (Assuming 1Hz sampling approx)
        mid_p = len(power_samples) // 2
        p1 = np.mean(power_samples[:mid_p]) if power_samples else 0
        p2 = np.mean(power_samples[mid_p:]) if power_samples else 0
        
        # Efficiency Factors (EF)
        ef1 = p1 / hr1 if hr1 > 0 else 0
        ef2 = p2 / hr2 if hr2 > 0 else 0
        
        # Decoupling %
        decoupling = (ef1 - ef2) / ef1 if ef1 > 0 else 0
        
        # 5. FORMULA SCORE 2.0
        # Efficiency Ratio: (Watts/Kg) per %HRR unit
        w_kg = watt_adj / weight
        efficiency_ratio = w_kg / hrr_pct if hrr_pct > 0 else 0
        
        # Decoupling Penalty: normalized by duration (sqrt of hours)
        # Longer runs with low decoupling are rewarded more than short runs
        d_penalty = decoupling / np.sqrt(t_hours) if t_hours > 0 else 0
        
        # Final Score
        score = (efficiency_ratio - base_offset) * (1 - d_penalty)
        
        return {
            "Data": date,
            "Watt_Adj": round(watt_adj, 1), 
            "HR_Avg": round(avg_hr, 1),
            "%HRR": round(hrr_pct*100, 1),
            "Decoupling": round(decoupling*100, 2),
            "SCORE_2": round(score, 3),
            "Duration_Min": round(duration_sec/60, 0)
        }
    except Exception as e:
        st.error(f"Errore processando i dati: {e}")
        return None

# --- UPLOAD FILE ---
st.header("📂 Carica Dati")
upload_option = st.radio("Scegli fonte dati:", ["File JSON (Polar/Garmin)", "Strava API"])

uploaded_files = None
strava_activities = None

if upload_option == "File JSON (Polar/Garmin)":
    uploaded_files = st.file_uploader(
        "📂 Carica i tuoi file JSON (Polar/Garmin Data)", 
        type="json", 
        accept_multiple_files=True
    )
else:  # Strava
    if st.button("🔄 Carica Attività da Strava") or st.session_state.get('refresh_strava', False):
        if strava_configured and 'strava_token' in st.session_state:
            try:
                client = Client()
                client.access_token = st.session_state['strava_token']
                # Ottieni le attività recenti e filtra solo le corse
                all_activities = client.get_activities(limit=50)  # Prendi più attività per avere abbastanza corse
                strava_activities = [activity for activity in all_activities if activity.type == "Run"]
                
                if strava_activities:
                    st.success(f"✅ Caricate {len(strava_activities)} attività di corsa da Strava!")
                else:
                    st.warning("Nessuna attività di corsa trovata nelle ultime 50 attività.")
                
                st.session_state['refresh_strava'] = False
            except Exception as e:
                st.error(f"Errore caricando da Strava: {e}")
                # Se token scaduto, chiedi riconnessione
                if 'token' in str(e).lower():
                    st.warning("Token scaduto. Riconnettiti a Strava.")
                    del st.session_state['strava_token']
        else:
            st.warning("Connettiti prima a Strava usando il pulsante nella sidebar.")

if (uploaded_files or strava_activities):
    results = []
    with st.spinner('Elaborazione dati in corso...'):
        # Elabora file JSON
        if uploaded_files:
            for file in uploaded_files:
                res = process_running_file(file)
                if res:
                    results.append(res)
                else:
                    st.warning(f"Saltato file {file.name}: Dati insufficienti (manca Power o R-R).")
        
        # Elabora attività Strava
        if strava_activities:
            if 'strava_token' in st.session_state:
                client = Client()
                client.access_token = st.session_state['strava_token']
                for activity in strava_activities:
                    res = process_strava_activity(activity, client)
                    if res:
                        results.append(res)
                    else:
                        st.warning(f"Saltata attività {activity.name}: Dati insufficienti.")
            else:
                st.error("Token Strava non disponibile. Riautenticati.")

    if results:
        df = pd.DataFrame(results).sort_values("Data")
        
        # --- TOP METRICS ---
        st.markdown("---")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Score Medio", f"{df['SCORE_2'].mean():.2f}")
        m2.metric("Decoupling Medio", f"{df['Decoupling'].mean():.2f}%")
        m3.metric("Watt Adj Medi", f"{df['Watt_Adj'].mean():.0f} W")
        m4.metric("%HRR Media", f"{df['%HRR'].mean():.1f}%")
        st.markdown("---")

        # --- VISUALIZZAZIONE AVANZATA ---
        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("📈 Trend Efficienza & Decoupling")
            
            # Create figure with secondary y-axis
            fig = go.Figure()

            # Add Score Trace
            fig.add_trace(go.Scatter(
                x=df['Data'], y=df['SCORE_2'],
                name="Score 2.0", mode='lines+markers',
                line=dict(color='#00CC96', width=3)
            ))

            # Add Decoupling Bars
            fig.add_trace(go.Bar(
                x=df['Data'], y=df['Decoupling'],
                name="Decoupling %", yaxis='y2',
                marker_color='rgba(239, 85, 59, 0.5)'
            ))
            
            # Add Median Line
            fig.add_hline(y=MEDIAN_VAL, line_dash="dot", annotation_text="Peer Median", annotation_position="top left")

            # Layout
            fig.update_layout(
                yaxis=dict(title="Score 2.0"),
                yaxis2=dict(title="Decoupling %", overlaying='y', side='right', range=[-5, 20]),
                legend=dict(x=0, y=1.1, orientation='h'),
                hovermode="x unified"
            )
            
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("📋 Dettaglio Sessioni")
            st.dataframe(
                df[["Data", "SCORE_2", "%HRR", "Decoupling", "Duration_Min"]].style.background_gradient(subset=['SCORE_2'], cmap='Greens'), 
                height=400,
                hide_index=True
            )

        # --- INSIGHTS ---
        avg_score = df["SCORE_2"].mean()
        if avg_score > MEDIAN_VAL:
            st.success(f"🚀 Ottimo lavoro! Il tuo Score medio ({avg_score:.2f}) è superiore alla media del gruppo ({MEDIAN_VAL}).")
        else:
            st.info(f"💡 C'è margine di miglioramento. Il tuo Score ({avg_score:.2f}) è sotto la media del gruppo ({MEDIAN_VAL}). Concentrati sulla base aerobica.")
            
        # Mathematical Context
        with st.expander("ℹ️ Come viene calcolato lo Score?"):
            st.markdown(r"""
            Lo **Score 2.0** combina l'efficienza meccanica con la tenuta aerobica:
            
            $$
            \text{Score} = \left( \frac{\text{Watt}_{adj} / \text{Kg}}{\%HRR} - \text{Offset} \right) \times (1 - D_{penalty})
            $$
            
            Dove il **Decoupling Penalty** ($D_{penalty}$) riduce lo score se la frequenza cardiaca deriva verso l'alto a parità di potenza:
            
            $$
            D_{penalty} = \frac{\text{Decoupling}}{\sqrt{t_{hours}}}
            $$
            """)
            
            # Contextual image for Aerobic Decoupling
            st.markdown("Il decoupling misura quanto la frequenza cardiaca si 'scollega' dalla potenza con il passare del tempo.")
            #