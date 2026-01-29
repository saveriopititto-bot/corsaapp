import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta

# --- 1. CONFIG & VALIDATION (MUST BE FIRST) ---
from config import Config

# Check health before loading heavier modules
missing_secrets = Config.check_secrets()
if missing_secrets:
    st.error(f"❌ Missing Secrets: {', '.join(missing_secrets)}. Please check `.streamlit/secrets.toml`.")
    st.stop()

# --- 2. IMPORT MODULES ---
from engine.core import ScoreEngine, RunMetrics
from services.api import StravaService, WeatherService, AICoachService
from services.db import DatabaseService
from ui.visuals import render_benchmark_chart, render_zones_chart, render_scatter_chart, render_history_table, render_trend_chart
from ui.style import apply_custom_style

# --- 3. PAGE SETUP ---
st.set_page_config(page_title=Config.APP_TITLE, page_icon=Config.APP_ICON, layout="wide", initial_sidebar_state="collapsed")
apply_custom_style()

# --- 4. SERVICES INIT ---
# Secrets are guaranteed to exist by check_secrets()
strava_creds = Config.get_strava_creds()
supa_creds = Config.get_supabase_creds()
gemini_key = Config.get_gemini_key()

auth_svc = StravaService(strava_creds["client_id"], strava_creds["client_secret"])
db_svc = DatabaseService(supa_creds["url"], supa_creds["key"])

import concurrent.futures

# --- 5. STATE MANAGEMENT ---
if "strava_token" not in st.session_state: st.session_state.strava_token = None
if "data" not in st.session_state: st.session_state.data = db_svc.get_history()
if "demo_mode" not in st.session_state: st.session_state.demo_mode = False

# Callback Auth
if "code" in st.query_params and not st.session_state.strava_token:
    tk = auth_svc.get_token(st.query_params["code"])
    if tk: 
        st.session_state.strava_token = tk
        st.query_params.clear()
        st.rerun()

# --- 6. HEADER & PROFILE ---
col_head, col_prof = st.columns([3, 1], gap="large")
with col_head: 
    st.title(Config.APP_TITLE)
    if st.session_state.demo_mode:
        st.caption("🔴 DEMO MODE - Dati simulati")

with col_prof:
    if st.session_state.strava_token:
        ath = st.session_state.strava_token.get("athlete", {})
        st.markdown(f"<div style='text-align:right'><strong>{ath.get('firstname')} {ath.get('lastname')}</strong></div>", unsafe_allow_html=True)
        if st.button("Logout", key="logout"):
            st.session_state.strava_token = None
            st.rerun()
    elif st.session_state.demo_mode:
        st.markdown(f"<div style='text-align:right'><strong>Utente Demo</strong></div>", unsafe_allow_html=True)
        if st.button("Esci Demo"):
            st.session_state.demo_mode = False
            st.session_state.data = []
            st.rerun()
    else:
        c_login, c_demo = st.columns([3, 2])
        with c_login:
            st.link_button("🔗 Connetti Strava", auth_svc.get_link("https://scorerun.streamlit.app/"), type="primary", use_container_width=True)
        with c_demo:
            if st.button("👀 Demo", use_container_width=True):
                st.session_state.demo_mode = True
                # Carica dati finti
                st.session_state.data = [
                    {"id": 101, "Data": datetime.now()-timedelta(days=1), "Dist (km)": 10.5, "Power": 240, "HR": 155, "Decoupling": 3.2, "SCORE": 0.29, "Rank": "🥇 Pro", "WR_Pct": 76.5, "Meteo": "18.5°C", "raw_watts": [240]*2000, "raw_hr": [155]*2000},
                    {"id": 102, "Data": datetime.now()-timedelta(days=3), "Dist (km)": 21.1, "Power": 230, "HR": 160, "Decoupling": 6.5, "SCORE": 0.31, "Rank": "🏆 Elite", "WR_Pct": 73.0, "Meteo": "22.0°C", "raw_watts": [230]*4000, "raw_hr": [160]*4000},
                    {"id": 103, "Data": datetime.now()-timedelta(days=6), "Dist (km)": 5.0, "Power": 260, "HR": 165, "Decoupling": 1.1, "SCORE": 0.18, "Rank": "🥉 Intermediate", "WR_Pct": 68.5, "Meteo": "15.0°C", "raw_watts": [260]*1000, "raw_hr": [165]*1000},
                ]
                st.rerun()

# --- 7. ATHLETE PARAMS ---
weight, hr_max, hr_rest, ftp, age = Config.DEFAULT_WEIGHT, Config.DEFAULT_HR_MAX, Config.DEFAULT_HR_REST, Config.DEFAULT_FTP, Config.DEFAULT_AGE

if st.session_state.strava_token:
    ath = st.session_state.strava_token.get("athlete", {})
    def_w = float(ath.get('weight', 0)) if ath.get('weight', 0) > 0 else Config.DEFAULT_WEIGHT
    
    with st.expander("⚙️ Profilo Atleta (Parametri)", expanded=False):
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: weight = st.number_input("Peso (kg)", value=def_w)
        with c2: hr_max = st.number_input("FC Max", value=Config.DEFAULT_HR_MAX)
        with c3: hr_rest = st.number_input("FC Riposo", value=Config.DEFAULT_HR_REST)
        with c4: ftp = st.number_input("FTP (W)", value=Config.DEFAULT_FTP)
        with c5: age = st.number_input("Età", value=Config.DEFAULT_AGE, help="Fondamentale per il calcolo percentile")

st.divider()

# --- 8. MAIN LOGIC ---
if not st.session_state.strava_token and not st.session_state.demo_mode:
    st.info("👆 Connetti Strava per accedere alla Dashboard Pro o prova la modalità Demo.")
else:
    # TOOLBAR (Refresh & Filtro)
    spL, col_ctrl, spR = st.columns([3, 2, 3])
    with col_ctrl:
        c_drop, c_btn = st.columns([2, 1], gap="small", vertical_alignment="bottom")
        with c_drop:
            opts = {"30 Giorni": 30, "90 Giorni": 90, "12 Mesi": 365, "Storico": 3650}
            sel_label = st.selectbox("Periodo:", list(opts.keys()), index=2)
            days_fetch = opts[sel_label]
        with c_btn:
            do_sync = st.button("🔄 Sync", type="primary", use_container_width=True, disabled=st.session_state.demo_mode)

    # SYNC ENGINE (PARALLEL)
    if do_sync and not st.session_state.demo_mode:
        eng = ScoreEngine()
        aid = st.session_state.strava_token.get("athlete", {}).get("id", 0)
        tk = st.session_state.strava_token["access_token"]
        
        with st.status(f"Analisi attività in corso ({sel_label})...", expanded=True) as status:
            st.write("📥 Scaricamento lista attività da Strava...")
            act_list = auth_svc.fetch_activities(tk, days_back=days_fetch)
            
            if not act_list: 
                status.update(label="Nessuna attività trovata.", state="error")
            else:
                # Filtraggio esistenti
                ex_ids = [r['id'] for r in st.session_state.data]
                to_process = [s for s in act_list if s['id'] not in ex_ids]
                
                if not to_process:
                    status.update(label="Tutte le attività sono già aggiornate!", state="complete")
                else:
                    st.write(f"⚙️ Elaborazione di {len(to_process)} nuove attività...")
                    p_bar = st.progress(0)
                    new_cnt = 0
                    
                    # Funzione worker per processare singola attività
                    def process_activity(s):
                        try:
                            streams = auth_svc.fetch_streams(tk, s['id'])
                            if streams and 'watts' in streams and 'heartrate' in streams:
                                dt = datetime.strptime(s['start_date_local'], "%Y-%m-%dT%H:%M:%SZ")
                                lat_lng = s.get('start_latlng', [])
                                
                                # Meteo Reale
                                t, h = 20.0, 50.0
                                if lat_lng:
                                    t, h = WeatherService.get_weather(lat_lng[0], lat_lng[1], dt.strftime("%Y-%m-%d"), dt.hour)
                                
                                m = RunMetrics(s.get('average_watts', 0), s.get('average_heartrate', 0), s.get('distance', 0), s.get('moving_time', 0), s.get('total_elevation_gain', 0), weight, hr_max, hr_rest, t, h)
                                dec = eng.calculate_decoupling(streams['watts']['data'], streams['heartrate']['data'])
                                
                                score, details, wcf, wr_p = eng.compute_score(m, dec)
                                rnk, _ = eng.get_rank(score)
                                
                                return {
                                    "id": s['id'], "Data": dt.strftime("%Y-%m-%d"), 
                                    "Dist (km)": round(m.distance_meters/1000, 2),
                                    "Power": int(m.avg_power), "HR": int(m.avg_hr),
                                    "Decoupling": round(dec*100, 1), "WCF": round(wcf, 2),
                                    "SCORE": round(score, 2), "WR_Pct": round(wr_p, 1),
                                    "Rank": rnk, "Meteo": f"{t}°C",
                                    "SCORE_DETAIL": details,
                                    "raw_watts": streams['watts']['data'], "raw_hr": streams['heartrate']['data']
                                }
                        except Exception as e:
                            print(f"Error processing {s['id']}: {e}")
                            return None
                        return None

                    # Parallel Execution
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        futures = {executor.submit(process_activity, s): s for s in to_process}
                        
                        for i, future in enumerate(concurrent.futures.as_completed(futures)):
                            res = future.result()
                            if res:
                                db_svc.save_run(res, aid) # Save to DB synchronous (safer for SQLite/Supabase concurrent limits)
                                new_cnt += 1
                            p_bar.progress((i+1)/len(to_process))
                    
                    st.session_state.data = db_svc.get_history()
                    status.update(label=f"Completato! Aggiunte {new_cnt} attività.", state="complete")
                    if new_cnt: st.balloons(); time.sleep(1); st.rerun()

    # --- DASHBOARD INTELLIGENTE ---
    if st.session_state.data:
        st.markdown("<br>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["📊 Dashboard Pro", "🔬 Laboratorio"])
        
        # 1. PREPARAZIONE DATI + MEDIE MOBILI
        df = pd.DataFrame(st.session_state.data)
        df['Data'] = pd.to_datetime(df['Data'])
        
        # ORDINE CRONOLOGICO (Fondamentale per rolling)
        df = df.sort_values("Data", ascending=True)
        df["SCORE_MA_7"] = df["SCORE"].rolling(7, min_periods=1).mean()
        df["SCORE_MA_28"] = df["SCORE"].rolling(28, min_periods=1).mean()
        
        # TORNA ORDINE INVERSO (Per visualizzazione: Oggi -> Ieri)
        df = df.sort_values("Data", ascending=False)
        
        # Filtro Periodo
        if 'days_fetch' in locals():
            cutoff = datetime.now() - timedelta(days=days_fetch)
            df = df[df['Data'] > cutoff]

        if df.empty: st.warning("Nessun dato nel periodo."); st.stop()

        # CALCOLI KPI AVANZATI
        cur_run = df.iloc[0]
        cur_score = cur_run['SCORE']
        cur_ma7 = cur_run['SCORE_MA_7']
        
        # Delta Intelligente (su MA7)
        if len(df) > 1:
            prev_ma7 = df.iloc[1]['SCORE_MA_7']
            delta_val = cur_ma7 - prev_ma7
        else:
            delta_val = 0
            
        # Logica Semaforica
        if delta_val > 0.005: trend_lbl, trend_col = "In Crescita ↗", "normal" # Streamlit gestisce il verde col '+'
        elif delta_val < -0.005: trend_lbl, trend_col = "In Calo ↘", "inverse"
        else: trend_lbl, trend_col = "Stabile →", "off"

        # Percentile Età
        eng = ScoreEngine()
        age_pct = eng.age_adjusted_percentile(cur_score, age)

        # TAB 1
        with t1:
            # HERO (3 Cerchi)
            c_prev, c_main, c_next = st.columns([1, 1.5, 1], gap="small")
            
            with c_prev: # Mostriamo la Media 7gg passata invece del singolo score
                st.markdown(f"""<div style="text-align:center; opacity:0.6"><small>TREND IERI</small><br><h1>{round(prev_ma7, 2) if len(df)>1 else '-'}</h1></div>""", unsafe_allow_html=True)
            with c_main:
                 st.markdown(f"""
                <div style="display: flex; justify-content: center;">
                    <div class="score-circle">
                         <span style="color: #999; font-size: 0.7rem; font-weight: 700;">SCORE OGGI</span>
                         <span style="color: #2D3436; font-size: 3.2rem; font-weight: 800; line-height: 1;">{cur_score}</span>
                         <div style="background:#CDFAD5; color:#2D3436; padding:3px 12px; border-radius:20px; font-size:0.7rem; font-weight:700; margin-top:5px;">{cur_run['Rank'].split('/')[0]}</div>
                    </div>
                </div>""", unsafe_allow_html=True)
            with c_next: # Percentile invece dell'atteso
                st.markdown(f"""<div style="text-align:center; opacity:0.8"><small style="color:#6C5DD3">PERCENTILE (ETÀ)</small><br><h1 style="color:#6C5DD3">{age_pct}%</h1></div>""", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # KPI INTELLIGENTI
            k1, k2, k3, k4, k5 = st.columns(5)
            st.markdown("""<style>div[data-testid="stMetric"] { background-color: white; border-radius: 10px; padding: 10px; border: 1px solid #eee; box-shadow: 0 2px 5px rgba(0,0,0,0.02); text-align: center; } </style>""", unsafe_allow_html=True)
            
            with k1: st.metric("Efficienza", f"{cur_run['Decoupling']}%", "Drift")
            with k2: st.metric("Potenza", f"{cur_run['Power']}w", f"{cur_run['Meteo']}")
            with k3: st.metric("Benchmark", f"{cur_run['WR_Pct']}%", "vs WR")
            with k4: st.metric("Media 28gg", f"{round(cur_run['SCORE_MA_28'], 2)}", "Solidità")
            with k5: st.metric("Trend (7gg)", trend_lbl, f"{delta_val:+.3f}", delta_color=trend_col)
            
            st.markdown("<br>", unsafe_allow_html=True)

            # SCORE SPIEGABILE (Expander)
            with st.expander("🔍 Perché questo punteggio? (Breakdown)", expanded=True):
                # Se i dettagli non sono salvati (vecchie run), li ricalcoliamo al volo
                if "SCORE_DETAIL" in cur_run and isinstance(cur_run["SCORE_DETAIL"], dict):
                    dets = cur_run["SCORE_DETAIL"]
                else:
                    # Fallback calcolo al volo
                    eng = ScoreEngine()
                    # Creiamo oggetto metriche fittizio veloce
                    m_temp = RunMetrics(cur_run['Power'], cur_run['HR'], cur_run['Dist (km)']*1000, 0, 0, weight, hr_max, hr_rest, 20, 50)
                    _, dets, _, _ = eng.compute_score(m_temp, cur_run['Decoupling']/100)

                d1, d2, d3, d4 = st.columns(4)
                with d1: st.metric("🚀 Contributo Potenza", f"+{dets.get('Potenza',0)}")
                with d2: st.metric("🔋 Contributo Volume", f"+{dets.get('Volume',0)}")
                with d3: st.metric("💓 Contributo Intensità", f"+{dets.get('Intensità',0)}")
                with d4: st.metric("📉 Malus Efficienza", f"{dets.get('Malus Efficienza',0)}")
                
                st.caption("Nota: La somma di questi fattori genera il tuo Score finale.")

            with st.expander("📂 Archivio Attività", expanded=False): render_history_table(df)

        # TAB 2
        with t2:
            st.markdown("### 🔬 Laboratorio Analisi")
            render_trend_chart(df.head(60)) # Mostriamo ultimi 60gg nel grafico
            st.divider()
            
            # ... (sezione dettaglio singolo rimane uguale) ...
            opts = {r['id']: f"{r['Data'].strftime('%Y-%m-%d')} - {r['Dist (km)']}km" for i, r in df.iterrows()}
            sel = st.selectbox("Seleziona:", list(opts.keys()), format_func=lambda x: opts[x])
            run = df[df['id'] == sel].iloc[0].to_dict()
            
            c_ai, c_ch = st.columns([1, 2])
            with c_ai:
                st.markdown("##### � Analisi Corsa")
                if run.get('ai_feedback'):
                    st.success("Analisi salvata"); st.write(run.get('ai_feedback'))
                else:
                    if st.button("✨ Genera Analisi"):
                        coach = AICoachService(gemini_key)
                        res = coach.get_feedback(run, ScoreEngine().calculate_zones(run['raw_watts'], ftp))
                        st.write(res); db_svc.update_ai_feedback(run['id'], res)
            with c_ch:
                render_scatter_chart(run['raw_watts'], run['raw_hr'])
                render_zones_chart(ScoreEngine().calculate_zones(run['raw_watts'], ftp))
