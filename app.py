import streamlit as st
import pandas as pd
import plotly.express as px
import anthropic
import requests
import time
import numpy as np
import random

# --- 1. APP CONFIGURATION ---
st.set_page_config(
    page_title="Tide Tales", 
    layout="wide", 
    page_icon="🌊",
    initial_sidebar_state="expanded"
)

# --- 2. PERSISTENT LOCATION ENGINE ---
if 'user_location' not in st.session_state:
    try:
        # Try a high-accuracy service first
        res = requests.get('https://ipapi.co/json/', timeout=5).json()
        city = res.get('city', 'Bhubaneswar')
        country = res.get('country_name', 'India')
        st.session_state['user_location'] = f"{city}, {country}"
    except:
        st.session_state['user_location'] = "Bhubaneswar, India"

# --- 3. SCIENCE METADATA DETECTOR ---
def detect_science_metadata(column_name, data_series):
    """Detects what we are measuring to set units, colors, and metaphors."""
    name = str(column_name).lower()
    avg_val = data_series.mean()
    
    # Air Quality
    if any(k in name for k in ['aqi', 'air', 'quality', 'pm2', 'pm10']):
        return {
            "unit": "AQI Index",
            "label": "Air Quality Index",
            "metaphor": "the choking haze",
            "element": "Breath",
            "color": "#FF5733"
        }
    # Temperature
    if any(k in name for k in ['temp', 'anomaly', 'j-d', 'celsius', 'farenheit']):
        return {
            "unit": "°C Anomaly",
            "label": "Temperature Anomaly",
            "metaphor": "the earth's fever",
            "element": "Fire",
            "color": "#00D4FF"
        }
    # Sea Level
    if any(k in name for k in ['sea', 'level', 'tide', 'mm', 'water', 'ocean']):
        return {
            "unit": "mm",
            "label": "Sea Level Rise",
            "metaphor": "the hungry ocean",
            "element": "Water",
            "color": "#2E7D32"
        }
    # Carbon
    if any(k in name for k in ['co2', 'carbon', 'ppm']):
        return {
            "unit": "ppm",
            "label": "Atmospheric CO2",
            "metaphor": "the heavy sky",
            "element": "Weight",
            "color": "#8E44AD"
        }
    
    return {"unit": "Units", "label": "Measurement", "metaphor": "the changing pulse", "element": "Change", "color": "#FFFFFF"}

# --- 4. DATA LOADERS ---
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
    return pd.DataFrame({'year': range(1900, 2025), 'anomaly': np.linspace(-0.3, 1.2, 125)})

def ai_sniff_columns(df, api_key=None):
    """Detects Time and Data columns using AI or Keywords."""
    cols = df.columns.tolist()
    if api_key:
        try:
            client = anthropic.Anthropic(api_key=api_key)
            sample = df.head(5).to_string()
            prompt = f"Analyze these CSV headers: {cols}. Sample: {sample}. Return ONLY -> Year: [col], Data: [col]"
            resp = client.messages.create(model="claude-3-5-sonnet-20240620", max_tokens=100, messages=[{"role": "user", "content": prompt}])
            res = resp.content[0].text
            y = res.split("Year:")[1].split("\n")[0].strip()
            d = res.split("Data:")[1].split("\n")[0].strip()
            return y, d
        except: pass

    # Heuristic Logic (Fallback)
    y_col = next((c for c in cols if any(k in str(c).lower() for k in ['year', 'yr', 'date', 'time', 'period'])), cols[0])
    d_keywords = ['temp', 'anom', 'val', 'j-d', 'annual', 'index', 'aqi', 'ppm']
    d_col = next((c for c in cols if any(k in str(c).lower() for k in d_keywords) and c != y_col), cols[1] if len(cols)>1 else cols[0])
    return y_col, d_col

# --- 5. SIDEBAR SETUP ---
with st.sidebar:
    st.title("🌊 Tide Tales Settings")
    st.divider()
    
    api_key = st.text_input("Anthropic API Key", type="password", key="side_api_key")
    
    # Sticky Location Update
    st.session_state['user_location'] = st.text_input(
        "📍 Confirm Your Location", 
        value=st.session_state['user_location'], 
        key="side_loc_field"
    )
    
    st.divider()
    source_choice = st.radio("Select Data Source", ["NASA GISTEMP (Global)", "Upload My Own CSV"], key="side_src")
    
    user_file = None
    if source_choice == "Upload My Own CSV":
        user_file = st.file_uploader("Upload CSV", type="csv", key="side_uploader")
    
    demo_mode = st.toggle("Enable Demo Narrative Mode", value=True, key="side_demo_toggle")

# --- 6. DATA PROCESSING ---
if 'active_df' not in st.session_state:
    st.session_state['active_df'] = fetch_nasa_gistemp()

if source_choice == "Upload My Own CSV" and user_file:
    try:
        peek = pd.read_csv(user_file, nrows=2)
        user_file.seek(0)
        skip = 1 if "Land-Ocean" in str(peek.columns[0]) else 0
        raw_df = pd.read_csv(user_file, skiprows=skip, na_values="***")
        
        if st.button("🔍 Analyze Structure", key="side_analyze_btn"):
            with st.spinner("AI is sniffing the columns..."):
                y_name, d_name = ai_sniff_columns(raw_df, api_key)
                if y_name in raw_df.columns and d_name in raw_df.columns:
                    st.success(f"Mapping: {y_name} & {d_name}")
                    processed = raw_df[[y_name, d_name]].copy()
                    processed.columns = ['year', 'anomaly']
                    processed['year'] = pd.to_numeric(processed['year'], errors='coerce')
                    processed['anomaly'] = pd.to_numeric(processed['anomaly'], errors='coerce')
                    st.session_state['active_df'] = processed.dropna()
    except Exception as e:
        st.error(f"Load Error: {e}")
elif source_choice == "NASA GISTEMP (Global)":
    st.session_state['active_df'] = fetch_nasa_gistemp()

data = st.session_state['active_df'].copy()

# --- 7. MAIN DASHBOARD ---
st.title("🌊 Tide Tales")

# Time Slider
min_year, max_year = int(data['year'].min()), int(data['year'].max())
if min_year >= max_year: max_year = min_year + 1
selected_range = st.slider("Select Analysis Timeframe", min_year, max_year, (min_year, max_year), key="main_year_slider")

# Filter Data
filtered_df = data[(data['year'] >= selected_range[0]) & (data['year'] <= selected_range[1])]

if not filtered_df.empty:
    # --- MATH (FACT PACK) ---
    val_start, val_end = filtered_df['anomaly'].iloc[0], filtered_df['anomaly'].iloc[-1]
    net_shift = val_end - val_start
    peak, trough = filtered_df['anomaly'].max(), filtered_df['anomaly'].min()
    slope, intercept = np.polyfit(filtered_df['year'].values, filtered_df['anomaly'].values, 1)
    
    # Get Metadata
    sci = detect_science_metadata("anomaly", filtered_df['anomaly'])

    # EVIDENCE PANEL
    st.header(f"📊 Evidence: {sci['label']}")
    fig = px.line(filtered_df, x='year', y='anomaly', template="plotly_dark", 
                  title=f"The Scientific Truth in {st.session_state['user_location']}")
    fig.add_scatter(x=filtered_df['year'], y=slope*filtered_df['year'] + intercept, name="Trend", line=dict(color='red', dash='dot'))
    fig.update_traces(line_color=sci['color'], line_width=3)
    st.plotly_chart(fig, use_container_width=True)

    # METRICS
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Net Shift", f"{round(net_shift, 2)} {sci['unit']}")
    m2.metric("Trend Rate", f"{round(slope, 3)} / yr")
    m3.metric("Peak Record", f"{round(peak, 2)}")
    m4.metric("Lowest Point", f"{round(trough, 2)}")

    # --- 8. PROCEDURAL NARRATIVE ENGINE ---
    st.divider()
    st.header(f"📖 The Tale of {st.session_state['user_location']}")
    
    if st.button("✨ Weave Narrative", key="main_weave_button"):
        # If API Key is present AND Demo Mode is OFF, run the real Claude
        if api_key and not demo_mode:
            with st.spinner("Claude is researching folklore and weaving your 1,500-word epic..."):
                try:
                    client = anthropic.Anthropic(api_key=api_key)
                    
                    # Construct the prompt using our Week 3 Fact Pack
                    # 1. ENHANCED SYSTEM PROMPT
                    prompt = f"""
                    You are a world-class literary novelist and environmental researcher. 
                    Your goal is to translate scientific data into a 1,500-word cultural epic for the people of {st.session_state['user_location']}.

                    THE DATA (Immutable Truth):
                    - Science: {sci['label']}
                    - Observation Period: {selected_range[0]} to {selected_range[1]}
                    - Net Change: {round(net_shift, 2)} {sci['unit']}
                    - Warming Rate: {round(slope, 3)} units per year
                    - Max/Min: {round(peak, 2)} / {round(trough, 2)}

                    STORY REQUIREMENTS:
                    1. STYLE: Use the folklore, rhythmic structures (like oral legends or Panchali), and local metaphors of {st.session_state['user_location']}.
                    2. WIGGLE ROOM: Do not just list numbers. Use them to describe the environment. If the rate is {round(slope, 3)}, describe it as a 'creeping fever' or 'restless tide'.
                    3. STRUCTURE: Write 5 long chapters.
                    4. BILINGUAL: Write the full 1,500-word story in English, followed by the full story in the local vernacular of {st.session_state['user_location']}.
                    
                    FORMAT: Use [ENGLISH] at the start of the English section and [LOCAL] at the start of the local language section.
                    """

                    col_eng, col_loc = st.columns(2)
                    with col_eng:
                        st.subheader("🌍 English Epic")
                        eng_p = st.empty()
                    with col_loc:
                        st.subheader(f"🗣️ Local Voice")
                        loc_p = st.empty()

                    full_resp = ""
                    with client.messages.stream(
                        model="claude-3-5-sonnet-20240620",
                        max_tokens=8192,
                        messages=[{"role": "user", "content": prompt}],
                    ) as stream:
                        for text in stream.text_stream:
                            full_resp += text
                            if "[LOCAL]" in full_resp:
                                parts = full_resp.split("[LOCAL]")
                                eng_text = parts[0].replace("[ENGLISH]", "").strip()
                                loc_text = parts[1].strip()
                                eng_p.markdown(eng_text)
                                loc_p.markdown(loc_text + " ▌")
                            else:
                                eng_text = full_resp.replace("[ENGLISH]", "").strip()
                                eng_p.markdown(eng_text + " ▌")
                    
                    # SAVE TO SESSION STATE FOR DOWNLOAD
                    st.session_state['last_story'] = full_resp
                    st.balloons()
