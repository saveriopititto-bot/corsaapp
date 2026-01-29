import streamlit as st

def apply_custom_style():
    st.markdown("""
        <style>
        /* 1. IMPORT FONT (Montserrat per titoli, Inter per testo) */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Montserrat:wght@700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        h1, h2, h3 {
            font-family: 'Montserrat', sans-serif;
            font-weight: 800;
            color: #2D3436;
            letter-spacing: -0.5px;
        }

        /* 2. PULIZIA STREAMLIT */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;} /* Nasconde la barra colorata in alto */
        
        /* Spaziatura superiore ridotta */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 5rem;
        }

        /* 3. STILE KPI CARDS (st.metric) */
        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            border: 1px solid #F0F0F3;
            border-radius: 16px;
            padding: 15px 10px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            transition: all 0.3s ease;
        }

        div[data-testid="stMetric"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -2px rgba(0, 0, 0, 0.04);
            border-color: #6C5DD3;
        }

        div[data-testid="stMetricLabel"] {
            font-size: 0.8rem !important;
            color: #636E72 !important;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.6rem !important;
            color: #2D3436 !important;
            font-weight: 700;
        }

        /* 4. BOTTONI */
        div.stButton > button {
            border-radius: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            padding-top: 0.5rem;
            padding-bottom: 0.5rem;
            border: none;
            transition: all 0.2s;
        }
        
        /* 5. TABS */
        .stTabs [data-baseweb="tab-list"] {
            gap: 20px;
            background-color: transparent;
        }

        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            border-radius: 10px;
            color: #636E72;
            font-weight: 600;
        }

        .stTabs [aria-selected="true"] {
            background-color: #E3F2FD; /* Colore sfondo tab attiva */
            color: #6C5DD3 !important; /* Colore testo tab attiva */
            border-bottom: none;
        }
        
        /* 6. EXPANDER */
        .streamlit-expanderHeader {
            background-color: #FFFFFF;
            border-radius: 10px;
            font-weight: 600;
            color: #2D3436;
        }

        /* 7. SCORE CIRCLE ANIMATION */
        @property --angle {
            syntax: '<angle>';
            initial-value: 0deg;
            inherits: false;
        }

        .score-container {
            display: flex;
            justify-content: center;
            padding: 20px;
        }

        .score-circle {
            position: relative;
            width: 170px;
            height: 170px;
            border-radius: 50%;
            background: white;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            /* Base border */
            border: 6px solid #F0F0F3;
            cursor: pointer;
        }

        /* The animated ring */
        .score-circle::after {
            content: '';
            position: absolute;
            top: -6px; left: -6px; right: -6px; bottom: -6px;
            border-radius: 50%;
            background: conic-gradient(#6C5DD3 var(--angle), transparent 0deg);
            z-index: -1; /* Behind the white circle? No, we need a mask */
            /* Let's try a border image approach or mask */
            display: none;
        }
        
        /* Better approach for ring overlay */
        .score-circle:hover {
            border-color: transparent;
            background: 
                linear-gradient(white, white) padding-box,
                conic-gradient(#00E676 var(--angle), #F0F0F3 0deg) border-box; /* Green loading */
            animation: rotateScore 1s ease-out forwards;
        }

        @keyframes rotateScore {
            to {
                --angle: 360deg;
            }
        }
        </style>
    """, unsafe_allow_html=True)
