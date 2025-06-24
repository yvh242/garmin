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
    # Dit wordt gedaan op *alle* kolommen om consistentie te garanderen
    df.columns = df.columns.str.strip().str.replace('Â®', '', regex=False).str.replace('\xa0', '', regex=False)

    # Definieer een mapping van verwachte Nederlandse kolomnamen naar interne, schone namen
    # Dit maakt de code robuuster voor kleine variaties in kolomnamen en makkelijker te lezen.
    column_mapping = {
        "Activiteittype": "activity_type",
        "Datum": "date",
        "Favoriet": "favorite",
        "Titel": "title",
        "Afstand": "distance_km",
        "Calorieën": "calories_kcal",
        "Tijd": "duration_raw", # Dit is de string HH:MM:SS
        "Gem. HS": "avg_heart_rate_bpm",
        "Max. HS": "max_heart_rate_bpm",
        "Gem. cadans": "avg_cadence",
        "Maximale cadans": "max_cadence",
        "Gemiddeld tempo": "avg_pace_raw", # Dit is de string MM:SS
        "Beste tempo": "best_pace_raw", # Dit is de string MM:SS
        "Totale stijging": "total_elevation_gain_m",
        "Totale daling": "total_elevation_loss_m",
        "Gem. staplengte": "avg_stride_length_cm",
        "Training Stress Score": "tss", # Na opschonen van ®
        "Stappen": "steps",
        "Min. temp.": "min_temp_celsius",
        "Decompressie": "decompression",
        "Beste": "best_overall", # Na opschonen van spatie
    }

    # Hernoem kolommen op basis van de mapping
    df.rename(columns=column_mapping, inplace=True)

    # Zorg ervoor dat kritieke kolommen bestaan, vul aan met NaN/0 indien afwezig
    # En converteer data types
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df.dropna(subset=['date'], inplace=True)
    else:
        st.warning("De 'Datum' kolom is niet gevonden. Sommige functionaliteiten werken mogelijk niet correct.")
        df['date'] = pd.NaT # Voeg kolom toe met Not a Time
        df['date_week_start'] = pd.NaT # Noodzakelijk voor week/maand aggregatie

    if 'distance_km' in df.columns:
        df['distance_km'] = df['distance_km'].astype(str).str.replace(',', '.', regex=False).astype(float)
        df['distance_km'].fillna(0, inplace=True)
    else:
        st.warning("De 'Afstand' kolom is niet gevonden. Afstandsberekeningen zijn niet mogelijk.")
        df['distance_km'] = 0.0

    if 'calories_kcal' in df.columns:
        df['calories_kcal'] = pd.to_numeric(df['calories_kcal'], errors='coerce').fillna(0)
    else:
        st.warning("De 'Calorieën' kolom is niet gevonden. Calorieberekeningen zijn niet mogelijk.")
        df['calories_kcal'] = 0.0

    if 'steps' in df.columns:
        df['steps'] = pd.to_numeric(df['steps'], errors='coerce').fillna(0)
    else:
        st.warning("De 'Stappen' kolom is niet gevonden. Stappenberekeningen zijn niet mogelijk.")
        df['steps'] = 0.0

    if 'avg_heart_rate_bpm' in df.columns:
        df['avg_heart_rate_bpm'] = pd.to_numeric(df['avg_heart_rate_bpm'], errors='coerce').fillna(0)
    else:
        st.warning("De 'Gem. HS' kolom is niet gevonden. Hartslag analyses zijn niet mogelijk.")
        df['avg_heart_rate_bpm'] = 0.0

    if 'activity_type' not in df.columns:
        st.warning("De 'Activiteittype' kolom is niet gevonden. Analyses per activiteitstype zijn beperkt.")
        df['activity_type'] = 'Onbekend' # Voeg standaard type toe

    # Tijd conversie: van HH:MM:SS string naar seconden
    def parse_time_to_seconds(time_str):
        if pd.isna(time_str): return 0
        try:
            parts = str(time_str).split(':')
            if len(parts) == 3: return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2: return int(parts[0]) * 60 + int(parts[1]) # Kan voorkomen bij tempo format
            else: return float(time_str)
        except (ValueError, TypeError): return 0

    if 'duration_raw' in df.columns:
        df['duration_seconds'] = df['duration_raw'].apply(parse_time_to_seconds)
    else:
        st.warning("De 'Tijd' kolom is niet gevonden. Duur analyses zijn niet mogelijk.")
        df['duration_seconds'] = 0.0

    # Tempo conversie: van MM:SS string naar seconden per eenheid
    def parse_pace_to_seconds_per_unit(pace_str):
        if pd.isna(pace_str): return 0
        try:
            parts = str(pace_str).split(':')
            if len(parts) == 2: return int(parts[0]) * 60 + int(parts[1])
            else: return float(pace_str)
        except (ValueError, TypeError): return 0

    if 'avg_pace_raw' in df.columns:
        df['avg_pace_sec_per_km'] = df['avg_pace_raw'].apply(parse_pace_to_seconds_per_unit)
    else:
        df['avg_pace_sec_per_km'] = 0.0 # Voeg kolom toe met default waarde

    if 'best_pace_raw' in df.columns:
        df['best_pace_sec_per_km'] = df['best_pace_raw'].apply(parse_pace_to_seconds_per_unit)
    else:
        df['best_pace_sec_per_km'] = 0.0 # Voeg kolom toe met default waarde


    # Voeg week- en maandkolommen toe voor aggregatie
    if 'date' in df.columns and not df['date'].empty:
        df['year_week'] = df['date'].dt.strftime('%Y-%W')
        df['year_month'] = df['date'].dt.strftime('%Y-%m')
        # Bepaal het begin van de week voor elke datum, handig voor x-as in grafieken
        df['date_week_start'] = df['date'].apply(lambda x: x - timedelta(days=x.weekday()))
    else:
        df['year_week'] = 'Onbekend'
        df['year_month'] = 'Onbekend'
        df['date_week_start'] = pd.NaT # Default indien datum ontbreekt

    return df

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

    df_full = None # DataFrame voor de volledige dataset
    filtered_df = pd.DataFrame() # Initialiseer filtered_df als leeg dataframe

    if uploaded_file is not None:
        df_full = load_and_process_data(uploaded_file)
        if df_full is not None and not df_full.empty:
            st.success("Bestand succesvol geladen!")
            st.write(f"Totaal {len(df_full)} records gevonden.")

            # Datum filter
            st.header("Filter op datum")
            # Zorg ervoor dat de datums binnen het bereik van de data liggen
            if 'date' in df_full.columns and not df_full['date'].empty and pd.notna(df_full['date'].min()):
                min_date_data = df_full['date'].min().date()
                max_date_data = df_full['date'].max().date()
            else:
                min_date_data = datetime.now().date() - timedelta(days=30)
                max_date_data = datetime.now().date()

            col_start_date, col_end_date = st.columns(2)
            with col_start_date:
                start_date = st.date_input("Vanaf", min_date_data, min_value=datetime(1900,1,1).date(), max_value=datetime(2100,1,1).date())
            with col_end_date:
                end_date = st.date_input("Tot", max_date_data, min_value=datetime(1900,1,1).date(), max_value=datetime(2100,1,1).date())

            if start_date > end_date:
                st.error("Fout: De 'Tot' datum moet na of gelijk zijn aan de 'Vanaf' datum.")
                filtered_df = pd.DataFrame() # Leeg dataframe om fouten te voorkomen
            else:
                filtered_df = df_full[(df_full['date'].dt.date >= start_date) & (df_full['date'].dt.date <= end_date)].copy() # .copy() om SettingWithCopyWarning te voorkomen

            # Sla de geselecteerde datums op in session_state voor gebruik in tabs
            st.session_state.start_date_filter = start_date
            st.session_state.end_date_filter = end_date

            # Activiteittype filter
            st.header("Filter op Activiteittype")
            if 'activity_type' in filtered_df.columns and not filtered_df.empty:
                all_activity_types = ['Alle'] + sorted(filtered_df['activity_type'].unique().tolist())
                selected_activity_types = st.multiselect(
                    "Selecteer activiteittypen",
                    options=all_activity_types,
                    default=['Alle']
                )

                if 'Alle' not in selected_activity_types:
                    filtered_df = filtered_df[filtered_df['activity_type'].isin(selected_activity_types)]
            else:
                st.warning("Geen 'Activiteittype' kolom gevonden of geen data om te filteren.")

            if filtered_df.empty and df_full is not None:
                st.warning("Geen gegevens beschikbaar voor de geselecteerde filters. Pas de filters aan.")
    else:
        st.info("Upload een Excel- of CSV-bestand met je sportactiviteiten om het dashboard te genereren. Zorg ervoor dat de kolomnamen correct zijn.")

# --- Hoofd Dashboard Content ---
st.title("🏃‍♂️ Je Persoonlijke Sportactiviteiten Dashboard")
st.markdown("Visualiseer en analyseer je prestaties met dit interactieve dashboard. Upload je gegevens en ontdek je vooruitgang!")

if uploaded_file is not None and not filtered_df.empty:
    st.markdown("---")

    # --- Sectie: Algemene Overzicht KPI's ---
    st.header("Algemeen Overzicht")
    total_distance = filtered_df['distance_km'].sum()
    avg_distance = filtered_df['distance_km'].mean()
    total_duration_seconds = filtered_df['duration_seconds'].sum()
    avg_duration_seconds = filtered_df['duration_seconds'].mean()
    total_calories = filtered_df['calories_kcal'].sum()
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
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Afstand & Duur", "💓 Tempo & Hartslag", "🏃‍♀️ Activiteitentypen", "📈 Vergelijking", "📋 Ruwe Data"])

    with tab1:
        st.header("Afstand en Duur Overzicht")
        st.markdown("Bekijk hoe je afstand en duur zich ontwikkelen over de tijd.")

        col_dist_time, col_dur_time = st.columns(2)

        with col_dist_time:
            st.subheader("Afstand over tijd")
            df_daily_distance = filtered_df.groupby('date')['distance_km'].sum().reset_index()
