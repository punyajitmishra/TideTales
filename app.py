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
        if api_key and not demo_mode:
            st.info("AI Mode: Engaging Claude for a unique 1500-word epic...")
        else:
            # Wiggle Room Descriptors
            intensity = "a frantic gallop" if slope > 0.015 else "a steady, relentless climb" if slope > 0.005 else "a subtle, whispering shift"
            impact = "the world has broken its ancient promises" if abs(net_shift) > 1.0 else "the balance is beginning to fray at the edges"
            loc = st.session_state['user_location']

            # Procedural Variations
            ch1_opts = [
                f"In the ancient memory of **{loc}**, the wind once spoke a language of predictable seasons. But since **{selected_range[0]}**, a new dialect has emerged—one written in the language of {sci['metaphor']}.",
                f"The soil of **{loc}** has its own way of keeping time. Long before we had the records starting in **{selected_range[0]}**, the ancestors knew the rhythm of the {sci['element']}. Now, that rhythm has faltered.",
                f"If you stand on the highest hill in **{loc}**, you might not see the change, but the data does. From the moment we began tracking in **{selected_range[0]}**, the {sci['label']} has been a silent witness to a transformation."
            ]
            ch2_opts = [
                f"Science confirms what our hearts already suspected. This is no random flicker of a dying candle. Our trendline moves at **{intensity}**—a rate of **{round(slope, 3)} units per year**. In the year we touched the peak of **{round(peak, 2)}**, the very stones seemed to weep.",
                f"The math does not lie, even when it is hard to hear. Moving at **{round(slope, 3)} per year**, the {sci['element']} is undergoing **{intensity}**. When the record hit **{round(peak, 2)}**, it wasn't just a number; it was a fever that {loc} had never known."
            ]
            ch3_opts = [
                f"There is a legend in **{loc}** about a mirror that reflects the health of the earth. Today, that mirror is clouded. The trough of **{round(trough, 2)}** is a ghost—a remnant of a cooler past that is receding into the fog of history.",
                f"The measurement stands today at **{round(val_end, 2)}**, far from the stability of the past. The trough of **{round(trough, 2)}** is a milestone we are leaving behind as the {sci['metaphor']} takes hold."
            ]

            story_chapters = [
                f"### Chapter 1: The Omens\n{random.choice(ch1_opts)} The data reveals a shift of **{round(net_shift, 2)} {sci['unit']}**, but to the people here, it is more than that. It is {impact}.",
                f"### Chapter 2: The Quickening Fever\n{random.choice(ch2_opts)} This is no longer a fluctuation; it is a transformation of our physical reality, documented by NASA, but lived by every soul in {loc}.",
                f"### Chapter 3: The Ghost in the Mirror\n{random.choice(ch3_opts)} We realize the balance has shifted. The 'Wiggle Room' between the data and our lives is where the fear lives—and where the hope must grow.",
                f"### Chapter 4: The Convergence\nAs we stand at the end of this record in **{selected_range[1]}**, the narrative of the {sci['metaphor']} is an epic still being written. In **{loc}**, the convergence of scientific data and local song is our only map home."
            ]
            
            for chap in story_chapters:
                st.markdown(chap)
                time.sleep(0.7)
            st.balloons()
else:
    st.error("Adjust the slider to find valid data points.")
