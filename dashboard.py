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

    # --- Zorg ervoor dat alle benodigde kolommen bestaan en correct geconverteerd zijn ---
    # Voeg kolommen toe met standaardwaarden indien ze niet bestaan
    # Dit voorkomt KeyErrors en zorgt ervoor dat de app niet crasht.

    # Date kolom
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df.dropna(subset=['date'], inplace=True) # Verwijder rijen met ongeldige datums
    else:
        st.warning("De 'Datum' kolom is niet gevonden. Datum-gerelateerde analyses werken mogelijk niet.")
        df['date'] = pd.NaT # Not a Time

    # Numeric/Float kolommen, vul NaN met 0
    numeric_cols = {
        'distance_km': 0.0,
        'calories_kcal': 0.0,
        'steps': 0.0,
        'avg_heart_rate_bpm': 0.0,
        'max_heart_rate_bpm': 0.0,
        'avg_cadence': 0.0,
        'max_cadence': 0.0,
        'total_elevation_gain_m': 0.0,
        'total_elevation_loss_m': 0.0,
        'avg_stride_length_cm': 0.0,
        'tss': 0.0,
        'min_temp_celsius': 0.0,
    }
    for col, default_val in numeric_cols.items():
        if col in df.columns:
            # Vervang komma's door punten voor float conversie
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(default_val)
        else:
            if col != 'duration_raw' and col != 'avg_pace_raw' and col != 'best_pace_raw': # Deze worden anders afgehandeld
                st.warning(f"De kolom '{col}' is niet gevonden. Data hiervoor zal 0 zijn.")
                df[col] = default_val

    # String kolommen, vul NaN met 'Onbekend'
    string_cols = {
        'activity_type': 'Onbekend',
        'favorite': 'Onbekend',
        'title': 'Geen Titel',
        'decompression': 'Onbekend',
        'best_overall': 'Onbekend',
    }
    for col, default_val in string_cols.items():
        if col not in df.columns:
            st.warning(f"De kolom '{col}' is niet gevonden. Data hiervoor zal '{default_val}' zijn.")
            df[col] = default_val
        else:
            df[col] = df[col].fillna(default_val) # Vul ook bestaande NaN's op

    # Tijd conversie: van HH:MM:SS string naar seconden
    def parse_time_to_seconds(time_str):
        if pd.isna(time_str): return 0
        try:
            parts = str(time_str).split(':')
            if len(parts) == 3: return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2: return int(parts[0]) * 60 + int(parts[1]) # Kan voorkomen bij tempo format (MM:SS)
            else: return float(time_str) # Voor het geval het al een nummer is
        except (ValueError, TypeError): return 0

    if 'duration_raw' in df.columns:
        df['duration_seconds'] = df['duration_raw'].apply(parse_time_to_seconds)
    else:
        st.warning("De 'Tijd' kolom (duur) is niet gevonden. Duur analyses zijn niet mogelijk.")
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
        st.warning("De 'Gemiddeld tempo' kolom is niet gevonden.")
        df['avg_pace_sec_per_km'] = 0.0

    if 'best_pace_raw' in df.columns:
        df['best_pace_sec_per_km'] = df['best_pace_raw'].apply(parse_pace_to_seconds_per_unit)
    else:
        st.warning("De 'Beste tempo' kolom is niet gevonden.")
        df['best_pace_sec_per_km'] = 0.0

    # Voeg week- en maandkolommen toe voor aggregatie als de 'date' kolom geldig is
    if not df['date'].empty and df['date'].notna().any():
        df['year_week'] = df['date'].dt.strftime('%Y-%W')
        df['year_month'] = df['date'].dt.strftime('%Y-%m')
        # Bepaal het begin van de week voor elke datum, handig voor x-as in grafieken
        df['date_week_start'] = df['date'].apply(lambda x: x - timedelta(days=x.weekday()))
    else:
        st.warning("Geen geldige datums gevonden na verwerking. Tijd-gebaseerde aggregaties zijn beperkt.")
        df['year_week'] = 'Onbekend'
        df['year_month'] = 'Onbekend'
        df['date_week_start'] = pd.NaT

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
            # Check for NaT values before min()/max()
            valid_dates = df_full['date'].dropna()
            if not valid_dates.empty:
                min_date_data = valid_dates.min().date()
                max_date_data = valid_dates.max().date()
            else:
                st.warning("Geen geldige datums gevonden in het bestand. Datumfilter is uitgeschakeld.")
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
                # Filter alleen op rijen waar de datum geldig is
                filtered_df = df_full[
                    df_full['date'].notna() & # Zorg ervoor dat de datum geen NaT is
                    (df_full['date'].dt.date >= start_date) &
                    (df_full['date'].dt.date <= end_date)
                ].copy() # .copy() om SettingWithCopyWarning te voorkomen

            # Activiteittype filter
            st.header("Filter op Activiteittype")
            if 'activity_type' in filtered_df.columns and not filtered_df.empty:
                # Zorg ervoor dat er geen lege strings of NaN's in unique() komen
                unique_activities = filtered_df['activity_type'].dropna().unique().tolist()
                all_activity_types = ['Alle'] + sorted(unique_activities)
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

        # Controleer of de benodigde kolommen bestaan en data bevatten
        if 'date' in filtered_df.columns and 'distance_km' in filtered_df.columns and filtered_df['date'].notna().any():
            with col_dist_time:
                st.subheader("Afstand over tijd")
                df_daily_distance = filtered_df.groupby('date')['distance_km'].sum().reset_index()
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
                st.info("Niet genoeg data om 'Afstand over tijd' te tonen.")

        if 'date' in filtered_df.columns and 'duration_seconds' in filtered_df.columns and filtered_df['date'].notna().any():
            with col_dur_time:
                st.subheader("Duur over tijd")
                df_daily_duration = filtered_df.groupby('date')['duration_seconds'].sum().reset_index()
                df_daily_duration['Tijd (HH:MM:SS)'] = df_daily_duration['duration_seconds'].apply(format_duration)
                fig_duration_time = px.line(
                    df_daily_duration,
                    x='date',
                    y='duration_seconds',
                    title='Totale Duur per Dag',
                    labels={'duration_seconds': 'Duur (seconden)', 'date': 'Datum'},
                    template="plotly_dark",
                    hover_data={'duration_seconds':False, 'Tijd (HH:MM:SS)':True} # Toon geformatteerde duur
                )
                fig_duration_time.update_traces(mode='lines+markers', marker_size=5)
                st.plotly_chart(fig_duration_time, use_container_width=True)
        else:
            with col_dur_time:
                st.info("Niet genoeg data om 'Duur over tijd' te tonen.")


    with tab2:
        st.header("Tempo en Hartslag Analyse")
        st.markdown("Inzichten in je prestatie-indicatoren zoals tempo en hartslag.")

        col_pace, col_hr = st.columns(2)

        if 'avg_pace_sec_per_km' in filtered_df.columns and 'activity_type' in filtered_df.columns:
            with col_pace:
                st.subheader("Gemiddeld Tempo per Activiteit")
                # Filter rijen waar avg_pace_sec_per_km 0 is als dit niet representatief is
                df_pace_filtered = filtered_df[filtered_df['avg_pace_sec_per_km'] > 0]
                if not df_pace_filtered.empty:
                    df_pace_filtered['Gemiddeld tempo Display'] = df_pace_filtered['avg_pace_sec_per_km'].apply(lambda x: f"{int(x // 60):02d}:{int(x % 60):02d}")
                    fig_pace_dist = px.box(
                        df_pace_filtered,
                        x='activity_type',
                        y='avg_pace_sec_per_km',
                        title='Distributie van Gemiddeld Tempo per Activiteittype',
                        labels={'avg_pace_sec_per_km': 'Gemiddeld Tempo (sec/km)'},
                        template="plotly_dark",
                        color='activity_type'
                    )
                    st.plotly_chart(fig_pace_dist, use_container_width=True)
                else:
                    st.info("Tempo data niet beschikbaar voor analyse of alle waarden zijn 0.")
        else:
            with col_pace:
                st.info("Tempo data niet beschikbaar voor analyse.")

        if 'avg_heart_rate_bpm' in filtered_df.columns and 'activity_type' in filtered_df.columns:
            with col_hr:
                st.subheader("Gemiddelde Hartslag per Activiteit")
                df_hr_filtered = filtered_df[filtered_df['avg_heart_rate_bpm'] > 0]
                if not df_hr_filtered.empty:
                    fig_hr_dist = px.box(
                        df_hr_filtered,
                        x='activity_type',
                        y='avg_heart_rate_bpm',
                        title='Distributie van Gemiddelde Hartslag per Activiteittype',
                        labels={'avg_heart_rate_bpm': 'Gemiddelde Hartslag (bpm)'},
                        template="plotly_dark",
                        color='activity_type'
                    )
                    st.plotly_chart(fig_hr_dist, use_container_width=True)
                else:
                    st.info("Hartslag data niet beschikbaar voor analyse of alle waarden zijn 0.")
        else:
            with col_hr:
                st.info("Hartslag data niet beschikbaar voor analyse.")


        st.subheader("Afstand vs. Hartslag per Activiteit")
        if ('distance_km' in filtered_df.columns and 'avg_heart_rate_bpm' in filtered_df.columns and
            filtered_df['distance_km'].sum() > 0 and filtered_df['avg_heart_rate_bpm'].sum() > 0):
            fig_scatter_hr = px.scatter(
                filtered_df,
                x='distance_km',
                y='avg_heart_rate_bpm',
                color='activity_type',
                size='duration_seconds', # Grootte van de stip gebaseerd op duur
                hover_name='title',
                title='Afstand vs. Gemiddelde Hartslag',
                labels={'distance_km': 'Afstand (km)', 'avg_heart_rate_bpm': 'Gemiddelde Hartslag (bpm)'},
                template="plotly_dark"
            )
            st.plotly_chart(fig_scatter_hr, use_container_width=True)
        else:
            st.info("Afstand of hartslag data ontbreekt voor deze analyse.")


    with tab3:
        st.header("Analyse per Activiteittype")
        st.markdown("Duik dieper in je prestaties per type activiteit.")

        # Totaal afstand & Gemiddelde afstand per activiteittype
        col_total_dist_type, col_avg_dist_type = st.columns(2)

        if 'distance_km' in filtered_df.columns and 'activity_type' in filtered_df.columns and filtered_df['distance_km'].sum() > 0:
            with col_total_dist_type:
                st.subheader("Totale Afstand per Activiteittype")
                df_total_distance_by_type = filtered_df.groupby('activity_type')['distance_km'].sum().reset_index()
                df_total_distance_by_type = df_total_distance_by_type.sort_values(by='distance_km', ascending=False)
                fig_total_distance_type = px.bar(
                    df_total_distance_by_type,
                    x='activity_type',
                    y='distance_km',
                    title='Totaal Afstand per Activiteittype',
                    labels={'distance_km': 'Totale Afstand (km)', 'activity_type': 'Activiteittype'},
                    template="plotly_dark",
                    color='activity_type'
                )
                st.plotly_chart(fig_total_distance_type, use_container_width=True)

            with col_avg_dist_type:
                st.subheader("Gemiddelde Afstand per Activiteittype")
                df_avg_distance_by_type = filtered_df.groupby('activity_type')['distance_km'].mean().reset_index()
                df_avg_distance_by_type = df_avg_distance_by_type.sort_values(by='distance_km', ascending=False)
                fig_avg_distance_type = px.bar(
                    df_avg_distance_by_type,
                    x='activity_type',
                    y='distance_km',
                    title='Gemiddelde Afstand per Activiteittype',
                    labels={'distance_km': 'Gemiddelde Afstand (km)', 'activity_type': 'Activiteittype'},
                    template="plotly_dark",
                    color='activity_type'
                )
                st.plotly_chart(fig_avg_distance_type, use_container_width=True)
        else:
            st.info("Afstand data ontbreekt voor deze analyse.")

        # Calorieën en Stappen per activiteittype
        col_calories_type, col_steps_type = st.columns(2)

        if 'calories_kcal' in filtered_df.columns and 'activity_type' in filtered_df.columns and filtered_df['calories_kcal'].sum() > 0:
            with col_calories_type:
                st.subheader("Totaal Calorieën per Activiteittype")
                df_total_calories_by_type = filtered_df.groupby('activity_type')['calories_kcal'].sum().reset_index()
                df_total_calories_by_type = df_total_calories_by_type.sort_values(by='calories_kcal', ascending=False)
                fig_calories_type = px.pie(
                    df_total_calories_by_type,
                    values='calories_kcal',
                    names='activity_type',
                    title='Verdeling Calorieën per Activiteittype',
                    template="plotly_dark",
                    hole=0.4 # Maak er een donut chart van
                )
                st.plotly_chart(fig_calories_type, use_container_width=True)
        else:
            with col_calories_type:
                st.info("Calorieën data ontbreekt voor deze analyse.")

        if 'steps' in filtered_df.columns and 'activity_type' in filtered_df.columns and filtered_df['steps'].sum() > 0:
            with col_steps_type:
                st.subheader("Totaal Aantal Stappen per Activiteittype")
                df_total_steps_by_type = filtered_df.groupby('activity_type')['steps'].sum().reset_index()
                df_total_steps_by_type = df_total_steps_by_type.sort_values(by='steps', ascending=False)
                fig_steps_type = px.bar(
                    df_total_steps_by_type,
                    x='activity_type',
                    y='steps',
                    title='Totaal Stappen per Activiteittype',
                    labels={'steps': 'Totaal Aantal Stappen', 'activity_type': 'Activiteittype'},
                    template="plotly_dark",
                    color='activity_type'
                )
                st.plotly_chart(fig_steps_type, use_container_width=True)
        else:
            with col_steps_type:
                st.info("Stappen data ontbreekt voor deze analyse.")


    with tab4: # Nieuw tabblad voor vergelijking per week/maand
        st.header("Vergelijking van Afstand en Duur")
        st.markdown("Bekijk je **gemiddelde** afstand en duur geaggregeerd.")

        # Keuzemenu voor week of maand
        aggregation_period = st.radio(
            "Kies aggregatieperiode:",
            ('Per Week', 'Per Maand'),
            horizontal=True,
            key='agg_period_radio' # Voeg een unieke key toe
        )
        st.markdown(f"**Toont gemiddelde waarden {aggregation_period.lower()}**")


        # Controleer of de benodigde kolommen bestaan en data bevatten
        if (not filtered_df.empty and
            'distance_km' in filtered_df.columns and filtered_df['distance_km'].notna().any() and
            'duration_seconds' in filtered_df.columns and filtered_df['duration_seconds'].notna().any() and
            'year_week' in filtered_df.columns and filtered_df['year_week'].notna().any() and
            'year_month' in filtered_df.columns and filtered_df['year_month'].notna().any()):

            if aggregation_period == 'Per Week':
                df_agg = filtered_df.groupby('year_week').agg(
                    avg_distance=('distance_km', 'mean'),
                    avg_duration=('duration_seconds', 'mean')
                ).reset_index()
                df_agg.columns = ['Periode', 'Gem. Afstand (km)', 'Gem. Duur (sec)']
                df_agg['Gem. Duur (HH:MM:SS)'] = df_agg['Gem. Duur (sec)'].apply(format_duration)
                x_label = 'Jaar-Week'

            else: # Per Maand
                df_agg = filtered_df.groupby('year_month').agg(
                    avg_distance=('distance_km', 'mean'),
                    avg_duration=('duration_seconds', 'mean')
                ).reset_index()
                df_agg.columns = ['Periode', 'Gem. Afstand (km)', 'Gem. Duur (sec)']
                df_agg['Gem. Duur (HH:MM:SS)'] = df_agg['Gem. Duur (sec)'].apply(format_duration)
                x_label = 'Jaar-Maand'

            # --- Grafieken ---
            col_agg_dist, col_agg_dur = st.columns(2)

            with col_agg_dist:
                st.subheader(f"Gemiddelde Afstand {aggregation_period.lower()}")
                fig_agg_dist = px.bar(
                    df_agg,
                    x='Periode',
                    y='Gem. Afstand (km)',
                    title=f'Gemiddelde Afstand {aggregation_period.lower()}',
                    labels={'Periode': x_label, 'Gem. Afstand (km)': 'Gemiddelde Afstand (km)'},
                    template="plotly_dark",
                    text_auto='.2f' # Toon waarde op de balk, 2 decimalen
                )
                fig_agg_dist.update_traces(textposition='outside', marker_color='#FF4B4B') # Gebruik primaire kleur
                fig_agg_dist.update_layout(showlegend=False) # Verwijder legende
                st.plotly_chart(fig_agg_dist, use_container_width=True)

            with col_agg_dur:
                st.subheader(f"Gemiddelde Duur {aggregation_period.lower()}")
                fig_agg_dur = px.bar(
                    df_agg,
                    x='Periode',
                    y='Gem. Duur (sec)',
                    title=f'Gemiddelde Duur {aggregation_period.lower()}',
                    labels={'Periode': x_label, 'Gem. Duur (sec)': 'Gemiddelde Duur (seconden)'},
                    template="plotly_dark",
                    text='Gem. Duur (HH:MM:SS)' # Toon geformatteerde duur op de balk
                )
                fig_agg_dur.update_traces(textposition='outside', marker_color='#636EFA') # Gebruik een andere standaardkleur
                fig_agg_dur.update_layout(showlegend=False) # Verwijder legende
                st.plotly_chart(fig_agg_dur, use_container_width=True)
        else:
            st.info("Niet genoeg data (afstand, duur, of geldige datums/periodes) om de vergelijking te tonen voor de geselecteerde filters.")


    with tab5: # Ruwe Data tab
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
    st.info("Upload een Excel- of CSV-bestand met je sportactiviteiten om het dashboard te genereren.")
    st.markdown("---")
    st.markdown("""
        **Tip:** Zorg ervoor dat je bestand kolommen bevat zoals `Activiteittype`, `Datum`, `Afstand`, `Calorieën`, en `Tijd` voor de beste analyse.
    """)
    if uploaded_file is not None and df_full is not None and df_full.empty:
        st.warning("Het geüploade bestand bevat geen leesbare gegevens.")
