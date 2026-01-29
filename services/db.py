import streamlit as st
from supabase import create_client, Client

class DatabaseService:
    def __init__(self, url, key):
        self.supabase: Client = create_client(url, key)

    def update_ai_feedback(self, run_id, feedback_text):
        """Salva il commento dell'AI nel DB per non rigenerarlo."""
        try:
            self.client.table("runs").update({"ai_feedback": feedback_text}).eq("id", run_id).execute()
            return True
        except Exception as e:
            print(f"Errore update AI: {e}")
            return False

    def save_run(self, run_data, athlete_id):
        """Salva o aggiorna una corsa nel DB (Upsert)"""
        # Prepariamo il payload per Supabase
        payload = {
            "id": run_data['id'],
            "athlete_id": athlete_id,
            "date": run_data['Data'],
            "distance_km": run_data['Dist (km)'],
            "duration_sec": len(run_data['raw_watts']), # Stima approx
            "avg_power": run_data['Power'],
            "avg_hr": run_data['HR'],
            "decoupling": run_data['Decoupling'],
            "score": run_data['SCORE'],
            "wcf": run_data['WCF'],
            "wr_pct": run_data['WR_Pct'],
            "rank": run_data['Rank'],
            "meteo_desc": run_data['Meteo'],
            # Serializziamo i dati grezzi in JSON
            "raw_data": {
                "watts": run_data['raw_watts'],
                "hr": run_data['raw_hr']
            }
        }
        
        try:
            # upsert = insert or update se l'ID esiste già
            self.supabase.table("runs").upsert(payload).execute()
            return True
        except Exception as e:
            st.error(f"Errore DB Save: {e}")
            return False

    def get_history(self, athlete_id=None, limit=50):
        """Carica lo storico dal DB"""
        try:
            query = self.supabase.table("runs").select("*").order("date", desc=True).limit(limit)
            
            # Se volessimo filtrare per atleta (futuro)
            # if athlete_id: query = query.eq("athlete_id", athlete_id)
            
            response = query.execute()
            data = response.data
            
            # Riconvertiamo il formato DB nel formato App
            processed = []
            for row in data:
                processed.append({
                    "id": row['id'],
                    "Data": row['date'],
                    "Dist (km)": row['distance_km'],
                    "Power": row['avg_power'],
                    "HR": row['avg_hr'],
                    "Decoupling": row['decoupling'],
                    "WCF": row['wcf'],
                    "SCORE": row['score'],
                    "WR_Pct": row['wr_pct'],
                    "Rank": row['rank'],
                    "Meteo": row['meteo_desc'],
                    # Estraiamo i dati grezzi dal JSONB
                    "raw_watts": row['raw_data']['watts'],
                    "raw_hr": row['raw_data']['hr']
                })
            return processed
        except Exception as e:
            st.error(f"Errore DB Load: {e}")
            return []
