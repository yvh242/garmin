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
    df.columns = df.columns.str.strip().str.replace('Â®', '', regex=False).str.replace('\xa0', '', regex=False)

    # Definieer een mapping van verwachte Nederlandse kolomnamen naar interne, schone namen
    column_mapping = {
        "Activiteittype": "activity_type",
        "Datum": "date",
        "Favoriet": "favorite",
        "Titel": "title",
        "Afstand": "distance_km",
        "Calorieën": "calories_kcal",
        "Tijd": "duration_raw",
        "Gem. HS": "avg_heart_rate_bpm",
        "Max. HS": "max_heart_rate_bpm",
        "Gem. cadans": "avg_cadence",
        "Maximale cadans": "max_cadence",
        "Gemiddeld tempo": "avg_pace_raw",
        "Beste tempo": "best_pace_raw",
        "Totale stijging": "total_elevation_gain_m",
        "Totale daling": "total_elevation_loss_m",
        "Gem. staplengte": "avg_stride_length_cm",
        "Training Stress Score": "tss",
        "Stappen": "steps",
        "Min. temp.": "min_temp_celsius",
        "Decompressie": "decompression",
        "Beste": "best_overall",
    }

    # Hernoem kolommen op basis van de mapping
    df.rename(columns=column_mapping, inplace=True)

    # Controleer en converteer essentiële kolommen
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df.dropna(subset=['date'], inplace=True)
    else:
        st.warning("De 'Datum' kolom is niet gevonden. Sommige functionaliteiten werken mogelijk niet correct.")
        df['date'] = pd.NaT # Voeg kolom toe met Not a Time

    if 'distance_km' in df.columns:
        df['distance_km'] = df['distance_km'].astype(str).str.replace(',', '.', regex=False).astype(float).fillna(0)
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
        df['activity_type'] = 'Onbekend'

    # Tijd conversie: van HH:MM:SS string naar seconden
    def parse_time_to_seconds(time_str):
        if pd.isna(time_str): return 0
        try:
            parts = str(time_str).split(':')
            if len(parts) == 3: return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2: return int(parts[0]) * 60 + int(parts[1])
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
        df['avg_pace_sec_per_km'] = 0.0

    if 'best_pace_raw' in df.columns:
        df['best_pace_sec_per_km'] = df['best_pace_raw'].apply(parse_pace_to_seconds_per_unit)
    else:
        df['best_pace_sec_per_km'] = 0.0

    # Voeg week- en maandkolommen toe voor aggregatie
    if 'date' in df.columns and not df['date'].empty and df['date'].notna().any():
        # Formatteer year_week als 'YYYY-WW' zodat het correct sorteert en weergeeft
        df['year_week'] = df['date'].dt.strftime('%Y-%W')
        # Bereken de startdatum van de week voor elke activiteit
        df['date_week_start'] = df['date'].apply(lambda x: x - timedelta(days=x.weekday()))
        # Bereken de einddatum van de week
        df['date_week_end'] = df['date_week_start'] + timedelta(days=6)
        # Formatteer year_month als 'YYYY-MM'
        df['year_month'] = df['date'].dt.strftime('%Y-%m')
    else:
        df['year_week'] = 'Onbekend'
        df['year_month'] = 'Onbekend'
        df['date_week_start'] = pd.NaT
        df['date_week_end'] = pd.NaT


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

    df_full = None
    filtered_df = pd.DataFrame()

    if uploaded_file is not None:
        df_full = load_and_process_data(uploaded_file)
        if df_full is not None and not df_full.empty:
            st.success("Bestand succesvol geladen!")
            st.write(f"Totaal {len(df_full)} records gevonden.")

            # Datum filter
            st.header("Filter op datum")
            valid_dates = df_full['date'].dropna()
            if not valid_dates.empty:
                min_date_data = valid_dates.min().date()
                max_date_data = valid_dates.max().date()
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
                filtered_df = pd.DataFrame()
            else:
                filtered_df = df_full[(df_full['date'].dt.date >= start_date) & (df_full['date'].dt.date <= end_date)].copy()

            # Sla de geselecteerde datums op in session_state voor gebruik in tabs
            st.session_state.start_date_filter = start_date
            st.session_state.end_date_filter = end_date

            # Activiteittype filter
            st.header("Filter op Activiteittype")
            if 'activity_type' in filtered_df.columns and not filtered_df.empty:
                all_activity_types = ['Alle'] + sorted(filtered_df['activity_type'].dropna().unique().tolist())
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
st.title("🏃‍♂️ Sportactiviteiten Dashboard")
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
    tab1, tab_new_period_overview, tab5 = st.tabs([
        "📊 Afstand & Duur",
        "🗓️ Overzicht per Periode",
        "📋 Ruwe Data"
    ])

    with tab1:
        st.header("Afstand en Duur Overzicht")
        st.markdown("Bekijk hoe je afstand en duur zich ontwikkelen over de tijd.")

        col_dist_time, col_dur_time = st.columns(2)

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
                    hover_data={'duration_seconds':False, 'Tijd (HH:MM:SS)':True}
                )
                fig_duration_time.update_traces(mode='lines+markers', marker_size=5)
                st.plotly_chart(fig_duration_time, use_container_width=True)
        else:
            with col_dur_time:
                st.info("Niet genoeg data om 'Duur over tijd' te tonen.")


    # NIEUW TABBLAD: Overzicht per Periode
    with tab_new_period_overview:
        st.header("Overzicht per Week of Maand")
        st.markdown("Kies zelf of je de totale en gemiddelde waarden per **week** of per **maand** wilt bekijken.")

        # Keuzemenu voor week of maand
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

        if (not filtered_df.empty and
            'distance_km' in filtered_df.columns and filtered_df['distance_km'].notna().any() and
            'duration_seconds' in filtered_df.columns and filtered_df['duration_seconds'].notna().any() and
            'avg_heart_rate_bpm' in filtered_df.columns and filtered_df['avg_heart_rate_bpm'].notna().any() and # Added for avg heart rate
            'year_week' in filtered_df.columns and filtered_df['year_week'].notna().any() and
            'year_month' in filtered_df.columns and filtered_df['year_month'].notna().any()):

            if aggregation_period_new_tab == 'Per Week':
                # Eerst aggregeren op year_week
                df_agg_new = filtered_df.groupby('year_week').agg(
                    total_distance=('distance_km', 'sum'),
                    avg_distance=('distance_km', 'mean'),
                    total_duration=('duration_seconds', 'sum'),
                    avg_duration=('duration_seconds', 'mean'),
                    avg_heart_rate=('avg_heart_rate_bpm', lambda x: x[x > 0].mean()) # Gemiddelde HS, excl. 0-waarden
                ).reset_index()

                # Daarna de unieke start- en einddatums van de week ophalen en toevoegen
                # We nemen de min_date_week_start en max_date_week_end per year_week om consistentie te garanderen
                week_dates = filtered_df.groupby('year_week').agg(
                    min_date_week_start=('date_week_start', 'min'),
                    max_date_week_end=('date_week_end', 'max')
                ).reset_index()

                # Merge de geaggregeerde data met de weekdatums
                df_agg_new = pd.merge(df_agg_new, week_dates, on='year_week', how='left')

                df_agg_new.columns = ['Periode', 'Totaal Afstand (km)', 'Gem. Afstand (km)', 'Totale Duur (sec)', 'Gem. Duur (sec)', 'Gem. Hartslag (bpm)', 'Datum Week Start', 'Datum Week Einde']
                df_agg_new['Week Periode'] = df_agg_new['Datum Week Start'].dt.strftime('%d-%m') + ' t/m ' + df_agg_new['Datum Week Einde'].dt.strftime('%d-%m')

                x_label = 'Jaar-Week (JJJJ-WW)'
                show_xaxis_range_slider = True
                x_tickangle = 0 # Horizontale labels voor weken
            else: # Per Maand
                df_agg_new = filtered_df.groupby('year_month').agg(
                    total_distance=('distance_km', 'sum'),
                    avg_distance=('distance_km', 'mean'),
                    total_duration=('duration_seconds', 'sum'),
                    avg_duration=('duration_seconds', 'mean'),
                    avg_heart_rate=('avg_heart_rate_bpm', lambda x: x[x > 0].mean()) # Gemiddelde HS, excl. 0-waarden
                ).reset_index()
                df_agg_new.columns = ['Periode', 'Totaal Afstand (km)', 'Gem. Afstand (km)', 'Totale Duur (sec)', 'Gem. Duur (sec)', 'Gem. Hartslag (bpm)']
                x_label = 'Jaar-Maand (JJJJ-MM)'
                show_xaxis_range_slider = False
                x_tickangle = -45 # Schuine labels voor maanden


            # Formatteer duur kolommen voor weergave in zowel grafiek als tabel
            df_agg_new['Totale Duur (HH:MM:SS)'] = df_agg_new['Totale Duur (sec)'].apply(format_duration)
            df_agg_new['Gem. Duur (HH:MM:SS)'] = df_agg_new['Gem. Duur (sec)'].apply(format_duration)
            df_agg_new['Gem. Hartslag (bpm)'] = df_agg_new['Gem. Hartslag (bpm)'].round(0).astype('Int64').fillna(0) # Afronden naar heel getal, NaN naar 0

            if display_type == 'Grafiek':
                # --- Grafieken voor Totaal en Gemiddeld Afstand ---
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
                    # Specifieke aanpassing voor maandweergave in grafiek
                    if aggregation_period_new_tab == 'Per Maand':
                        fig_total_dist_new.update_xaxes(
                            tickformat="%Y-%m", # Formatteer als YYYY-MM
                            dtick="M1", # Toon elke maand
                            ticklabelmode="period", # Zorgt voor correcte labels bij de periode
                            # Ensure the last month is visible:
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
                    # Specifieke aanpassing voor maandweergave in grafiek
                    if aggregation_period_new_tab == 'Per Maand':
                        fig_avg_dist_new.update_xaxes(
                            tickformat="%Y-%m", # Formatteer als YYYY-MM
                            dtick="M1", # Toon elke maand
                            ticklabelmode="period", # Zorgt voor correcte labels bij de periode
                            # Ensure the last month is visible:
                            range=[df_agg_new['Periode'].min(), df_agg_new['Periode'].max()]
                        )
                    st.plotly_chart(fig_avg_dist_new, use_container_width=True)

                # --- Grafieken voor Totaal en Gemiddeld Duur ---
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
                    # Specifieke aanpassing voor maandweergave in grafiek
                    if aggregation_period_new_tab == 'Per Maand':
                        fig_total_dur_new.update_xaxes(
                            tickformat="%Y-%m", # Formatteer als YYYY-MM
                            dtick="M1", # Toon elke maand
                            ticklabelmode="period", # Zorgt voor correcte labels bij de periode
                            # Ensure the last month is visible:
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
                    # Specifieke aanpassing voor maandweergave in grafiek
                    if aggregation_period_new_tab == 'Per Maand':
                        fig_avg_dur_new.update_xaxes(
                            tickformat="%Y-%m", # Formatteer als YYYY-MM
                            dtick="M1", # Toon elke maand
                            ticklabelmode="period", # Zorgt voor correcte labels bij de periode
                            # Ensure the last month is visible:
                            range=[df_agg_new['Periode'].min(), df_agg_new['Periode'].max()]
                        )
                    st.plotly_chart(fig_avg_dur_new, use_container_width=True)

                # --- Grafiek voor Gemiddelde Hartslag (alleen in grafiekweergave) ---
                if 'Gem. Hartslag (bpm)' in df_agg_new.columns and df_agg_new['Gem. Hartslag (bpm)'].sum() > 0:
                    st.subheader(f"Gemiddelde Hartslag {aggregation_period_new_tab.lower()}")
                    fig_avg_hr_new = px.bar(
                        df_agg_new,
                        x='Periode',
                        y='Gem. Hartslag (bpm)',
                        title=f'Gemiddelde Hartslag {aggregation_period_new_tab.lower()}',
                        labels={'Periode': x_label, 'Gem. Hartslag (bpm)': 'Gemiddelde Hartslag (bpm)'},
                        template="plotly_dark",
                        text_auto='.0f' # Toont hele getallen
                    )
                    fig_avg_hr_new.update_traces(textposition='outside', marker_color='#DAA520') # Gouden kleur
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
                            tickformat="%Y-%m", # Formatteer als YYYY-MM
                            dtick="M1", # Toon elke maand
                            ticklabelmode="period", # Zorgt voor correcte labels bij de periode
                            # Ensure the last month is visible:
                            range=[df_agg_new['Periode'].min(), df_agg_new['Periode'].max()]
                        )
                    st.plotly_chart(fig_avg_hr_new, use_container_width=True)
                else:
                    st.info("Niet genoeg hartslagdata om de grafiek te tonen.")

            else: # display_type == 'Tabel'
                st.subheader(f"Overzichtstabel {aggregation_period_new_tab.lower()}")

                # Selecteer kolommen voor de tabelweergave, inclusief 'Week Periode' indien van toepassing
                if aggregation_period_new_tab == 'Per Week':
                    df_agg_new_display = df_agg_new[['Periode', 'Week Periode', 'Totaal Afstand (km)', 'Gem. Afstand (km)', 'Totale Duur (HH:MM:SS)', 'Gem. Duur (HH:MM:SS)', 'Gem. Hartslag (bpm)']].copy()
                else: # Per Maand
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
            st.info("Niet genoeg data (afstand, duur, hartslag of geldige datums/periodes) om het overzicht te tonen voor de geselecteerde filters.")


    with tab5: # Ruwe Data tab
        st.header("Ruwe Gegevens")
        st.markdown("Hier kun je de gefilterde ruwe data bekijken en eventueel exporteren.")
        st.dataframe(filtered_df)

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
