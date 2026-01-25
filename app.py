import streamlit as st
import json
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from stravalib import Client
import requests

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="CorsaScore App", layout="wide", page_icon="🏃‍♂️")

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

# Usa secrets se disponibili, altrimenti input manuale
if 'strava' in st.secrets:
    strava_client_id = st.secrets['strava']['client_id']
    strava_client_secret = st.secrets['strava']['client_secret']
    st.sidebar.info("✅ Configurazione Strava caricata dai secrets.")
else:
    strava_client_id = st.sidebar.text_input("Strava Client ID", type="password", help="Ottieni il Client ID dalla tua app Strava su https://www.strava.com/settings/api")
    strava_client_secret = st.sidebar.text_input("Strava Client Secret", type="password", help="Ottieni il Client Secret dalla tua app Strava")

strava_code = st.sidebar.text_input("Authorization Code", help="Dopo aver autorizzato l'app, copia il code dall'URL di redirect")

if st.sidebar.button("🔗 Autorizza Strava"):
    if strava_client_id and strava_client_secret:
        auth_url = f"https://www.strava.com/oauth/authorize?client_id={strava_client_id}&response_type=code&redirect_uri=http://localhost:8501&scope=activity:read_all"
        st.sidebar.markdown(f"[Clicca qui per autorizzare]({auth_url})")
        st.sidebar.info("Dopo l'autorizzazione, copia il 'code' dall'URL e inseriscilo sopra.")
    else:
        st.sidebar.error("Inserisci Client ID e Client Secret prima di autorizzare.")

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

# --- FUNZIONE PER ELABORARE ATTIVITÀ STRAVA ---
def process_strava_activity(activity, client):
    try:
        # Ottieni i dettagli dell'attività
        detailed_activity = client.get_activity(activity.id)
        
        # Simula la struttura JSON Polar/Garmin
        date = pd.to_datetime(activity.start_date)
        duration_sec = activity.elapsed_time.total_seconds()
        distance = activity.distance.num  # in meters
        ascent = getattr(activity, 'total_elevation_gain', 0) or 0
        
        # Ottieni i streams (dati di potenza, HR, etc.)
        streams = client.get_activity_streams(activity.id, types=['watts', 'heartrate', 'time'])
        
        samples = []
        rr_data = []
        
        if 'time' in streams:
            time_stream = streams['time'].data
            if 'watts' in streams:
                power_data = streams['watts'].data
                for i, p in enumerate(power_data):
                    samples.append({'Power': p})
            if 'heartrate' in streams:
                hr_data = streams['heartrate'].data
                # Converti HR in RR intervals (approssimativo)
                for i in range(1, len(hr_data)):
                    rr_interval = 60000 / ((hr_data[i-1] + hr_data[i]) / 2)  # ms
                    rr_data.append(int(rr_interval))
        
        # Costruisci la struttura dati simile
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
        
        # Usa la stessa logica di process_running_file
        return process_running_file_from_data(data)
        
    except Exception as e:
        st.error(f"Errore processando attività Strava: {e}")
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
    if st.button("🔄 Carica Attività da Strava"):
        if strava_client_id and strava_client_secret and strava_code:
            try:
                # Scambia il code per il token
                token_response = requests.post(
                    'https://www.strava.com/oauth/token',
                    data={
                        'client_id': strava_client_id,
                        'client_secret': strava_client_secret,
                        'code': strava_code,
                        'grant_type': 'authorization_code'
                    }
                )
                token_data = token_response.json()
                access_token = token_data.get('access_token')
                
                if access_token:
                    st.session_state['strava_token'] = access_token
                    client = Client()
                    client.access_token = access_token
                    # Ottieni le attività recenti
                    activities = client.get_activities(limit=10)  # ultime 10 attività
                    strava_activities = list(activities)
                    st.success(f"Caricate {len(strava_activities)} attività da Strava!")
                else:
                    st.error("Errore nell'autenticazione Strava. Verifica il code.")
            except Exception as e:
                st.error(f"Errore caricando da Strava: {e}")
        else:
            st.warning("Inserisci Client ID, Client Secret e Authorization Code per caricare da Strava.")

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