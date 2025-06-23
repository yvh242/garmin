# mijn_sportdashboard/Home.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# --- Pagina Configuratie ---
st.set_page_config(
    page_title="Sportactiviteiten Dashboard",
    page_icon="🏃‍♂️",
    layout="wide", # Gebruik "wide" voor een breder dashboard
    initial_sidebar_state="expanded"
)

# --- Helper Functies ---
@st.cache_data
def load_and_process_data(uploaded_file):
    """Laadt en verwerkt het geüploade Excel/CSV bestand."""
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    elif uploaded_file.name.endswith(('.xls', '.xlsx')):
        df = pd.read_excel(uploaded_file)
    else:
        st.error("Ongeldig bestandsformaat. Upload alstublieft een .csv of .xlsx bestand.")
        return None

    # Kolomnamen opschonen: spaties verwijderen, speciale tekens vervangen
    # Let op: 'Beste\xa0' (non-breaking space) wordt hier ook opgevangen
    df.columns = df.columns.str.strip().str.replace('Â®', '', regex=False).str.replace('\xa0', '', regex=False)

    # Controleer of alle vereiste kolommen aanwezig zijn
    required_cols = [
        "Activiteittype", "Datum", "Afstand", "Tijd",
        "Gem. HS", "Max. HS", "Gem. cadans", "Maximale cadans",
        "Gemiddeld tempo", "Beste tempo", "Totale stijging", "Totale daling",
        "Gem. staplengte", "Stappen",
        "Min. temp.", "Decompressie", "Beste", "Favoriet", "Titel"
    ]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        st.error(f"Het bestand mist de volgende vereiste kolommen: {', '.join(missing_cols)}. Zorg ervoor dat de kolomnamen correct zijn benoemd, inclusief hoofdletters/kleine letters en eventuele speciale tekens.")
        return None

    # Datum conversie
    df['Datum'] = pd.to_datetime(df['Datum'], errors='coerce')
    df.dropna(subset=['Datum'], inplace=True) # Verwijder rijen met ongeldige datums

    # Numerieke conversies
    df['Afstand'] = df['Afstand'].astype(str).str.replace(',', '.', regex=False).astype(float)
    df['Calorieën'] = pd.to_numeric(df['Calorieën'], errors='coerce').fillna(0)
    df['Stappen'] = pd.to_numeric(df['Stappen'], errors='coerce').fillna(0)
    df['Gem. HS'] = pd.to_numeric(df['Gem. HS'], errors='coerce').fillna(0) # Voorbereiden voor hartslag analyse

    # Tijd conversie: van HH:MM:SS string naar seconden (voor berekeningen)
    def parse_time_to_seconds(time_str):
        if pd.isna(time_str):
            return 0
        try:
            parts = str(time_str).split(':')
            if len(parts) == 3: # HH:MM:SS
                h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
                return h * 3600 + m * 60 + s
            elif len(parts) == 2: # MM:SS (kan voorkomen bij 'Tempo')
                m, s = int(parts[0]), int(parts[1])
                return m * 60 + s
            else: # Probeer direct te converteren als getal (bijv. seconden als float)
                return float(time_str)
        except ValueError:
            return 0 # Ongeldige formaten
        except TypeError:
            return 0 # NaN of andere types

    df['Tijd_seconden'] = df['Tijd'].apply(parse_time_to_seconds)
    df['Gemiddeld tempo_sec_per_km'] = df['Gemiddeld tempo'].apply(parse_pace_to_seconds_per_unit)
    df['Beste tempo_sec_per_km'] = df['Beste tempo'].apply(parse_pace_to_seconds_per_unit)

    return df

def parse_pace_to_seconds_per_unit(pace_str):
    """Converteert een MM:SS tempo string naar seconden per eenheid."""
    if pd.isna(pace_str):
        return 0
    try:
        parts = str(pace_str).split(':')
        if len(parts) == 2:
            m, s = int(parts[0]), int(parts[1])
            return m * 60 + s
        else: # Als het al een getal is (bijv. '300.0')
            return float(pace_str)
    except ValueError:
        return 0
    except TypeError:
        return 0

def format_duration(seconds):
    """Formateert een aantal seconden naar HH:MM:SS string."""
    if pd.isna(seconds) or seconds == 0:
        return "00:00:00"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

# --- Zijbalk voor bestand uploaden en filters ---
with st.sidebar:
    st.image("https://www.streamlit.io/images/brand/streamlit-logo-secondary-colormark-light.svg", width=150)
    st.header("Upload je gegevens")
    st.markdown("Upload hier je sportactiviteitenbestand (Excel of CSV).")

    uploaded_file = st.file_uploader("Kies een bestand", type=["csv", "xlsx"])

    df = None # Initialiseer df buiten de if-statement
    filtered_df = pd.DataFrame() # Initialiseer filtered_df als leeg dataframe

    if uploaded_file is not None:
        df = load_and_process_data(uploaded_file)
        if df is not None:
            st.success("Bestand succesvol geladen!")
            st.write(f"Totaal {len(df)} records gevonden.")

            # Datum filter
            st.header("Filter op datum")
            # Zorg ervoor dat de datums binnen het bereik van de data liggen
            min_date_data = df['Datum'].min().date()
            max_date_data = df['Datum'].max().date()

            col_start_date, col_end_date = st.columns(2)
            with col_start_date:
                start_date = st.date_input("Vanaf", min_date_data, min_value=min_date_data, max_value=max_date_data)
            with col_end_date:
                end_date = st.date_input("Tot", max_date_data, min_value=min_date_data, max_value=max_date_data)

            if start_date > end_date:
                st.error("Fout: De 'Tot' datum moet na of gelijk zijn aan de 'Vanaf' datum.")
                # Leeg dataframe zodat geen verdere berekeningen met foutieve data gebeuren
                filtered_df = pd.DataFrame()
            else:
                filtered_df = df[(df['Datum'].dt.date >= start_date) & (df['Datum'].dt.date <= end_date)]

            # Activiteittype filter
            st.header("Filter op Activiteittype")
            all_activity_types = ['Alle'] + sorted(filtered_df['Activiteittype'].unique().tolist())
            selected_activity_types = st.multiselect(
                "Selecteer activiteittypen",
                options=all_activity_types,
                default=['Alle']
            )

            if 'Alle' not in selected_activity_types:
                filtered_df = filtered_df[filtered_df['Activiteittype'].isin(selected_activity_types)]

            if filtered_df.empty and df is not None:
                st.warning("Geen gegevens beschikbaar voor de geselecteerde filters. Pas de filters aan.")
    else:
        st.info("Upload een bestand om het dashboard te zien. Zorg ervoor dat de kolomnamen correct zijn.")

# --- Hoofd Dashboard Content ---
st.title("🏃‍♂️ Je Persoonlijke Sportactiviteiten Dashboard")
st.markdown("Visualiseer en analyseer je prestaties met dit interactieve dashboard. Upload je gegevens en ontdek je vooruitgang!")

if uploaded_file is not None and not filtered_df.empty:
    st.markdown("---")

    # --- Sectie: Algemene Overzicht KPI's ---
    st.header("Algemeen Overzicht")
    total_distance = filtered_df['Afstand'].sum()
    avg_distance = filtered_df['Afstand'].mean()
    total_duration_seconds = filtered_df['Tijd_seconden'].sum()
    avg_duration_seconds = filtered_df['Tijd_seconden'].mean()
    total_calories = filtered_df['Calorieën'].sum()
    num_activities = len(filtered_df)

    # Gebruik kolommen voor een nette presentatie van KPI's
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    with kpi1:
        st.metric(label="Aantal activiteiten", value=num_activities)
    with kpi2:
        st.metric(label="Totale afstand", value=f"{total_distance:,.2f} km")
    with kpi3:
        st.metric(label="Gem. afstand per activiteit", value=f"{avg_distance:,.2f} km")
    with kpi4:
        st.metric(label="Totale duur", value=format_duration(total_duration_seconds))
    with kpi5:
        st.metric(label="Totaal calorieën", value=f"{total_calories:,.0f} kcal")

    st.markdown("---")

    # --- Tabs voor Gedetailleerde Inzichten ---
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Afstand & Duur", "💓 Tempo & Hartslag", "🏃‍♀️ Activiteitentypen", "📋 Ruwe Data"])

    with tab1:
        st.header("Afstand en Duur Overzicht")
        st.markdown("Bekijk hoe je afstand en duur zich ontwikkelen over de tijd.")

        col_dist_time, col_dur_time = st.columns(2)

        with col_dist_time:
            st.subheader("Afstand over tijd")
            df_daily_distance = filtered_df.groupby('Datum')['Afstand'].sum().reset_index()
            fig_distance_time = px.line(
                df_daily_distance,
                x='Datum',
                y='Afstand',
                title='Totale Afstand per Dag',
                labels={'Afstand': 'Afstand (km)', 'Datum': 'Datum'},
                template="plotly_dark"
            )
            fig_distance_time.update_traces(mode='lines+markers', marker_size=5)
            st.plotly_chart(fig_distance_time, use_container_width=True)

        with col_dur_time:
            st.subheader("Duur over tijd")
            df_daily_duration = filtered_df.groupby('Datum')['Tijd_seconden'].sum().reset_index()
            # Optioneel: voeg een geformatteerde duurkolom toe voor tooltip
            df_daily_duration['Tijd (HH:MM:SS)'] = df_daily_duration['Tijd_seconden'].apply(format_duration)
            fig_duration_time = px.line(
                df_daily_duration,
                x='Datum',
                y='Tijd_seconden',
                title='Totale Duur per Dag',
                labels={'Tijd_seconden': 'Duur (seconden)', 'Datum': 'Datum'},
                template="plotly_dark",
                hover_data={'Tijd_seconden':False, 'Tijd (HH:MM:SS)':True} # Toon geformatteerde duur
            )
            fig_duration_time.update_traces(mode='lines+markers', marker_size=5)
            st.plotly_chart(fig_duration_time, use_container_width=True)

    with tab2:
        st.header("Tempo en Hartslag Analyse")
        st.markdown("Inzichten in je prestatie-indicatoren zoals tempo en hartslag.")

        col_pace, col_hr = st.columns(2)

        with col_pace:
            st.subheader("Gemiddeld Tempo per Activiteit")
            # Converteer terug naar MM:SS string voor weergave
            filtered_df['Gemiddeld tempo Display'] = filtered_df['Gemiddeld tempo_sec_per_km'].apply(lambda x: f"{int(x // 60):02d}:{int(x % 60):02d}")
            fig_pace_dist = px.box(
                filtered_df,
                x='Activiteittype',
                y='Gemiddeld tempo_sec_per_km',
                title='Distributie van Gemiddeld Tempo per Activiteittype',
                labels={'Gemiddeld tempo_sec_per_km': 'Gemiddeld Tempo (sec/km)'},
                template="plotly_dark",
                color='Activiteittype'
            )
            st.plotly_chart(fig_pace_dist, use_container_width=True)


        with col_hr:
            st.subheader("Gemiddelde Hartslag per Activiteit")
            fig_hr_dist = px.box(
                filtered_df,
                x='Activiteittype',
                y='Gem. HS',
                title='Distributie van Gemiddelde Hartslag per Activiteittype',
                labels={'Gem. HS': 'Gemiddelde Hartslag (bpm)'},
                template="plotly_dark",
                color='Activiteittype'
            )
            st.plotly_chart(fig_hr_dist, use_container_width=True)

        st.subheader("Afstand vs. Hartslag per Activiteit")
        fig_scatter_hr = px.scatter(
            filtered_df,
            x='Afstand',
            y='Gem. HS',
            color='Activiteittype',
            size='Tijd_seconden', # Grootte van de stip gebaseerd op duur
            hover_name='Titel',
            title='Afstand vs. Gemiddelde Hartslag',
            labels={'Afstand': 'Afstand (km)', 'Gem. HS': 'Gemiddelde Hartslag (bpm)'},
            template="plotly_dark"
        )
        st.plotly_chart(fig_scatter_hr, use_container_width=True)


    with tab3:
        st.header("Analyse per Activiteittype")
        st.markdown("Duik dieper in je prestaties per type activiteit.")

        # Totaal afstand & Gemiddelde afstand per activiteittype
        col_total_dist_type, col_avg_dist_type = st.columns(2)

        with col_total_dist_type:
            st.subheader("Totale Afstand per Activiteittype")
            df_total_distance_by_type = filtered_df.groupby('Activiteittype')['Afstand'].sum().reset_index()
            df_total_distance_by_type = df_total_distance_by_type.sort_values(by='Afstand', ascending=False)
            fig_total_distance_type = px.bar(
                df_total_distance_by_type,
                x='Activiteittype',
                y='Afstand',
                title='Totaal Afstand per Activiteittype',
                labels={'Afstand': 'Totale Afstand (km)', 'Activiteittype': 'Activiteittype'},
                template="plotly_dark",
                color='Activiteittype'
            )
            st.plotly_chart(fig_total_distance_type, use_container_width=True)

        with col_avg_dist_type:
            st.subheader("Gemiddelde Afstand per Activiteittype")
            df_avg_distance_by_type = filtered_df.groupby('Activiteittype')['Afstand'].mean().reset_index()
            df_avg_distance_by_type = df_avg_distance_by_type.sort_values(by='Afstand', ascending=False)
            fig_avg_distance_type = px.bar(
                df_avg_distance_by_type,
                x='Activiteittype',
                y='Afstand',
                title='Gemiddelde Afstand per Activiteittype',
                labels={'Afstand': 'Gemiddelde Afstand (km)', 'Activiteittype': 'Activiteittype'},
                template="plotly_dark",
                color='Activiteittype'
            )
            st.plotly_chart(fig_avg_distance_type, use_container_width=True)

        # Calorieën en Stappen per activiteittype
        col_calories_type, col_steps_type = st.columns(2)

        with col_calories_type:
            st.subheader("Totaal Calorieën per Activiteittype")
            df_total_calories_by_type = filtered_df.groupby('Activiteittype')['Calorieën'].sum().reset_index()
            df_total_calories_by_type = df_total_calories_by_type.sort_values(by='Calorieën', ascending=False)
            fig_calories_type = px.pie(
                df_total_calories_by_type,
                values='Calorieën',
                names='Activiteittype',
                title='Verdeling Calorieën per Activiteittype',
                template="plotly_dark",
                hole=0.4 # Maak er een donut chart van
            )
            st.plotly_chart(fig_calories_type, use_container_width=True)

        with col_steps_type:
            st.subheader("Totaal Aantal Stappen per Activiteittype")
            df_total_steps_by_type = filtered_df.groupby('Activiteittype')['Stappen'].sum().reset_index()
            df_total_steps_by_type = df_total_steps_by_type.sort_values(by='Stappen', ascending=False)
            fig_steps_type = px.bar(
                df_total_steps_by_type,
                x='Activiteittype',
                y='Stappen',
                title='Totaal Stappen per Activiteittype',
                labels={'Stappen': 'Totaal Aantal Stappen', 'Activiteittype': 'Activiteittype'},
                template="plotly_dark",
                color='Activiteittype'
            )
            st.plotly_chart(fig_steps_type, use_container_width=True)


    with tab4:
        st.header("Ruwe Gegevens")
        st.markdown("Hier kun je de gefilterde ruwe data bekijken en eventueel exporteren.")
        st.dataframe(filtered_df) # Toon de volledige gefilterde DataFrame

        csv_export = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download gefilterde data als CSV",
            data=csv_export,
            file_name="gefilterde_sportdata.csv",
            mime="text/csv",
        )

else:
    st.info("Upload een Excel- of CSV-bestand met je sportactiviteiten om het dashboard te genereren. Zorg ervoor dat de kolomnamen overeenkomen met de verwachte indeling.")
