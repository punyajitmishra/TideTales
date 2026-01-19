import streamlit as st
import pandas as pd
import plotly.express as px
import anthropic
import requests
import time
import numpy as np

# --- 1. APP CONFIGURATION ---
# We set wide mode and a custom theme color
st.set_page_config(
    page_title="Tide Tales", 
    layout="wide", 
    page_icon="🌊",
    initial_sidebar_state="expanded"
)

# --- 2. ACCURATE LOCATION ENGINE ---
@st.cache_data(ttl=3600)
def get_geo_location():
    """Tries multiple IP-based services to find the city accurately."""
    services = [
        'https://ipapi.co/json/',
        'http://ip-api.com/json/',
        'https://ipwho.is/'
    ]
    for service in services:
        try:
            response = requests.get(service, timeout=5).json()
            city = response.get('city')
            country = response.get('country_name') or response.get('country')
            if city:
                return f"{city}, {country}"
        except:
            continue
    return "Bhubaneswar, India" # Robust default

# --- 3. SCIENCE TYPE DETECTOR ---
def detect_science_metadata(column_name, data_series):
    """
    Analyzes column names and data values to determine 
    the science type, units, and cultural metaphors.
    """
    name = str(column_name).lower()
    avg_val = data_series.mean()
    
    # 1. Air Quality (AQI)
    if any(k in name for k in ['aqi', 'air', 'quality', 'pm2', 'pm10']):
        return {
            "unit": "AQI Index",
            "label": "Air Quality Index",
            "metaphor": "The Breath of the City",
            "color": "#FF5733" # Orange/Red
        }
    
    # 2. Temperature
    if any(k in name for k in ['temp', 'anomaly', 'j-d', 'celsius', 'farenheit']):
        return {
            "unit": "°C Anomaly",
            "label": "Temperature Anomaly",
            "metaphor": "The Fever of the Earth",
            "color": "#00D4FF" # Cyan
        }
    
    # 3. Sea Level / Water
    if any(k in name for k in ['sea', 'level', 'tide', 'mm', 'water', 'ocean']):
        return {
            "unit": "mm",
            "label": "Sea Level Rise",
            "metaphor": "The Rising Tides",
            "color": "#2E7D32" # Deep Green
        }
        
    # 4. Carbon / CO2
    if any(k in name for k in ['co2', 'carbon', 'ppm']):
        return {
            "unit": "ppm",
            "label": "Atmospheric CO2",
            "metaphor": "The Heavy Sky",
            "color": "#8E44AD" # Purple
        }

    # Fallback based on typical ranges
    if avg_val > 300: # Likely CO2
        return {"unit": "ppm", "label": "Carbon Levels", "metaphor": "The Ancient Air", "color": "#8E44AD"}
    if avg_val > 50: # Likely AQI
        return {"unit": "Index", "label": "Pollution Levels", "metaphor": "The Hazy Breath", "color": "#FF5733"}
    
    return {"unit": "Units", "label": "Measurement", "metaphor": "The Changing Land", "color": "#FFFFFF"}

# --- 4. DATA INGESTION (NASA + AUTO-CLEAN) ---
@st.cache_data
def fetch_nasa_gistemp():
    """Fetches and cleans NASA GISTEMP v4."""
    url = "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv"
    try:
        df = pd.read_csv(url, skiprows=1, na_values="***")
        if 'Year' in df.columns and 'J-D' in df.columns:
            df_clean = df[['Year', 'J-D']].copy()
            df_clean.columns = ['year', 'anomaly']
            df_clean = df_clean.apply(pd.to_numeric, errors='coerce').dropna()
            return df_clean
    except Exception as e:
        st.error(f"NASA Site Connection Failed: {e}")
    # Fallback fake data if NASA is offline
    return pd.DataFrame({'year': range(1900, 2025), 'anomaly': np.linspace(-0.3, 1.2, 125)})

# --- 5. THE AI COLUMN SNIFFER (Real AI + Heuristic Fallback) ---
def ai_sniff_columns(df, api_key=None):
    """Detects Time and Data columns using AI or Keywords."""
    cols = df.columns.tolist()
    
    # 1. Try Real AI if key exists
    if api_key:
        try:
            client = anthropic.Anthropic(api_key=api_key)
            sample = df.head(5).to_string()
            prompt = f"Analyze these CSV headers: {cols}. Data sample: {sample}. Return ONLY -> Year: [col_name], Data: [col_name]"
            response = client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )
            result = response.content[0].text
            y_col = result.split("Year:")[1].split("\n")[0].strip()
            d_col = result.split("Data:")[1].split("\n")[0].strip()
            return y_col, d_col
        except:
            pass # Fallback to Heuristic if AI fails

    # 2. Heuristic Logic (Fake AI)
    y_col = next((c for c in cols if any(k in str(c).lower() for k in ['year', 'yr', 'date', 'time', 'period'])), None)
    
    # For Data, look for keywords or the first numeric column that isn't Year
    d_keywords = ['temp', 'anom', 'val', 'j-d', 'annual', 'index', 'aqi', 'ppm']
    d_col = next((c for c in cols if any(k in str(c).lower() for k in d_keywords) and c != y_col), None)
    
    if not y_col: y_col = cols[0]
    if not d_col: 
        others = [c for c in cols if c != y_col]
        d_col = others[0] if others else cols[0]
        
    return y_col, d_col

# --- 6. SIDEBAR SETUP ---
with st.sidebar:
    st.title("🌊 Tide Tales Settings")
    st.divider()
    
    # API KEY
    api_key = st.text_input("Anthropic API Key", type="password", key="side_key")
    
    # LOCATION (Manual Override Fix)
    detected_loc = get_geo_location()
    st.write(f"Detected: **{detected_loc}**")
    final_location = st.text_input("📍 Confirm Your Location", value=detected_loc, key="side_loc")
    
    st.divider()
    
    # DATA SOURCE
    data_source = st.radio("Data Source", ["NASA Official GISTEMP", "Manual CSV Upload"], key="side_src")
    
    uploaded_file = None
    if data_source == "Manual CSV Upload":
        uploaded_file = st.file_uploader("Upload CSV File", type="csv", key="side_file")
    
    demo_mode = st.toggle("Enable Demo Narrative Mode", value=True, key="side_demo")

# --- 7. DATA PROCESSING & SESSION STATE ---
# We use session state to keep data alive across widget clicks
if 'active_df' not in st.session_state:
    st.session_state['active_df'] = fetch_nasa_gistemp()

if data_source == "Manual CSV Upload" and uploaded_file:
    # Logic to handle NASA-style files with headers in Row 1
    try:
        # Check if we need to skip a row
        peek = pd.read_csv(uploaded_file, nrows=2)
        uploaded_file.seek(0)
        
        if "Land-Ocean" in str(peek.columns[0]):
            raw_df = pd.read_csv(uploaded_file, skiprows=1, na_values="***")
        else:
            raw_df = pd.read_csv(uploaded_file, na_values="***")
        
        if st.button("🔍 Analyze Data Structure", key="side_analyze"):
            with st.spinner("AI is sniffing the columns..."):
                y_name, d_name = ai_sniff_columns(raw_df, api_key)
                
                if y_name in raw_df.columns and d_name in raw_df.columns:
                    st.success(f"Mapping: {y_name} (Time) & {d_name} (Data)")
                    # Standardize
                    processed = raw_df[[y_name, d_name]].copy()
                    processed.columns = ['year', 'anomaly']
                    processed['year'] = pd.to_numeric(processed['year'], errors='coerce')
                    processed['anomaly'] = pd.to_numeric(processed['anomaly'], errors='coerce')
                    st.session_state['active_df'] = processed.dropna()
                else:
                    st.error("Could not find matching columns. Check CSV headers.")
    except Exception as e:
        st.error(f"Load Error: {e}")

elif data_source == "NASA Official GISTEMP":
    st.session_state['active_df'] = fetch_nasa_gistemp()

# Assign working dataframe
working_data = st.session_state['active_df'].copy()

# --- 8. MAIN DASHBOARD ---
st.title("🌊 Tide Tales")

# Time Slider (Ensuring Int values to prevent 0-1 bug)
min_year = int(working_data['year'].min())
max_year = int(working_data['year'].max())
if min_year >= max_year: max_year = min_year + 1

selected_range = st.slider(
    "Select Analysis Timeframe", 
    min_year, max_year, (min_year, max_year), 
    key="main_slider"
)

# Filter Data
filtered_df = working_data[(working_data['year'] >= selected_range[0]) & (working_data['year'] <= selected_range[1])]

if not filtered_df.empty:
    # MATH: THE FACT PACK (Week 3 Objective)
    val_start = filtered_df['anomaly'].iloc[0]
    val_end = filtered_df['anomaly'].iloc[-1]
    net_shift = val_end - val_start
    peak = filtered_df['anomaly'].max()
    trough = filtered_df['anomaly'].min()
    
    # Slope (Trendline)
    slope, intercept = np.polyfit(filtered_df['year'], filtered_df['anomaly'], 1)
    
    # Detect Metadata (Science Type)
    # We pass the anomaly column to detect what we are looking at
    sci = detect_science_metadata("anomaly", filtered_df['anomaly'])

    # EVIDENCE PANEL (Interactive Plotly)
    st.header(f"📊 Evidence Panel: {sci['label']}")
    st.write(f"Observing scientific trends in **{final_location}**.")
    
    fig = px.line(
        filtered_df, x='year', y='anomaly', 
        title=f"{sci['label']} Trend ({selected_range[0]} - {selected_range[1]})",
        template="plotly_dark",
        labels={'year': 'Year', 'anomaly': sci['unit']}
    )
    # Add Trendline
    fig.add_scatter(
        x=filtered_df['year'], 
        y=slope*filtered_df['year'] + intercept, 
        name="Mathematical Trend", 
        line=dict(color='red', dash='dot')
    )
    fig.update_traces(line_color=sci['color'], line_width=3)
    st.plotly_chart(fig, use_container_width=True)

    # THE FACT PACK METRICS
    st.subheader(f"📋 {sci['label']} Metrics")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Net Shift", f"{round(net_shift, 2)} {sci['unit']}")
    m2.metric("Warming Rate", f"{round(slope, 3)} / yr")
    m3.metric("Peak Record", f"{round(peak, 2)}")
    m4.metric("Trough Record", f"{round(trough, 2)}")

    # THE NARRATIVE GENERATOR
    st.divider()
    st.header(f"📖 The Story of {sci['metaphor']}")
    
    if st.button("✨ Weave the Narrative", key="main_weave"):
        if api_key and not demo_mode:
            st.info("AI Mode: Engaging Claude 3.5 Sonnet...")
            # (Real AI Logic will be finalized in Week 4)
        else:
            # ROBUST DEMO NARRATIVE (Multi-Chapter Structure)
            st.toast("Generating Demo Story Structure...")
            
            # This is the Week 3 Deliverable: A structured story using the Fact Pack
            chapters = [
                f"### Chapter 1: The Omens\nIn the ancient memory of **{final_location}**, the land spoke a language of balance. But between {selected_range[0]} and {selected_range[1]}, a new dialect has emerged. The data reveals a net shift of **{round(net_shift, 2)} {sci['unit']}**, a change that is felt in the drying of the wells and the heat of the noon-day sun.",
                f"### Chapter 2: The Rising Fever\nScientific observation confirms that this is not a random flicker. The trendline, sharp as a hunter's arrow, moves at a rate of **{round(slope, 3)} units per year**. In the year of the peak, which reached **{round(peak, 2)}**, the story of {final_location} changed forever.",
                f"### Chapter 3: The Cultural Lens\nFolklore tells us of spirits that once guarded our tides, but even they now navigate a world dictated by **{sci['label']}**. What was once a mystery is now a measurement. The trough of **{round(trough, 2)}** is a ghost of a cooler past, a reminder of the world our ancestors once knew.",
                f"### Chapter 4: The Path Forward\nAs we close the records on this timeframe, the measurement stands at **{round(val_end, 2)}**. The narrative is no longer just about numbers on a chart; it is about how the people of {final_location} will translate this scientific truth into the songs of their survival."
            ]
            
            # Display chapters with a slight delay for "typing" effect
            for chap in chapters:
                st.markdown(chap)
                time.sleep(0.4)
            
            st.balloons()
else:
    st.error("Adjust the slider to find valid data points.")
