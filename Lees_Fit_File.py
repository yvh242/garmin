import streamlit as st
import pandas as pd
import plotly.express as px
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

@st.cache_data(show_spinner="FIT bestand inlezen en verwerken...")
def parse_fit_file(file_bytes):
    """
    Parses a .fit file from bytes and extracts relevant activity data.
    Returns a DataFrame with key metrics.
    """
    try:
        # Create a FitFile object from the bytes
        fit_file = FitFile(file_bytes)

        records_data = []
        for record in fit_file.get_messages('record'):
            record_dict = record.as_dict()
            data = {}
            for field in record.fields:
                data[field.name] = field.value
            records_data.append(data)

        df = pd.DataFrame(records_data)

        # Rename common columns to a standardized format
        column_renames = {
            'timestamp': 'DatumTijd',
            'position_lat': 'Latitude',
            'position_long': 'Longitude',
            'distance': 'Afstand_m',
            'heart_rate': 'Hartslag_bpm',
            'cadence': 'Cadans_rpm', # or spm for running
            'speed': 'Snelheid_ms', # meters/second
            'altitude': 'Hoogte_m',
            'power': 'Vermogen_watts',
            'calories': 'Calorieën'
        }
        df.rename(columns=column_renames, inplace=True)

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

        # Extract activity type from file metadata if possible (often not in 'record' messages)
        # This part is often more complex as activity type might be in 'session' or 'activity' messages
        # For simplicity, we'll try to infer or set to unknown
        activity_type = "Onbekend"
        for session in fit_file.get_messages('session'):
            session_dict = session.as_dict()
            if 'sport' in session_dict and session_dict['sport'] is not None:
                activity_type = str(session_dict['sport']).replace('_', ' ').title()
                break # Take the first found sport type

        df['Activiteitstype'] = activity_type

        return df

    except Exception as e:
        st.error(f"Fout bij het parsen van het FIT-bestand: {e}")
        return pd.DataFrame()

# --- Zijbalk voor bestand uploaden ---
with st.sidebar:
    st.header("Upload je FIT-bestand")
    st.markdown("Upload hier een .fit bestand van je sportactiviteit.")

    uploaded_fit_file = st.file_uploader("Kies een .fit bestand", type=["fit"])

    if uploaded_fit_file is not None:
        st.session_state.fit_df = parse_fit_file(uploaded_fit_file.read())
        if not st.session_state.fit_df.empty:
            st.success(f"FIT bestand '{uploaded_fit_file.name}' succesvol ingelezen!")
            st.info(f"Activiteitstype gedetecteerd: **{st.session_state.fit_df['Activiteitstype'].iloc[0]}**")
        else:
            st.warning("Geen bruikbare data gevonden in het FIT-bestand.")
            st.session_state.fit_df = pd.DataFrame() # Ensure it's empty on failure
    else:
        st.session_state.fit_df = pd.DataFrame() # Reset if no file uploaded

# --- Hoofd Dashboard Content ---
st.title("🚴‍♂️ FIT Bestand Analyse Dashboard")
st.markdown("Upload een .fit-bestand om je activiteit te visualiseren.")

if st.session_state.get('fit_df', pd.DataFrame()).empty:
    st.info("Upload een .fit-bestand in de zijbalk om je sportactiviteit te analyseren. Deze app is specifiek voor .fit-bestanden.")
else:
    df = st.session_state.fit_df

    # --- Algemene KPI's ---
    st.subheader("Overzicht van de Activiteit")

    total_distance_km = df['Afstand_km'].max() if 'Afstand_km' in df.columns else 0
    total_duration_seconds = df['Tijd_sec'].max() if 'Tijd_sec' in df.columns else 0
    max_heart_rate = df['Hartslag_bpm'].max() if 'Hartslag_bpm' in df.columns else 0
    avg_heart_rate = df['Hartslag_bpm'][df['Hartslag_bpm'] > 0].mean() if 'Hartslag_bpm' in df.columns else 0
    max_speed_kmh = df['Snelheid_kmh'].max() if 'Snelheid_kmh' in df.columns else 0
    total_calories = df['Calorieën'].max() if 'Calorieën' in df.columns else 0
    total_elevation_gain = df['Hoogte_m'].diff().apply(lambda x: max(0, x)).sum() if 'Hoogte_m' in df.columns else 0

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
        st.metric(label="Totale afstand", value=f"{total_distance_km:,.2f} km")
    with kpi2:
        st.metric(label="Totale duur", value=format_duration(total_duration_seconds))
    with kpi3:
        st.metric(label="Gem. Hartslag", value=f"{avg_heart_rate:,.0f} bpm" if avg_heart_rate > 0 else "N/B")
    with kpi4:
        st.metric(label="Max. Snelheid", value=f"{max_speed_kmh:,.1f} km/u" if max_speed_kmh > 0 else "N/B")

    kpi5, kpi6, kpi7 = st.columns(3)
    with kpi5:
        st.metric(label="Totaal Calorieën", value=f"{total_calories:,.0f} kcal" if total_calories > 0 else "N/B")
    with kpi6:
        st.metric(label="Max. Hartslag", value=f"{max_heart_rate:,.0f} bpm" if max_heart_rate > 0 else "N/B")
    with kpi7:
        st.metric(label="Totale Stijging", value=f"{total_elevation_gain:,.0f} m" if total_elevation_gain > 0 else "N/B")

    st.markdown("---")

    # --- Tijdreeks Grafieken ---
    st.subheader("Prestaties over Tijd")

    # Selectiebox voor de y-as
    available_metrics = {
        "Hartslag (bpm)": "Hartslag_bpm",
        "Snelheid (km/u)": "Snelheid_kmh",
        "Hoogte (m)": "Hoogte_m",
        "Cadans (rpm/spm)": "Cadans_rpm",
        "Vermogen (watts)": "Vermogen_watts",
        "Afstand (km)": "Afstand_km"
    }

    # Filter out metrics that are not in the DataFrame or are all zeros
    plottable_metrics = {
        label: col for label, col in available_metrics.items()
        if col in df.columns and (df[col].sum() > 0 or col in ['Hoogte_m', 'Afstand_km'])
    }

    if not plottable_metrics:
        st.warning("Niet genoeg numerieke data om grafieken te genereren.")
    else:
        selected_metric = st.selectbox(
            "Selecteer een meting om te visualiseren:",
            options=list(plottable_metrics.keys()),
            key="metric_selection"
        )

        y_column = plottable_metrics[selected_metric]

        if 'DatumTijd' in df.columns and not df.empty and not df['DatumTijd'].empty:
            fig = px.line(
                df,
                x='DatumTijd',
                y=y_column,
                title=f'{selected_metric} over Tijd',
                labels={'DatumTijd': 'Tijd', y_column: selected_metric},
                template="plotly_dark",
                line_shape='spline' # Maakt de lijnen vloeiender
            )
            fig.update_xaxes(rangeslider_visible=True, rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1m", step="minute", stepmode="backward"),
                    dict(count=5, label="5m", step="minute", stepmode="backward"),
                    dict(count=1, label="1u", step="hour", stepmode="backward"),
                    dict(step="all")
                ])
            ))
            fig.update_layout(hovermode="x unified") # Toon alle waarden op de x-as bij hover
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("Kan geen tijdreeksgrafieken genereren, 'DatumTijd' kolom ontbreekt of is leeg na verwerking.")

    st.markdown("---")

    # --- Gegevens voorbeelden ---
    st.subheader("Ruwe Data Voorbeeld")
    st.markdown("Bekijk de eerste rijen van de verwerkte data.")
    st.dataframe(df.head())

    # --- Download Knop ---
    csv_export = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download verwerkte data als CSV",
        data=csv_export,
        file_name="fit_data_processed.csv",
        mime="text/csv",
    )
