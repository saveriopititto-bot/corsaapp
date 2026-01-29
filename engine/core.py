import math
from config import Config

class RunMetrics:
    def __init__(self, avg_power, avg_hr, distance, moving_time, elevation, weight, hr_max, hr_rest, temp, humidity):
        self.avg_power = avg_power
        self.avg_hr = avg_hr
        self.distance_meters = distance
        self.moving_time_seconds = moving_time
        self.elevation_gain = elevation
        self.weight = weight
        self.hr_max = hr_max
        self.hr_rest = hr_rest
        self.temp = temp
        self.humidity = humidity
        
    @property
    def avg_speed_mps(self):
        if self.moving_time_seconds > 0:
            return self.distance_meters / self.moving_time_seconds
        return 0

class ScoreEngine:
    def calculate_zones(self, watts_stream, ftp):
        if not watts_stream or not ftp: return {}
        zones = {"Z1": 0, "Z2": 0, "Z3": 0, "Z4": 0, "Z5": 0}
        for w in watts_stream:
            if w < 0.55 * ftp: zones["Z1"] += 1
            elif w < 0.75 * ftp: zones["Z2"] += 1
            elif w < 0.90 * ftp: zones["Z3"] += 1
            elif w < 1.05 * ftp: zones["Z4"] += 1
            else: zones["Z5"] += 1
        total = len(watts_stream)
        if total == 0: return zones
        return {k: round((v/total)*100, 1) for k, v in zones.items()}

    def calculate_decoupling(self, power_stream, hr_stream):
        if not power_stream or not hr_stream or len(power_stream) != len(hr_stream):
            return 0.0
        
        # Split in due metà
        mid = len(power_stream) // 2
        p1, p2 = power_stream[:mid], power_stream[mid:]
        h1, h2 = hr_stream[:mid], hr_stream[mid:]
        
        # Gestione divisione per zero
        avg_p1 = sum(p1)/len(p1) if len(p1) > 0 else 1
        avg_p2 = sum(p2)/len(p2) if len(p2) > 0 else 1
        avg_h1 = sum(h1)/len(h1) if len(h1) > 0 else 1
        avg_h2 = sum(h2)/len(h2) if len(h2) > 0 else 1
        
        ratio1 = avg_p1 / avg_h1 if avg_h1 > 0 else 0
        ratio2 = avg_p2 / avg_h2 if avg_h2 > 0 else 0
        
        if ratio1 == 0: return 0.0
        return (ratio1 - ratio2) / ratio1

    def age_adjusted_percentile(self, score, age):
        """Calcola il percentile basato sull'età (Mock statistico)"""
        # Semplificazione statistica: i punteggi calano con l'età.
        # Definiamo la 'media' (mu) e 'deviazione standard' (sigma) attesa per fascia.
        if age < 30: mu, sigma = 0.22, 0.05
        elif age < 40: mu, sigma = 0.20, 0.05
        elif age < 50: mu, sigma = 0.18, 0.04
        else: mu, sigma = 0.16, 0.04
        
        # Z-score: quanto sei distante dalla media della tua età?
        z = (score - mu) / sigma
        
        # Conversione approssimativa Z -> Percentile (Base 50%, 1 sigma = +34%)
        # Formula semplificata per evitare import scipy
        pct = 50 + (z * 34)
        return max(1.0, min(99.9, round(pct, 1)))

    def compute_score(self, m: RunMetrics, decoupling):
        # 1. World Class Factor (Benchmark Power/Weight)
        w_kg = m.avg_power / m.weight
        wcf = min(w_kg / Config.WR_WKG, 1.0)
        
        # 2. Volume Factor (Logaritmico per premiare volume senza esagerare)
        dist_km = m.distance_meters / 1000
        vol_factor = math.log(dist_km + 1) / Config.VOLUME_LOG_DIVISOR
        
        # 3. Efficiency Penalty (Malus se il cuore deriva troppo rispetto ai watt)
        eff_penalty = max(0, decoupling - Config.DECOUPLING_THRESHOLD) * Config.DECOUPLING_PENALTY_FACTOR
        
        # 4. Intensity/HR Factor (Riserva Cardiaca usata)
        if (m.hr_max - m.hr_rest) > 0:
            hr_res = (m.avg_hr - m.hr_rest) / (m.hr_max - m.hr_rest)
        else:
            hr_res = 0.7 # Fallback
        
        # Formula SCORE
        raw_score = (wcf * Config.WEIGHT_POWER) + (vol_factor * Config.WEIGHT_VOLUME) + (hr_res * Config.WEIGHT_INTENSITY) - eff_penalty
        final_score = max(0.01, round(raw_score, 2))
        
        wr_pct = round(wcf * 100, 1)

        # BREAKDOWN per "Score Spiegabile"
        # Scaling factor 100 per visualizzazione percentuale
        details = {
            "Potenza": round(wcf * Config.WEIGHT_POWER * 100, 1),
            "Volume": round(vol_factor * Config.WEIGHT_VOLUME * 100, 1),
            "Intensità": round(hr_res * Config.WEIGHT_INTENSITY * 100, 1),
            "Malus Efficienza": round(-eff_penalty * 100, 1)
        }

        # NOTA: Restituiamo 4 valori ora! (score, details, wcf, wr_pct)
        return final_score, details, wcf, wr_pct

    def get_rank(self, score):
        if score > Config.RANK_THRESHOLDS["ELITE"]: return "🏆 Elite", "#FFD700"
        if score > Config.RANK_THRESHOLDS["PRO"]: return "🥇 Pro", "#C0C0C0"
        if score > Config.RANK_THRESHOLDS["ADVANCED"]: return "🥈 Advanced", "#CD7F32"
        if score > Config.RANK_THRESHOLDS["INTERMEDIATE"]: return "🥉 Intermediate", "#4CAF50"
        return "👟 Amateur", "#9E9E9E"
