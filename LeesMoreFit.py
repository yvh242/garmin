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
            # Tijd_sec based on timestamp difference (Elapsed Time) - not used for total duration anymore
            # df['Tijd_sec'] = (df['DatumTijd'] - df['DatumTijd'].iloc[0]).dt.total_seconds()
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
        session_total_timer_time = 0 # NEW: Initialize total_timer_time

        # Loop through session messages to get summary data
        for session in fit_file.get_messages('session'):
            session_dict = session.as_dict()
            if 'sport' in session_dict and session_dict['sport'] is not None:
                activity_type = str(session_dict['sport']).replace('_', ' ').title()
            if 'total_calories' in session_dict and session_dict['total_calories'] is not None:
                session_calories = session_dict['total_calories']
            if 'max_speed' in session_dict and session_dict['max_speed'] is not None:
                session_max_speed_kmh = session_dict['max_speed'] * 3.6
            if 'total_elevation_gain' in session_dict and session_dict['total_elevation_gain'] is not None:
                 session_total_elevation_gain_m = session_dict['total_elevation_gain']
            if 'total_timer_time' in session_dict and session_dict['total_timer_time'] is not None: # NEW: Read total_timer_time
                session_total_timer_time = session_dict['total_timer_time']
            break # Take the first found session, usually one session per file for an activity

        # Add these session-level totals as single-value columns to the DataFrame
        df['Activiteitstype'] = activity_type
        df['Totale_Calorieën'] = session_calories
        df['Max_Snelheid_Activiteit'] = session_max_speed_kmh
        df['Totale_Stijging_Meters'] = session_total_elevation_gain_m
        df['Totale_Duur_Timer_Sec'] = session_total_timer_time # NEW: Add to DataFrame

        return df

    except Exception as e:
        st.error(f"Fout bij het parsen van FIT-bestand '{activity_id}': {e}")
        return pd.DataFrame()

# --- Zijbalk voor bestand uploaden ---
with st.sidebar:
    st.header("Upload je FIT-bestand(en)")
    st.markdown("Upload hier één of meerdere .fit bestanden van je sportactiviteiten.")

    uploaded_fit_files = st.file_uploader("Kies .fit bestand(en)", type=["fit"], accept_multiple_files=True)

    if 'fit_dfs_list' not in st.session_state:
        st.session_state.fit_dfs_list = []

    if uploaded_fit_files:
        current_file_names = {f.name for f in uploaded_fit_files}
        previous_file_names = {df.attrs['original_filename'] for df in st.session_state.fit_dfs_list if 'original_filename' in df.attrs}

        if current_file_names != previous_file_names:
            st.session_state.fit_dfs_list = []
            st.info(f"Verwerken van {len(uploaded_fit_files)} bestand(en)...")
            all_dfs = []
            for idx, uploaded_file in enumerate(uploaded_fit_files):
                df_temp = parse_fit_file(uploaded_file.read(), uploaded_file.name)
                if not df_temp.empty:
                    df_temp.attrs['original_filename'] = uploaded_file.name
                    all_dfs.append(df_temp)

            if all_dfs:
                st.session_state.fit_df = pd.concat(all_dfs, ignore_index=True)
                st.session_state.fit_dfs_list = all_dfs
                st.success(f"{len(all_dfs)} FIT bestand(en) succesvol ingelezen!")
            else:
                st.warning("Geen bruikbare data gevonden in de geüploade FIT bestanden.")
                st.session_state.fit_df = pd.DataFrame()
                st.session_state.fit_dfs_list = []
        else:
            if not st.session_state.fit_df.empty:
                st.success(f"{len(uploaded_fit_files)} FIT bestand(en) zijn al geladen.")
    else:
        st.session_state.fit_df = pd.DataFrame()
        st.session_state.fit_dfs_list = []
        st.info("Upload een of meerdere .fit bestanden met je sportactiviteiten om het dashboard te genereren.")

# --- Hoofd Dashboard Content ---
st.title("🚴‍♂️ FIT Bestand Analyse Dashboard")
st.markdown("Upload één of meerdere .fit-bestanden om je activiteit(en) te visualiseren.")

if st.session_state.get('fit_df', pd.DataFrame()).empty:
    st.info("Upload een of meerdere .fit-bestanden in de zijbalk om je sportactiviteit(en) te analyseren. Deze app is specifiek voor .fit-bestanden.")
else:
    df = st.session_state.fit_df

    # --- Tabs ---
    # Removed 'Prestaties over Tijd' tab
    tab_map, tab_table, tab_raw_data = st.tabs(["🗺️ Activiteit Route", "📋 Overzicht Tabel", "📋 Ruwe Data"])

    with tab_map:
        st.subheader("Activiteiten Routes op Kaart")
        if 'Latitude' in df.columns and 'Longitude' in df.columns and df['Latitude'].notna().any() and df['Longitude'].notna().any():
            df_map = df.dropna(subset=['Latitude', 'Longitude']).copy()

            if not df_map.empty:
                center_lat = df_map['Latitude'].mean()
                center_lon = df_map['Longitude'].mean()

                fig_map = px.line_mapbox(
                    df_map,
                    lat="Latitude",
                    lon="Longitude",
                    color="Activity_ID",
                    zoom=12,
                    height=700,
                    mapbox_style="open-street-map",
                    title="Afgelegde Routes",
                    hover_name="Activity_ID",
                    hover_data={'DatumTijd': True, 'Afstand_km': ':.2f', 'Hartslag_bpm': True, 'Activity_ID': False}
                )

                # Adjust line width after creating the map
                fig_map.update_traces(line=dict(width=3))


                # Add start and end points for each activity
                for activity_id in df_map['Activity_ID'].unique():
                    activity_df = df_map[df_map['Activity_ID'] == activity_id]
                    if not activity_df.empty:
                        # Startpunkt
                        fig_map.add_trace(go.Scattermapbox(
                            lat=[activity_df['Latitude'].iloc[0]],
                            lon=[activity_df['Longitude'].iloc[0]],
                            mode='markers',
                            marker=go.scattermapbox.Marker(size=10, color='green', symbol='circle'),
                            name=f'Start: {activity_id}',
                            hoverinfo='name',
                            showlegend=False
                        ))
                        # Eindpunkt
                        fig_map.add_trace(go.Scattermapbox(
                            lat=[activity_df['Latitude'].iloc[-1]],
                            lon=[activity_df['Longitude'].iloc[-1]],
                            mode='markers',
                            marker=go.scattermapbox.Marker(size=10, color='red', symbol='circle'),
                            name=f'Eind: {activity_id}',
                            hoverinfo='name',
                            showlegend=False
                        ))

                fig_map.update_layout(mapbox_center={"lat": center_lat, "lon": center_lon})
                st.plotly_chart(fig_map, use_container_width=True, config={'displayModeBar': True})
            else:
                st.info("Geen geldige GPS-coördinaten gevonden in de bestanden om de routes te tonen.")
        else:
            st.info("Geen GPS-coördinaten (Latitude/Longitude) beschikbaar in de geüploade FIT-bestanden om de routes te tonen.")

    with tab_table:
        st.subheader("Overzicht van Alle Activiteiten")

        if not df.empty:
            summary_df = df.groupby('Activity_ID').agg(
                Datum=('DatumTijd', lambda x: x.min().strftime('%Y-%m-%d') if not x.empty else 'N/B'),
                Totale_Afstand_km=('Afstand_km', 'max'),
                Totale_Duur_Timer_Sec=('Totale_Duur_Timer_Sec', 'first'), # Using total_timer_time from session
                Gemiddelde_Hartslag=('Hartslag_bpm', lambda x: x[x > 0].mean() if not x.empty else 0),
                Maximale_Hartslag=('Hartslag_bpm', 'max'),
                Activiteitstype=('Activiteitstype', 'first')
            ).reset_index()

            # Calculate average speed based on total distance and accurate timer duration
            summary_df['Gemiddelde_Snelheid_kmh'] = summary_df.apply(
                lambda row: (row['Totale_Afstand_km'] / (row['Totale_Duur_Timer_Sec'] / 3600)) if row['Totale_Duur_Timer_Sec'] > 0 else 0,
                axis=1
            )

            # Format the total duration
            summary_df['Totale_Duur'] = summary_df['Totale_Duur_Timer_Sec'].apply(format_duration)

            # Round numerical columns and ensure proper display
            summary_df['Totale_Afstand_km'] = summary_df['Totale_Afstand_km'].round(2)
            summary_df['Gemiddelde_Snelheid_kmh'] = summary_df['Gemiddelde_Snelheid_kmh'].round(1)
            summary_df['Gemiddelde_Hartslag'] = summary_df['Gemiddelde_Hartslag'].round(0).astype('Int64')
            summary_df['Maximale_Hartslag'] = summary_df['Maximale_Hartslag'].round(0).astype('Int64')

            # Define and rename columns for display in the table
            display_columns = [
                'Bestandsnaam',
                'Datum',
                'Activiteitstype',
                'Afstand (km)',
                'Duur (UU:MM:SS)',
                'Gem. Snelheid (km/u)',
                'Gem. Hartslag (bpm)',
                'Max. Hartslag (bpm)'
            ]

            summary_df = summary_df.rename(columns={
                'Activity_ID': 'Bestandsnaam',
                'Totale_Afstand_km': 'Afstand (km)',
                'Gemiddelde_Snelheid_kmh': 'Gem. Snelheid (km/u)',
                'Gemiddelde_Hartslag': 'Gem. Hartslag (bpm)',
                'Maximale_Hartslag': 'Max. Hartslag (bpm)',
                'Totale_Duur': 'Duur (UU:MM:SS)'
            })[display_columns].copy()


            st.dataframe(summary_df, use_container_width=True)

            csv_export_summary = summary_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download overzichtstabel als CSV",
                data=csv_export_summary,
                file_name="fit_summary_table.csv",
                mime="text/csv",
            )

        else:
            st.info("Geen activiteiten geladen om een overzichtstabel te tonen.")

    with tab_raw_data:
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
