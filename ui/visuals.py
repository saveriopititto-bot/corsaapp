import streamlit as st
import pandas as pd
import altair as alt

def render_benchmark_chart(df):
    """
    Istogramma della distribuzione degli SCORE.
    """
    st.markdown("##### 📊 Distribuzione Punteggi")
    if df.empty:
        st.info("Dati insufficienti.")
        return

    base = alt.Chart(df).encode(
        x=alt.X('SCORE:Q', bin=alt.Bin(maxbins=10), title='Score'),
        y=alt.Y('count()', title='Freq')
    )
    chart = base.mark_bar(color='#FF8080', cornerRadiusTopLeft=5, cornerRadiusTopRight=5).properties(
        height=200
    ).configure_axis(
        grid=False,
        domain=False,
        labelColor='#B2BEC3',
        titleColor='#636E72'
    ).configure_view(strokeWidth=0)
    
    st.altair_chart(chart, use_container_width=True)

def render_zones_chart(zones):
    """
    Grafico a barre delle zone di potenza (Z1-Z5).
    """
    st.markdown("##### ⚡ Zone Potenza")
    if not zones:
        st.info("Dati di potenza non disponibili.")
        return

    df_zones = pd.DataFrame(list(zones.items()), columns=['Zona', 'Percentuale'])
    
    # Colori per le zone: Z1 (Grigio) -> Z5 (Rosso)
    colors = ['#CDFAD5', '#F6FDC3', '#FFCF96', '#FF8080', '#FF8080']
    
    chart = alt.Chart(df_zones).mark_bar(cornerRadiusEnd=5).encode(
        x=alt.X('Zona', sort=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y('Percentuale', title=None),
        color=alt.Color('Zona', scale=alt.Scale(range=colors), legend=None),
        tooltip=['Zona', 'Percentuale']
    ).properties(
        height=200
    ).configure_axis(
        grid=False,
        domain=False,
        labelColor='#B2BEC3',
        titleColor='#636E72'
    ).configure_view(strokeWidth=0)

    st.altair_chart(chart, use_container_width=True)

def render_scatter_chart(watts, hr):
    """
    Scatter plot Potenza vs Cuore.
    """
    st.markdown("##### ❤️ Accoppiamento Potenza/Cuore")
    if not watts or not hr:
        st.info("Stream dati mancanti.")
        return

    # Creiamo un df ridotto (campioniamo 1 ogni 5 secondi per velocità)
    df = pd.DataFrame({'Watts': watts[::5], 'HR': hr[::5]})
    
    chart = alt.Chart(df).mark_circle(size=60, opacity=0.3).encode(
        x=alt.X('Watts', title='Potenza (W)'),
        y=alt.Y('HR', title='Frequenza Cardiaca (bpm)', scale=alt.Scale(zero=False)),
        color=alt.value('#FF8080'),
        tooltip=['Watts', 'HR']
    ).interactive().properties(
        height=300
    ).configure_axis(
        grid=False,
        domain=False,
        labelColor='#B2BEC3',
        titleColor='#636E72'
    ).configure_view(strokeWidth=0)
    
    st.altair_chart(chart, use_container_width=True)

def render_history_table(df):
    """
    Tabella interattiva con le ultime attività.
    """
    if df.empty:
        st.text("Nessun dato.")
        return

    # Selezioniamo e ordiniamo le colonne per la visualizzazione
    cols_to_show = ['Data', 'Dist (km)', 'Power', 'HR', 'SCORE', 'Rank']
    # Controlliamo che esistano tutte (per evitare KeyError su vecchi dati)
    available_cols = [c for c in cols_to_show if c in df.columns]
    
    display_df = df[available_cols].copy()
    display_df['Data'] = pd.to_datetime(display_df['Data']).dt.strftime('%Y-%m-%d')
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "SCORE": st.column_config.NumberColumn(
                "Score",
                format="%.2f"
            ),
            "Power": st.column_config.NumberColumn(
                "Watt",
                format="%d w"
            ),
             "HR": st.column_config.NumberColumn(
                "FC",
                format="%d bpm"
            )
        }
    )

def render_trend_chart(df):
    """
    Mostra SCORE grezzo e Media Mobile.
    Grafico avanzato con area sfumata.
    """
    st.markdown("##### 📈 Trend Intelligente (Score vs Media 7gg)")

    if df.empty:
        st.info("Nessun dato SCORE disponibile.")
        return

    # Preparazione dati pulita
    cols = ['Data', 'SCORE']
    if 'SCORE_MA_7' in df.columns:
        cols.append('SCORE_MA_7')
        
    chart_data = df[cols].copy()
    chart_data['Data'] = pd.to_datetime(chart_data['Data'])
    
    # Pulizia
    chart_data = (
        chart_data
        .dropna(subset=["SCORE"])
        .sort_values("Data")
    )
    
    # Se abbiamo la media mobile, usiamo quella per il grafico principale
    y_col = 'SCORE_MA_7' if 'SCORE_MA_7' in df.columns else 'SCORE'

    # Grafico Linee + Area
    base = alt.Chart(chart_data).encode(x='Data:T')

    area = base.mark_area(
        line={'color':'#FF8080', 'strokeWidth': 3},
        color=alt.Gradient(
            gradient='linear',
            stops=[alt.GradientStop(color='#FF8080', offset=0),
                   alt.GradientStop(color='white', offset=1)],
            x1=1, x2=1, y1=1, y2=0
        ),
        opacity=0.3
    ).encode(y=alt.Y(y_col, scale=alt.Scale(zero=False), title=None))

    points = base.mark_circle(color='#FF8080').encode(
        y=y_col,
        tooltip=['Data', y_col]
    )

    chart = (area + points).properties(
        height=250
    ).configure_axis(
        grid=False,           # Via la griglia
        domain=False,         # Via le linee degli assi
        labelColor='#B2BEC3', # Etichette grigio chiaro
        titleColor='#636E72'  # Titoli grigio medio
    ).configure_view(
        strokeWidth=0         # Via il bordo quadrato attorno al grafico
    )
    
    st.altair_chart(chart, use_container_width=True)
