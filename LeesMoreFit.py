import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fitparse import FitFile
from datetime import datetime, timedelta

# --- Pagina Configuratie ---
st.set_page_config(
    page_title="FIT Bestanden Dashboard",
    page_icon="🚴‍♂️",
    layout="wide",
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

@st.cache_data(show_spinner="FIT bestand(en) inlezen en verwerken...")
def parse_fit_file(file_bytes, activity_id):
    """
    Parses a .fit file from bytes and extracts relevant activity data.
    Returns a DataFrame with key metrics.
    """
    try:
        fit_file = FitFile(file_bytes)

        records_data = []
        for record in fit_file.get_messages('record'):
            data = {}
            for field in record.fields:
                data[field.name] = field.value
            records_data.append(data)

        df = pd.DataFrame(records_data)

        # Rename common columns to a standardized format
        column_renames = {
            'timestamp': 'DatumTijd',
            'position_lat': 'Latitude_semicircles', # Raw format from FIT
            'position_long': 'Longitude_semicircles', # Raw format from FIT
            'distance': 'Afstand_m',
            'heart_rate': 'Hartslag_bpm',
            'cadence': 'Cadans_rpm', # or spm for running
            'speed': 'Snelheid_ms', # meters/second
            'altitude': 'Hoogte_m',
            'power': 'Vermogen_watts',
        }
        df.rename(columns=column_renames, inplace=True)

        # Convert raw semicircles GPS to degrees
        # 1 semicircle = 180 / 2^31 degrees
        if 'Latitude_semicircles' in df.columns and 'Longitude_semicircles' in df.columns:
            df['Latitude'] = df['Latitude_semicircles'] * (180 / 2**31)
            df['Longitude'] = df['Longitude_semicircles'] * (180 / 2**31)
            df.drop(columns=['Latitude_semicircles', 'Longitude_semicircles'], inplace=True)
        else:
            df['Latitude'] = pd.NA
            df['Longitude'] = pd.NA

        # Convert to more readable units
        if 'Afstand_m' in df.columns:
            df['Afstand_km'] = df['Afstand_m'] / 1000
        else:
            df['Afstand_km'] = 0.0

        if 'Snelheid_ms' in df.columns:
            df['Snelheid_kmh'] = df['Snelheid_ms'] * 3.6
        else:
            df['Snelheid_kmh'] = 0.0

        # Ensure datetime column is correct
        if 'DatumTijd' in df.columns:
            df['DatumTijd'] = pd.to_datetime(df['DatumTijd'], errors='coerce')
            df.dropna(subset=['DatumTijd'], inplace=True) # Drop rows where datetime is invalid
            df = df.sort_values(by='DatumTijd').reset_index(drop=True)
            df['Tijd_sec'] = (df['DatumTijd'] - df['DatumTijd'].iloc[0]).dt.total_seconds()
        else:
            st.error("Geen 'timestamp' data gevonden in het FIT-bestand. Kan geen dashboard genereren.")
            return pd.DataFrame()

        # Add the unique activity ID to the DataFrame
        df['Activity_ID'] = activity_id

        # --- Extract Session/Activity Summary Data (for KPIs) ---
        # Initialize with default values
        session_calories = 0
        session_max_speed_kmh = 0
        session_total_elevation_gain_m = 0
        activity_type = "Onbekend"

        # Loop through session messages to get summary data
        for session in fit_file.get_messages('session'):
            session_dict = session.as_dict()
            if 'sport' in session_dict and session_dict['sport'] is not None:
                activity_type = str(session_dict['sport']).replace('_', ' ').title()
            if 'total_calories' in session_dict and session_dict['total_calories'] is not None:
                session_calories = session_dict['total_calories']
            if 'max_speed' in session_dict and session_dict['max_speed'] is not None:
                session_max_speed_kmh = session_dict['max_speed'] * 3.6 # Convert m/s to km/h
            if 'total_elevation_gain' in session_dict and session_dict['total_elevation_gain'] is not None:
                 session_total_elevation_gain_m = session_dict['total_elevation_gain']
            break # Take the first found session, usually one session per file for an activity

        # Add these session-level totals as single-value columns to the DataFrame
        # This makes it easier to pass them around and display in KPIs
        df['Activiteitstype'] = activity_type
        df['Totale_Calorieën'] = session_calories
        df['Max_Snelheid_Activiteit'] = session_max_speed_kmh
        df['Totale_Stijging_Meters'] = session_total_elevation_gain_m

        return df

    except Exception as e:
        st.error(f"Fout bij het parsen van FIT-bestand '{activity_id}': {e}")
        return pd.DataFrame()

# --- Zijbalk voor bestand uploaden ---
with st.sidebar:
    st.header("Upload je FIT-bestand(en)")
    st.markdown("Upload hier één of meerdere .fit bestanden van je sportactiviteiten.")

    # Gebruik 'accept_multiple_files=True' om meerdere bestanden toe te staan
    uploaded_fit_files = st.file_uploader("Kies .fit bestand(en)", type=["fit"], accept_multiple_files=True)

    # Initialiseer st.session_state.fit_dfs_list om geparste individuele DFs te bewaren
    if 'fit_dfs_list' not in st.session_state:
        st.session_state.fit_dfs_list = []

    if uploaded_fit_files:
        # Check if current selection is different from previous to avoid re-parsing
        current_file_names = {f.name for f in uploaded_fit_files}
        previous_file_names = {df.attrs['original_filename'] for df in st.session_state.fit_dfs_list if 'original_filename' in df.attrs}

        if current_file_names != previous_file_names:
            st.session_state.fit_dfs_list = [] # Reset de lijst bij een nieuwe selectie
            st.info(f"Verwerken van {len(uploaded_fit_files)} bestand(en)...")
            all_dfs = []
            for idx, uploaded_file in enumerate(uploaded_fit_files):
                # Gebruik de bestandsnaam als unieke Activity_ID
                df_temp = parse_fit_file(uploaded_file.read(), uploaded_file.name)
                if not df_temp.empty:
                    df_temp.attrs['original_filename'] = uploaded_file.name # Bewaar de originele bestandsnaam
                    all_dfs.append(df_temp)

            if all_dfs:
                # Combineer alle geparste DataFrames in één groot DataFrame
                st.session_state.fit_df = pd.concat(all_dfs, ignore_index=True)
                st.session_state.fit_dfs_list = all_dfs # Bewaar ook de individuele DFs voor eventuele toekomstige behoeften
                st.success(f"{len(all_dfs)} FIT bestand(en) succesvol ingelezen!")
            else:
                st.warning("Geen bruikbare data gevonden in de geüploade FIT bestanden.")
                st.session_state.fit_df = pd.DataFrame()
                st.session_state.fit_dfs_list = []
        else:
            if not st.session_state.fit_df.empty:
                st.success(f"{len(uploaded_fit_files)} FIT bestand(en) zijn al geladen.")
    else:
        # Reset de DataFrames als er geen bestanden geselecteerd zijn
        st.session_state.fit_df = pd.DataFrame()
        st.session_state.fit_dfs_list = []
        st.info("Upload een of meerdere .fit bestanden met je sportactiviteiten om het dashboard te genereren.")

# --- Hoofd Dashboard Content ---
st.title("🚴‍♂️ FIT Bestand Analyse Dashboard")
st.markdown("Upload één of meerdere .fit-bestanden om je activiteit(en) te visualiseren.")

if st.session_state.get('fit_df', pd.DataFrame()).empty:
    st.info("Upload een of meerdere .fit-bestanden in de zijbalk om je sportactiviteit(en) te analyseren. Deze app is specifiek voor .fit-bestanden.")
else:
    df = st.session_state.fit_df # Dit DataFrame bevat nu alle gecombineerde data

    # --- Algemene KPI's ---
    st.subheader("Overzicht van de Activiteiten")

    # Bereken KPI's over ALLE activiteiten in het gecombineerde DataFrame
    num_activities = df['Activity_ID'].nunique()

    # Totale afstand van de langste activiteit OF de som van alle afstanden (kies degene die je wilt)
    # Hier is de som van de max afstanden per activiteit:
    total_distance_combined_km = df.groupby('Activity_ID')['Afstand_km'].max().sum() if 'Afstand_km' in df.columns else 0

    # Som van de duur van elke activiteit
    total_duration_seconds_combined = df.groupby('Activity_ID')['Tijd_sec'].max().sum() if 'Tijd_sec' in df.columns else 0

    # Gemiddelde hartslag over alle activiteiten (gemiddelde van de gemiddelden per activiteit)
    avg_heart_rate_combined = df.groupby('Activity_ID')['Hartslag_bpm'].mean().mean() if 'Hartslag_bpm' in df.columns else 0

    # Max hartslag over alle activiteiten (maximum van alle geregistreerde hartslagen)
    max_heart_rate_overall = df['Hartslag_bpm'].max() if 'Hartslag_bpm' in df.columns else 0

    # Deze KPI's komen nu direct uit de sessie-data die we aan de DF hebben toegevoegd
    total_calories_combined = df['Totale_Calorieën'].sum() if 'Totale_Calorieën' in df.columns else 0
    max_speed_kmh_combined_from_session = df['Max_Snelheid_Activiteit'].max() if 'Max_Snelheid_Activiteit' in df.columns else 0
    total_elevation_gain_combined = df['Totale_Stijging_Meters'].sum() if 'Totale_Stijging_Meters' in df.columns else 0


    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
        st.metric(label="Aantal Activiteiten", value=num_activities)
    with kpi2:
        st.metric(label="Totale Afstand (gecombineerd)", value=f"{total_distance_combined_km:,.2f} km")
    with kpi3:
        st.metric(label="Totale Duur (gecombineerd)", value=format_duration(total_duration_seconds_combined))
    with kpi4:
        st.metric(label="Gem. Hartslag (gecombineerd)", value=f"{avg_heart_rate_combined:,.0f} bpm" if avg_heart_rate_combined > 0 and not pd.isna(avg_heart_rate_combined) else "N/B")

    kpi5, kpi6, kpi7 = st.columns(3)
    with kpi5:
        st.metric(label="Totaal Calorieën (gecombineerd)", value=f"{total_calories_combined:,.0f} kcal" if total_calories_combined > 0 else "N/B")
    with kpi6:
        st.metric(label="Max. Hartslag (over alle)", value=f"{max_heart_rate_overall:,.0f} bpm" if max_heart_rate_overall > 0 else "N/B")
    with kpi7:
        st.metric(label="Totale Stijging (gecombineerd)", value=f"{total_elevation_gain_combined:,.0f} m" if total_elevation_gain_combined > 0 else "N/B")

    st.markdown("---")

    tab_performance, tab_map, tab_raw_data = st.tabs(["📊 Prestaties over Tijd", "🗺️ Activiteit Route", "📋 Ruwe Data"])

    with tab_performance:
        st.subheader("Prestaties over Tijd (per activiteit)")
        # Voeg een selector toe om specifieke activiteiten te kiezen voor de tijdreeksgrafieken
        activity_selection_for_plots = st.selectbox(
            "Selecteer activiteit voor tijdreeksgrafieken:",
            options=['Alle Activiteiten (overlay)'] + sorted(list(df['Activity_ID'].unique())), # Optie om alles te overlayen, gesorteerd
            key="activity_plot_select"
        )
        plot_df = df.copy()
        if activity_selection_for_plots != 'Alle Activiteiten (overlay)':
            plot_df = df[df['Activity_ID'] == activity_selection_for_plots]

        # Selectiebox voor de y-as (deze logica blijft hetzelfde, maar werkt nu op plot_df)
        available_metrics = {
            "Hartslag (bpm)": "Hartslag_bpm",
            "Snelheid (km/u)": "Snelheid_kmh",
            "Hoogte (m)": "Hoogte_m",
            "Cadans (rpm/spm)": "Cadans_rpm",
            "Vermogen (watts)": "Vermogen_watts",
            "Afstand (km)": "Afstand_km"
        }

        plottable_metrics = {
            label: col for label, col in available_metrics.items()
            if col in plot_df.columns and (plot_df[col].sum() > 0 or col in ['Hoogte_m', 'Afstand_km'])
        }

        if not plottable_metrics:
            st.warning("Niet genoeg numerieke data om grafieken te genereren.")
        else:
            selected_metric = st.selectbox(
                "Selecteer een meting om te visualiseren:",
                options=list(plottable_metrics.keys()),
                key="metric_selection_multi" # Unieke sleutel
            )

            y_column = plottable_metrics[selected_metric]

            if 'DatumTijd' in plot_df.columns and not plot_df.empty and not plot_df['DatumTijd'].empty:
                # Voeg 'color='Activity_ID'' toe voor meerdere lijnen als 'Alle Activiteiten' is geselecteerd
                fig = px.line(
                    plot_df,
                    x='DatumTijd',
                    y=y_column,
                    color='Activity_ID' if activity_selection_for_plots == 'Alle Activiteiten (overlay)' else None, # Kleur per activiteit
                    title=f'{selected_metric} over Tijd' + (f' voor {activity_selection_for_plots}' if activity_selection_for_plots != 'Alle Activiteiten (overlay)' else ''),
                    labels={'DatumTijd': 'Tijd', y_column: selected_metric, 'Activity_ID': 'Activiteit'},
                    template="plotly_dark",
                    line_shape='spline'
                )
                fig.update_xaxes(rangeslider_visible=True, rangeselector=dict(
                    buttons=list([
                        dict(count=1, label="1m", step="minute", stepmode="backward"),
                        dict(count=5, label="5m", step="minute", stepmode="backward"),
                        dict(count=1, label="1u", step="hour", stepmode="backward"),
                        dict(step="all")
                    ])
                ))
                fig.update_layout(hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': True})
            else:
                st.error("Kan geen tijdreeksgrafieken genereren, 'DatumTijd' kolom ontbreekt of is leeg na verwerking voor de geselecteerde activiteit(en).")

    with tab_map:
        st.subheader("Activiteiten Routes op Kaart")
        if 'Latitude' in df.columns and 'Longitude' in df.columns and df['Latitude'].notna().any() and df['Longitude'].notna().any():
            # Filter rijen met geldige GPS-coördinaten
            df_map = df.dropna(subset=['Latitude', 'Longitude']).copy()

            if not df_map.empty:
                # Gemiddelde positie om de kaart te centreren
                center_lat = df_map['Latitude'].mean()
                center_lon = df_map['Longitude'].mean()

                # Maak de kaart
                fig_map = px.line_mapbox(
                    df_map,
                    lat="Latitude",
                    lon="Longitude",
                    color="Activity_ID", # Kleurt de lijnen per Activity_ID
                    zoom=12,
                    height=1100, # Aangepaste hoogte voor betere visualisatie
                    mapbox_style="open-street-map",
                    title="Afgelegde Routes",
                    hover_name="Activity_ID", # Toon Activity_ID bij hover
                    hover_data={'DatumTijd': True, 'Afstand_km': ':.2f', 'Hartslag_bpm': True, 'Activity_ID': False}
                )

                # Optioneel: Voeg start- en eindpunten toe voor ELKE activiteit
                for activity_id in df_map['Activity_ID'].unique():
                    activity_df = df_map[df_map['Activity_ID'] == activity_id]
                    if not activity_df.empty:
                        # Startpunt
                        fig_map.add_trace(go.Scattermapbox(
                            lat=[activity_df['Latitude'].iloc[0]],
                            lon=[activity_df['Longitude'].iloc[0]],
                            mode='markers',
                            marker=go.scattermapbox.Marker(size=10, color='green', symbol='circle'),
                            name=f'Start: {activity_id}', # Naam voor de legenda
                            hoverinfo='name'
                        ))
                        # Eindpunt
                        fig_map.add_trace(go.Scattermapbox(
                            lat=[activity_df['Latitude'].iloc[-1]],
                            lon=[activity_df['Longitude'].iloc[-1]],
                            mode='markers',
                            marker=go.scattermapbox.Marker(size=10, color='red', symbol='circle'),
                            name=f'Eind: {activity_id}', # Naam voor de legenda
                            hoverinfo='name'
                        ))

                fig_map.update_layout(mapbox_center={"lat": center_lat, "lon": center_lon})
                st.plotly_chart(fig_map, use_container_width=True, config={'displayModeBar': True})
            else:
                st.info("Geen geldige GPS-coördinaten gevonden in de bestanden om de routes te tonen.")
        else:
            st.info("Geen GPS-coördinaten (Latitude/Longitude) beschikbaar in de geüploade FIT-bestanden om de routes te tonen.")


    with tab_raw_data: # Ruwe Data tab
        st.header("Ruwe Gegevens")
        st.markdown("Hier kun je de verwerkte ruwe data van alle activiteiten bekijken en eventueel exporteren.")
        if not st.session_state.fit_df.empty:
            st.dataframe(st.session_state.fit_df)

            csv_export = st.session_state.fit_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download verwerkte data als CSV",
                data=csv_export,
                file_name="fit_data_processed_combined.csv",
                mime="text/csv",
            )
        else:
            st.info("Geen verwerkte ruwe data beschikbaar.")
