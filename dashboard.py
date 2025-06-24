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
def format_duration(seconds):
    """Formateert een aantal seconden naar HH:MM:SS string."""
    if pd.isna(seconds) or seconds == 0:
        return "00:00:00"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

@st.cache_data
def load_data(uploaded_file):
    """Laadt het geüploade Excel/CSV bestand zonder directe verwerking."""
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    elif uploaded_file.name.endswith(('.xls', '.xlsx')):
        df = pd.read_excel(uploaded_file)
    else:
        st.error("Ongeldig bestandsformaat. Upload alstublieft een .csv of .xlsx bestand.")
        return None
    return df

@st.cache_data
def process_mapped_data(df, column_mapping_user):
    """Verwerkt het DataFrame met de door de gebruiker opgegeven kolommapping."""

    df_processed = df.copy()

    # Kolomnamen opschonen: spaties verwijderen, speciale tekens vervangen in ALLE kolommen
    df_processed.columns = df_processed.columns.str.strip().str.replace('Â®', '', regex=False).str.replace('\xa0', '', regex=False)

    # Maak een omgekeerde mapping van schone interne naam naar de naam in de user's file
    # Gebruik de user's mapping om de kolommen te hernoemen naar de verwachte interne namen
    rename_dict = {}
    for internal_name, user_col_name in column_mapping_user.items():
        # Belangrijk: Controleer of de user_col_name daadwerkelijk bestaat in de _originele_ (raw_df) kolommen
        if user_col_name and user_col_name in df_processed.columns:
            rename_dict[user_col_name] = internal_name
        else:
            # Als een kolom niet gemapt is of niet bestaat, voeg een placeholder toe
            df_processed[internal_name] = pd.NA # Gebruik pd.NA voor ontbrekende data

    # Voer de hernoeming uit
    df_processed.rename(columns=rename_dict, inplace=True)

    # Controleer en converteer essentiële kolommen met fallback
    if 'date' in df_processed.columns:
        df_processed['date'] = pd.to_datetime(df_processed['date'], errors='coerce')
        df_processed.dropna(subset=['date'], inplace=True)
    else:
        df_processed['date'] = pd.NaT # Voeg kolom toe met Not a Time

    if 'distance_km' in df_processed.columns:
        df_processed['distance_km'] = df_processed['distance_km'].astype(str).str.replace(',', '.', regex=False).astype(float).fillna(0)
    else:
        df_processed['distance_km'] = 0.0

    if 'calories_kcal' in df_processed.columns:
        df_processed['calories_kcal'] = pd.to_numeric(df_processed['calories_kcal'], errors='coerce').fillna(0)
    else:
        df_processed['calories_kcal'] = 0.0

    if 'steps' in df_processed.columns:
        df_processed['steps'] = pd.to_numeric(df_processed['steps'], errors='coerce').fillna(0)
    else:
        df_processed['steps'] = 0.0

    if 'avg_heart_rate_bpm' in df_processed.columns:
        df_processed['avg_heart_rate_bpm'] = pd.to_numeric(df_processed['avg_heart_rate_bpm'], errors='coerce').fillna(0)
    else:
        df_processed['avg_heart_rate_bpm'] = 0.0

    if 'activity_type' not in df_processed.columns:
        df_processed['activity_type'] = 'Onbekend' # Stel in op 'Onbekend' als de kolom ontbreekt

    # Tijd conversie: van HH:MM:SS string naar seconden
    def parse_time_to_seconds(time_str):
        if pd.isna(time_str): return 0
        try:
            parts = str(time_str).split(':')
            if len(parts) == 3: return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2: return int(parts[0]) * 60 + int(parts[1])
            else: return float(time_str) # Voor het geval het al seconden zijn
        except (ValueError, TypeError): return 0

    if 'duration_raw' in df_processed.columns:
        df_processed['duration_seconds'] = df_processed['duration_raw'].apply(parse_time_to_seconds)
    else:
        df_processed['duration_seconds'] = 0.0

    # Tempo conversie: van MM:SS string naar seconden per eenheid (niet gebruikt in de huidige tabs, maar handig om te behouden)
    def parse_pace_to_seconds_per_unit(pace_str):
        if pd.isna(pace_str): return 0
        try:
            parts = str(pace_str).split(':')
            if len(parts) == 2: return int(parts[0]) * 60 + int(parts[1])
            else: return float(pace_str)
        except (ValueError, TypeError): return 0

    if 'avg_pace_raw' in df_processed.columns:
        df_processed['avg_pace_sec_per_km'] = df_processed['avg_pace_raw'].apply(parse_pace_to_seconds_per_unit)
    else:
        df_processed['avg_pace_sec_per_km'] = 0.0

    if 'best_pace_raw' in df_processed.columns:
        df_processed['best_pace_sec_per_km'] = df_processed['best_pace_raw'].apply(parse_pace_to_seconds_per_unit)
    else:
        df_processed['best_pace_sec_per_km'] = 0.0

    # Voeg week- en maandkolommen toe voor aggregatie
    if 'date' in df_processed.columns and not df_processed['date'].empty and df_processed['date'].notna().any():
        df_processed['year_week'] = df_processed['date'].dt.strftime('%Y-%W')
        df_processed['date_week_start'] = df_processed['date'].apply(lambda x: x - timedelta(days=x.weekday()))
        df_processed['date_week_end'] = df_processed['date_week_start'] + timedelta(days=6)
        df_processed['year_month'] = df_processed['date'].dt.strftime('%Y-%m')
    else:
        df_processed['year_week'] = 'Onbekend'
        df_processed['year_month'] = 'Onbekend'
        df_processed['date_week_start'] = pd.NaT
        df_processed['date_week_end'] = pd.NaT

    return df_processed

# --- Initialiseer session_state variabelen indien nodig ---
if 'raw_df' not in st.session_state:
    st.session_state.raw_df = pd.DataFrame()
if 'processed_df' not in st.session_state:
    st.session_state.processed_df = pd.DataFrame()
if 'column_mapping_user' not in st.session_state:
    st.session_state.column_mapping_user = {}

# --- Zijbalk voor bestand uploaden en filters ---
with st.sidebar:
    st.image("https://www.streamlit.io/images/brand/streamlit-logo-secondary-colormark-light.svg", width=150)
    st.header("Upload je gegevens")
    st.markdown("Upload hier je sportactiviteitenbestand (Excel of CSV).")

    uploaded_file = st.file_uploader("Kies een bestand", type=["csv", "xlsx"])

    if uploaded_file is not None:
        # Als een nieuw bestand is geüpload, laad het en reset de processed_df en mapping
        if uploaded_file != st.session_state.get('last_uploaded_file', None):
            st.session_state.raw_df = load_data(uploaded_file)
            st.session_state.processed_df = pd.DataFrame() # Reset processed_df bij nieuwe upload
            st.session_state.column_mapping_user = {} # Reset mapping bij nieuwe upload
            st.session_state.last_uploaded_file = uploaded_file # Bewaar de laatst geüploade file voor vergelijking

        if not st.session_state.raw_df.empty:
            st.success("Bestand succesvol geladen!")
            # Filters worden nu getoond als processed_df beschikbaar is
            if not st.session_state.processed_df.empty:
                st.subheader("Filters")
                # Datum filter
                valid_dates = st.session_state.processed_df['date'].dropna()
                if not valid_dates.empty:
                    min_date_data = valid_dates.min().date()
                    max_date_data = valid_dates.max().date()
                else:
                    min_date_data = datetime.now().date() - timedelta(days=30)
                    max_date_data = datetime.now().date()

                col_start_date, col_end_date = st.columns(2)
                with col_start_date:
                    start_date = st.date_input("Vanaf", min_date_data, min_value=datetime(1900,1,1).date(), max_value=datetime(2100,1,1).date(), key="sidebar_start_date")
                with col_end_date:
                    end_date = st.date_input("Tot", max_date_data, min_value=datetime(1900,1,1).date(), max_value=datetime(2100,1,1).date(), key="sidebar_end_date")

                if start_date > end_date:
                    st.error("Fout: De 'Tot' datum moet na of gelijk zijn aan de 'Vanaf' datum.")
                    filtered_df = pd.DataFrame()
                else:
                    filtered_df = st.session_state.processed_df[
                        (st.session_state.processed_df['date'].dt.date >= start_date) &
                        (st.session_state.processed_df['date'].dt.date <= end_date)
                    ].copy()

                # Activiteittype filter
                if 'activity_type' in filtered_df.columns and not filtered_df.empty:
                    all_activity_types = ['Alle'] + sorted(filtered_df['activity_type'].dropna().unique().tolist())
                    selected_activity_types = st.multiselect(
                        "Selecteer activiteittypen",
                        options=all_activity_types,
                        default=['Alle'],
                        key="sidebar_activity_type_select"
                    )
                    if 'Alle' not in selected_activity_types:
                        filtered_df = filtered_df[filtered_df['activity_type'].isin(selected_activity_types)]
                else:
                    st.warning("Geen 'Activiteittype' kolom gevonden of geen data om te filteren.")

                if filtered_df.empty:
                    st.warning("Geen gegevens beschikbaar voor de geselecteerde filters. Pas de filters aan.")
                else:
                    st.session_state.filtered_df = filtered_df # Sla gefilterde DF op in session_state
            else:
                st.info("Ga naar het tabblad '⚙️ Data Instellingen' om je kolommen te mappen en de data te verwerken.")
                st.session_state.filtered_df = pd.DataFrame() # Zorg dat filtered_df leeg is
        else: # raw_df is leeg na upload
            st.error("Het geüploade bestand is leeg of kan niet gelezen worden.")
            st.session_state.filtered_df = pd.DataFrame()
    else: # Geen bestand geüpload
        st.info("Upload een Excel- of CSV-bestand met je sportactiviteiten om het dashboard te genereren.")
        st.session_state.raw_df = pd.DataFrame()
        st.session_state.processed_df = pd.DataFrame()
        st.session_state.filtered_df = pd.DataFrame()

# --- Hoofd Dashboard Content ---
st.title("🏃‍♂️ Je Persoonlijke Sportactiviteiten Dashboard")
st.markdown("Visualiseer en analyseer je prestaties met dit interactieve dashboard. Upload je gegevens en ontdek je vooruitgang!")

# Bepaal welke tabs getoond moeten worden
if st.session_state.raw_df.empty:
    st.info("Upload een Excel- of CSV-bestand met je sportactiviteiten om het dashboard te genereren.")
    st.markdown("---")
    st.markdown("""
        **Tip:** Zorg ervoor dat je bestand de benodigde gegevens bevat. Als de kolomnamen niet automatisch worden herkend, kun je deze na het uploaden handmatig mappen in het tabblad 'Data Instellingen'.
    """)
else:
    # Definieer de tabbladen. Data Instellingen is nu de eerste
    tab_settings, tab1, tab_new_period_overview, tab5 = st.tabs([
        "⚙️ Data Instellingen",
        "📊 Afstand & Duur",
        "🗓️ Overzicht per Periode",
        "📋 Ruwe Data"
    ])

    with tab_settings:
        st.header("Kolommapping")
        st.info("Koppel de kolommen uit je bestand aan de verwachte kolommen voor analyse. "
                "Na het mappen wordt de data verwerkt en kun je de andere tabbladen gebruiken.")

        # Definieer de verwachte interne kolomnamen
        required_columns_map = {
            "date": "Datum",
            "activity_type": "Activiteittype",
            "distance_km": "Afstand",
            "calories_kcal": "Calorieën",
            "duration_raw": "Tijd", # Dit is de ruwe string die we later parsen naar seconds
            "avg_heart_rate_bpm": "Gem. HS",
            "steps": "Stappen"
        }
        optional_columns = {
            "title": "Titel",
            "avg_pace_raw": "Gemiddeld tempo",
            "max_heart_rate_bpm": "Max. HS",
            "total_elevation_gain_m": "Totale stijging"
        }
        all_expected_columns = {**required_columns_map, **optional_columns}

        raw_columns_cleaned = [col.strip().replace('Â®', '', regex=False).replace('\xa0', '', regex=False) for col in st.session_state.raw_df.columns]
        raw_columns_options = [''] + sorted(list(set(raw_columns_cleaned)))

        # Forceer herladen van selectboxen als er een nieuwe file is geupload
        # Dit is cruciaal voor correcte reset van de mapping bij nieuwe files
        file_hash = hash(uploaded_file.read()) if uploaded_file else 'no_file'
        if 'current_file_hash' not in st.session_state or st.session_state.current_file_hash != file_hash:
            st.session_state.column_mapping_user = {} # Reset mapping
            st.session_state.current_file_hash = file_hash
            # Rerun om de selectboxes te resetten
            # Dit kan soms een infinite loop veroorzaken als niet correct behandeld.
            # We vermijden dit door de reset logica in de sidebar ook te laten triggeren.
            st.rerun()


        all_mapped_successfully = True
        for internal_name, display_name in all_expected_columns.items():
            current_selection = st.session_state.column_mapping_user.get(internal_name, '')

            normalized_raw_cols = {col.lower().replace('.', '').replace(' ', '').replace('®','').replace('â','').replace('à',''): col for col in raw_columns_options if col}
            normalized_display_name = display_name.lower().replace('.', '').replace(' ', '').replace('gemiddelde', 'gem').replace('hartslag', 'hs').replace('®','').replace('â','').replace('à','')

            suggested_value = current_selection
            if not current_selection: # Alleen automatisch suggestie als nog niets is geselecteerd
                if normalized_display_name in normalized_raw_cols:
                    suggested_value = normalized_raw_cols[normalized_display_name]
                # Meer specifieke suggesties
                elif internal_name == "activity_type" and "activiteittype" in normalized_raw_cols: suggested_value = normalized_raw_cols["activiteittype"]
                elif internal_name == "date" and "datumactiviteit" in normalized_raw_cols: suggested_value = normalized_raw_cols["datumactiviteit"]
                elif internal_name == "distance_km" and "afstandkm" in normalized_raw_cols: suggested_value = normalized_raw_cols["afstandkm"]
                elif internal_name == "duration_raw" and "tijdduur" in normalized_raw_cols: suggested_value = normalized_raw_cols["tijdduur"]
                elif internal_name == "calories_kcal" and ("calorieën" in normalized_raw_cols or "kcalorieën" in normalized_raw_cols):
                    suggested_value = normalized_raw_cols.get("calorieën") or normalized_raw_cols.get("kcalorieën")
                elif internal_name == "avg_heart_rate_bpm" and ("gemhs" in normalized_raw_cols or "avg.hs" in normalized_raw_cols or "gem.hs" in normalized_raw_cols or "gemidhs" in normalized_raw_cols or "gemiddeldehs" in normalized_raw_cols):
                    suggested_value = normalized_raw_cols.get("gemhs") or normalized_raw_cols.get("avg.hs") or normalized_raw_cols.get("gem.hs") or normalized_raw_cols.get("gemidhs") or normalized_raw_cols.get("gemiddeldehs")
                elif internal_name == "steps" and ("stappen" in normalized_raw_cols or "aantalstappen" in normalized_raw_cols):
                    suggested_value = normalized_raw_cols.get("stappen") or normalized_raw_cols.get("aantalstappen")


            selected_column = st.selectbox(
                f"'{display_name}' (verwacht):",
                options=raw_columns_options,
                index=raw_columns_options.index(suggested_value) if suggested_value in raw_columns_options else 0,
                key=f"map_{internal_name}"
            )
            st.session_state.column_mapping_user[internal_name] = selected_column

            if internal_name in required_columns_map and not selected_column:
                all_mapped_successfully = False

        if not all_mapped_successfully:
            st.warning("Map alle **vereiste** kolommen (gemarkeerd als 'verwacht') om door te gaan naar de analyses.")
            st.session_state.processed_df = pd.DataFrame() # Reset processed_df als mapping incompleet is
        else:
            try:
                processed_df_temp = process_mapped_data(st.session_state.raw_df, st.session_state.column_mapping_user)
                if not processed_df_temp.empty:
                    st.success("Kolommen succesvol gemapt en data verwerkt! Je kunt nu de andere tabbladen gebruiken.")
                    st.session_state.processed_df = processed_df_temp # Opslaan in session state
                    # Zorg ervoor dat de filters in de zijbalk worden bijgewerkt
                    # Dit kan door de app te reruns, maar vermijd infinite loops
                    # We vertrouwen erop dat de Streamlit lifecycle dit oppakt
                else:
                    st.error("Verwerkte dataframe is leeg. Controleer uw kolommapping en bestandsinhoud.")
                    st.session_state.processed_df = pd.DataFrame() # Reset processed_df
            except Exception as e:
                st.error(f"Er is een fout opgetreden tijdens het verwerken van de data met uw mapping: {e}")
                st.warning("Controleer uw kolomselecties.")
                st.session_state.processed_df = pd.DataFrame() # Reset processed_df


    # Alle volgende tabs zijn alleen zichtbaar en bruikbaar als processed_df beschikbaar is
    # We gebruiken st.session_state.filtered_df hier, die in de zijbalk wordt ingesteld
    if not st.session_state.filtered_df.empty:
        st.markdown("---")

        # --- Sectie: Algemene Overzicht KPI's (alleen weergeven als data beschikbaar is) ---
        st.header("Algemeen Overzicht")
        total_distance = st.session_state.filtered_df['distance_km'].sum()
        avg_distance = st.session_state.filtered_df['distance_km'].mean()
        total_duration_seconds = st.session_state.filtered_df['duration_seconds'].sum()
        avg_duration_seconds = st.session_state.filtered_df['duration_seconds'].mean()
        total_calories = st.session_state.filtered_df['calories_kcal'].sum()
        num_activities = len(st.session_state.filtered_df)

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

        with tab1:
            st.header("Afstand en Duur Overzicht")
            st.markdown("Bekijk hoe je afstand en duur zich ontwikkelen over de tijd.")

            col_dist_time, col_dur_time = st.columns(2)

            if 'date' in st.session_state.filtered_df.columns and 'distance_km' in st.session_state.filtered_df.columns and st.session_state.filtered_df['date'].notna().any() and st.session_state.filtered_df['distance_km'].sum() > 0:
                with col_dist_time:
                    st.subheader("Afstand over tijd")
                    df_daily_distance = st.session_state.filtered_df.groupby('date')['distance_km'].sum().reset_index()
                    fig_distance_time = px.line(
                        df_daily_distance,
                        x='date',
                        y='distance_km',
                        title='Totale Afstand per Dag',
                        labels={'distance_km': 'Afstand (km)', 'date': 'Datum'},
                        template="plotly_dark"
                    )
                    fig_distance_time.update_traces(mode='lines+markers', marker_size=5)
                    st.plotly_chart(fig_distance_time, use_container_width=True)
            else:
                with col_dist_time:
                    st.info("Niet genoeg data om 'Afstand over tijd' te tonen. Controleer de kolommapping voor 'Datum' en 'Afstand'.")

            if 'date' in st.session_state.filtered_df.columns and 'duration_seconds' in st.session_state.filtered_df.columns and st.session_state.filtered_df['date'].notna().any() and st.session_state.filtered_df['duration_seconds'].sum() > 0:
                with col_dur_time:
                    st.subheader("Duur over tijd")
                    df_daily_duration = st.session_state.filtered_df.groupby('date')['duration_seconds'].sum().reset_index()
                    df_daily_duration['Tijd (HH:MM:SS)'] = df_daily_duration['duration_seconds'].apply(format_duration)
                    fig_duration_time = px.line(
                        df_daily_duration,
                        x='date',
                        y='duration_seconds',
                        title='Totale Duur per Dag',
                        labels={'duration_seconds': 'Duur (seconden)', 'date': 'Datum'},
                        template="plotly_dark",
                        hover_data={'duration_seconds':False, 'Tijd (HH:MM:SS)':True}
                    )
                    fig_duration_time.update_traces(mode='lines+markers', marker_size=5)
                    st.plotly_chart(fig_duration_time, use_container_width=True)
            else:
                with col_dur_time:
                    st.info("Niet genoeg data om 'Duur over tijd' te tonen. Controleer de kolommapping voor 'Datum' en 'Tijd'.")


        with tab_new_period_overview:
            st.header("Overzicht per Week of Maand")
            st.markdown("Kies zelf of je de totale en gemiddelde waarden per **week** of per **maand** wilt bekijken.")

            col_period_choice, col_display_choice = st.columns([1, 1])
            with col_period_choice:
                aggregation_period_new_tab = st.radio(
                    "Gegevens aggregeren per:",
                    ('Per Week', 'Per Maand'),
                    horizontal=True,
                    key='new_tab_agg_period'
                )
            with col_display_choice:
                display_type = st.radio(
                    "Weergave type:",
                    ('Grafiek', 'Tabel'),
                    horizontal=True,
                    key='new_tab_display_type'
                )

            st.markdown(f"**Toont {display_type.lower()} overzicht {aggregation_period_new_tab.lower()}**")

            if (not st.session_state.filtered_df.empty and
                'distance_km' in st.session_state.filtered_df.columns and st.session_state.filtered_df['distance_km'].notna().any() and
                'duration_seconds' in st.session_state.filtered_df.columns and st.session_state.filtered_df['duration_seconds'].notna().any() and
                'avg_heart_rate_bpm' in st.session_state.filtered_df.columns and st.session_state.filtered_df['avg_heart_rate_bpm'].notna().any() and
                'year_week' in st.session_state.filtered_df.columns and st.session_state.filtered_df['year_week'].notna().any() and
                'year_month' in st.session_state.filtered_df.columns and st.session_state.filtered_df['year_month'].notna().any()):

                if aggregation_period_new_tab == 'Per Week':
                    df_agg_new = st.session_state.filtered_df.groupby('year_week').agg(
                        total_distance=('distance_km', 'sum'),
                        avg_distance=('distance_km', 'mean'),
                        total_duration=('duration_seconds', 'sum'),
                        avg_duration=('duration_seconds', 'mean'),
                        avg_heart_rate=('avg_heart_rate_bpm', lambda x: x[x > 0].mean())
                    ).reset_index()

                    week_dates = st.session_state.filtered_df.groupby('year_week').agg(
                        min_date_week_start=('date_week_start', 'min'),
                        max_date_week_end=('date_week_end', 'max')
                    ).reset_index()

                    df_agg_new = pd.merge(df_agg_new, week_dates, on='year_week', how='left')

                    df_agg_new.columns = ['Periode', 'Totaal Afstand (km)', 'Gem. Afstand (km)', 'Totale Duur (sec)', 'Gem. Duur (sec)', 'Gem. Hartslag (bpm)', 'Datum Week Start', 'Datum Week Einde']
                    df_agg_new['Week Periode'] = df_agg_new['Datum Week Start'].dt.strftime('%d-%m') + ' t/m ' + df_agg_new['Datum Week Einde'].dt.strftime('%d-%m')

                    x_label = 'Jaar-Week (JJJJ-WW)'
                    show_xaxis_range_slider = True
                    x_tickangle = 0
                else: # Per Maand
                    df_agg_new = st.session_state.filtered_df.groupby('year_month').agg(
                        total_distance=('distance_km', 'sum'),
                        avg_distance=('distance_km', 'mean'),
                        total_duration=('duration_seconds', 'sum'),
                        avg_duration=('duration_seconds', 'mean'),
                        avg_heart_rate=('avg_heart_rate_bpm', lambda x: x[x > 0].mean())
                    ).reset_index()
                    df_agg_new.columns = ['Periode', 'Totaal Afstand (km)', 'Gem. Afstand (km)', 'Totale Duur (sec)', 'Gem. Duur (sec)', 'Gem. Hartslag (bpm)']
                    x_label = 'Jaar-Maand (JJJJ-MM)'
                    show_xaxis_range_slider = False
                    x_tickangle = -45


                df_agg_new['Totale Duur (HH:MM:SS)'] = df_agg_new['Totale Duur (sec)'].apply(format_duration)
                df_agg_new['Gem. Duur (HH:MM:SS)'] = df_agg_new['Gem. Duur (sec)'].apply(format_duration)
                df_agg_new['Gem. Hartslag (bpm)'] = df_agg_new['Gem. Hartslag (bpm)'].round(0).astype('Int64').fillna(0)

                if display_type == 'Grafiek':
                    col_total_dist_new, col_avg_dist_new = st.columns(2)

                    with col_total_dist_new:
                        st.subheader(f"Totale Afstand {aggregation_period_new_tab.lower()}")
                        fig_total_dist_new = px.bar(
                            df_agg_new,
                            x='Periode',
                            y='Totaal Afstand (km)',
                            title=f'Totale Afstand {aggregation_period_new_tab.lower()}',
                            labels={'Periode': x_label, 'Totaal Afstand (km)': 'Totaal Afstand (km)'},
                            template="plotly_dark",
                            text_auto='.2f'
                        )
                        fig_total_dist_new.update_traces(textposition='outside', marker_color='#FF4B4B')
                        fig_total_dist_new.update_layout(showlegend=False)
                        fig_total_dist_new.update_xaxes(
                            tickangle=x_tickangle,
                            rangeslider_visible=show_xaxis_range_slider,
                            rangeselector=dict(
                                buttons=list([
                                    dict(count=1, label="1m", step="month", stepmode="backward"),
                                    dict(count=6, label="6m", step="month", stepmode="backward"),
                                    dict(count=1, label="1j", step="year", stepmode="backward"),
                                    dict(step="all")
                                ])
                            ) if show_xaxis_range_slider else None
                        )
                        if aggregation_period_new_tab == 'Per Maand':
                            fig_total_dist_new.update_xaxes(
                                tickformat="%Y-%m",
                                dtick="M1",
                                ticklabelmode="period",
                                range=[df_agg_new['Periode'].min(), df_agg_new['Periode'].max()]
                            )
                        st.plotly_chart(fig_total_dist_new, use_container_width=True)

                    with col_avg_dist_new:
                        st.subheader(f"Gemiddelde Afstand {aggregation_period_new_tab.lower()}")
                        fig_avg_dist_new = px.bar(
                            df_agg_new,
                            x='Periode',
                            y='Gem. Afstand (km)',
                            title=f'Gemiddelde Afstand {aggregation_period_new_tab.lower()}',
                            labels={'Periode': x_label, 'Gem. Afstand (km)': 'Gemiddelde Afstand (km)'},
                            template="plotly_dark",
                            text_auto='.2f'
                        )
                        fig_avg_dist_new.update_traces(textposition='outside', marker_color='#636EFA')
                        fig_avg_dist_new.update_layout(showlegend=False)
                        fig_avg_dist_new.update_xaxes(
                            tickangle=x_tickangle,
                            rangeslider_visible=show_xaxis_range_slider,
                            rangeselector=dict(
                                buttons=list([
                                    dict(count=1, label="1m", step="month", stepmode="backward"),
                                    dict(count=6, label="6m", step="month", stepmode="backward"),
                                    dict(count=1, label="1j", step="year", stepmode="backward"),
                                    dict(step="all")
                                ])
                            ) if show_xaxis_range_slider else None
                        )
                        if aggregation_period_new_tab == 'Per Maand':
                            fig_avg_dist_new.update_xaxes(
                                tickformat="%Y-%m",
                                dtick="M1",
                                ticklabelmode="period",
                                range=[df_agg_new['Periode'].min(), df_agg_new['Periode'].max()]
                            )
                        st.plotly_chart(fig_avg_dist_new, use_container_width=True)

                    col_total_dur_new, col_avg_dur_new = st.columns(2)

                    with col_total_dur_new:
                        st.subheader(f"Totale Duur {aggregation_period_new_tab.lower()}")
                        fig_total_dur_new = px.bar(
                            df_agg_new,
                            x='Periode',
                            y='Totale Duur (sec)',
                            title=f'Totale Duur {aggregation_period_new_tab.lower()}',
                            labels={'Periode': x_label, 'Totale Duur (sec)': 'Totale Duur (seconden)'},
                            template="plotly_dark",
                            text='Totale Duur (HH:MM:SS)'
                        )
                        fig_total_dur_new.update_traces(textposition='outside', marker_color='#00CC96')
                        fig_total_dur_new.update_layout(showlegend=False)
                        fig_total_dur_new.update_xaxes(
                            tickangle=x_tickangle,
                            rangeslider_visible=show_xaxis_range_slider,
                            rangeselector=dict(
                                buttons=list([
                                    dict(count=1, label="1m", step="month", stepmode="backward"),
                                    dict(count=6, label="6m", step="month", stepmode="backward"),
                                    dict(count=1, label="1j", step="year", stepmode="backward"),
                                    dict(step="all")
                                ])
                            ) if show_xaxis_range_slider else None
                        )
                        if aggregation_period_new_tab == 'Per Maand':
                            fig_total_dur_new.update_xaxes(
                                tickformat="%Y-%m",
                                dtick="M1",
                                ticklabelmode="period",
                                range=[df_agg_new['Periode'].min(), df_agg_new['Periode'].max()]
                            )
                        st.plotly_chart(fig_total_dur_new, use_container_width=True)

                    with col_avg_dur_new:
                        st.subheader(f"Gemiddelde Duur {aggregation_period_new_tab.lower()}")
                        fig_avg_dur_new = px.bar(
                            df_agg_new,
                            x='Periode',
                            y='Gem. Duur (sec)',
                            title=f'Gemiddelde Duur {aggregation_period_new_tab.lower()}',
                            labels={'Periode': x_label, 'Gem. Duur (sec)': 'Gemiddelde Duur (seconden)'},
                            template="plotly_dark",
                            text='Gem. Duur (HH:MM:SS)'
                        )
                        fig_avg_dur_new.update_traces(textposition='outside', marker_color='#EF553B')
                        fig_avg_dur_new.update_layout(showlegend=False)
                        fig_avg_dur_new.update_xaxes(
                            tickangle=x_tickangle,
                            rangeslider_visible=show_xaxis_range_slider,
                            rangeselector=dict(
                                buttons=list([
                                    dict(count=1, label="1m", step="month", stepmode="backward"),
                                    dict(count=6, label="6m", step="month", stepmode="backward"),
                                    dict(count=1, label="1j", step="year", stepmode="backward"),
                                    dict(step="all")
                                ])
                            ) if show_xaxis_range_slider else None
                        )
                        if aggregation_period_new_tab == 'Per Maand':
                            fig_avg_dur_new.update_xaxes(
                                tickformat="%Y-%m",
                                dtick="M1",
                                ticklabelmode="period",
                                range=[df_agg_new['Periode'].min(), df_agg_new['Periode'].max()]
                            )
                        st.plotly_chart(fig_avg_dur_new, use_container_width=True)

                    if 'Gem. Hartslag (bpm)' in df_agg_new.columns and df_agg_new['Gem. Hartslag (bpm)'].sum() > 0:
                        st.subheader(f"Gemiddelde Hartslag {aggregation_period_new_tab.lower()}")
                        fig_avg_hr_new = px.bar(
                            df_agg_new,
                            x='Periode',
                            y='Gem. Hartslag (bpm)',
                            title=f'Gemiddelde Hartslag {aggregation_period_new_tab.lower()}',
                            labels={'Periode': x_label, 'Gem. Hartslag (bpm)': 'Gemiddelde Hartslag (bpm)'},
                            template="plotly_dark",
                            text_auto='.0f'
                        )
                        fig_avg_hr_new.update_traces(textposition='outside', marker_color='#DAA520')
                        fig_avg_hr_new.update_layout(showlegend=False)
                        fig_avg_hr_new.update_xaxes(
                            tickangle=x_tickangle,
                            rangeslider_visible=show_xaxis_range_slider,
                            rangeselector=dict(
                                buttons=list([
                                    dict(count=1, label="1m", step="month", stepmode="backward"),
                                    dict(count=6, label="6m", step="month", stepmode="backward"),
                                    dict(count=1, label="1j", step="year", stepmode="backward"),
                                    dict(step="all")
                                ])
                            ) if show_xaxis_range_slider else None
                        )
                        if aggregation_period_new_tab == 'Per Maand':
                            fig_avg_hr_new.update_xaxes(
                                tickformat="%Y-%m",
                                dtick="M1",
                                ticklabelmode="period",
                                range=[df_agg_new['Periode'].min(), df_agg_new['Periode'].max()]
                            )
                        st.plotly_chart(fig_avg_hr_new, use_container_width=True)
                    else:
                        st.info("Niet genoeg hartslagdata om de grafiek te tonen. Controleer de kolommapping voor 'Gem. HS'.")

                else: # display_type == 'Tabel'
                    st.subheader(f"Overzichtstabel {aggregation_period_new_tab.lower()}")

                    if aggregation_period_new_tab == 'Per Week':
                        df_agg_new_display = df_agg_new[['Periode', 'Week Periode', 'Totaal Afstand (km)', 'Gem. Afstand (km)', 'Totale Duur (HH:MM:SS)', 'Gem. Duur (HH:MM:SS)', 'Gem. Hartslag (bpm)']].copy()
                    else:
                        df_agg_new_display = df_agg_new[['Periode', 'Totaal Afstand (km)', 'Gem. Afstand (km)', 'Totale Duur (HH:MM:SS)', 'Gem. Duur (HH:MM:SS)', 'Gem. Hartslag (bpm)']].copy()

                    st.dataframe(df_agg_new_display, use_container_width=True)

                    csv_export_agg = df_agg_new_display.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label=f"Download {aggregation_period_new_tab.lower()} overzicht als CSV",
                        data=csv_export_agg,
                        file_name=f"sportoverzicht_{aggregation_period_new_tab.lower().replace(' ', '_')}.csv",
                        mime="text/csv",
                    )

            else:
                st.info("Niet genoeg data (afstand, duur, hartslag of geldige datums/periodes) om het overzicht te tonen voor de geselecteerde filters. Controleer uw kolommapping en bestandsinhoud in het tabblad 'Data Instellingen'.")


    with tab5: # Ruwe Data tab
        st.header("Ruwe Gegevens")
        st.markdown("Hier kun je de gefilterde ruwe data bekijken en eventueel exporteren.")
        if not st.session_state.filtered_df.empty:
            st.dataframe(st.session_state.filtered_df)

            csv_export = st.session_state.filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download gefilterde data als CSV",
                data=csv_export,
                file_name="gefilterde_sportdata.csv",
                mime="text/csv",
            )
        else:
            st.info("Geen gefilterde ruwe data beschikbaar. Zorg ervoor dat de data correct is gemapt en gefilterd.")
