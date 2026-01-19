import streamlit as st
import pandas as pd
import plotly.express as px
import anthropic
import requests
import time
import numpy as np

# --- 1. SETUP ---
st.set_page_config(page_title="Tide Tales", layout="wide", page_icon="🌊")

# --- 2. ACCURATE LOCATION DETECTION ---
@st.cache_data(ttl=3600)
def detect_location():
    try:
        # Using ipapi.co which is generally more accurate for Indian cities
        response = requests.get('https://ipapi.co/json/').json()
        city = response.get('city', 'Bhubaneswar')
        country = response.get('country_name', 'India')
        return f"{city}, {country}"
    except:
        return "Bhubaneswar, India"

# --- 3. DATA LOADERS ---
@st.cache_data
def load_nasa_gistemp():
    url = "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv"
    try:
        df = pd.read_csv(url, skiprows=1, na_values="***")
        df_clean = df[['Year', 'J-D']].copy()
        df_clean.columns = ['year', 'anomaly']
        df_clean = df_clean.apply(pd.to_numeric, errors='coerce').dropna()
        return df_clean
    except:
        # Fail-safe data so the app never crashes
        return pd.DataFrame({'year': [2000, 2021], 'anomaly': [0.4, 0.85]})

def ai_detect_columns(df, api_key):
    """Real AI logic with Heuristic Fallback for Demo Mode."""
    if not api_key:
        # --- FAKE AI / HEURISTIC FALLBACK ---
        cols = df.columns.tolist()
        y_col = next((c for c in cols if 'year' in str(c).lower() or 'yr' in str(c).lower()), cols[0])
        d_col = next((c for c in cols if any(k in str(c).lower() for k in ['j-d', 'temp', 'anom', 'val']) and c != y_col), cols[1])
        return y_col, d_col

    # --- REAL CLAUDE LOGIC ---
    client = anthropic.Anthropic(api_key=api_key)
    sample_data = df.head(5).to_string()
    prompt = f"Identify 'Year' and 'Data' columns from this sample: {sample_data}. Return format -> Year: [name], Data: [name]"
    
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )
        answer = response.content[0].text
        y = answer.split("Year:")[1].split("\n")[0].strip()
        d = answer.split("Data:")[1].split("\n")[0].strip()
        return y, d
    except:
        return df.columns[0], df.columns[1]

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🌊 Tide Tales Settings")
    api_key = st.text_input("Anthropic API Key", type="password", key="api_key_sidebar")
    
    # Accurate Location with Manual Fix
    detected_loc = detect_location()
    loc = st.text_input("📍 Your Location (detected)", value=detected_loc, key="location_input")
    st.caption("If the detection is wrong (e.g. shows Kolkata instead of Bhubaneswar), please type it manually above.")

    st.divider()
    data_source = st.radio("Select Data Source", ["NASA GISTEMP (Auto)", "Upload My Own CSV"], key="source_selector")
    
    uploaded_file = None
    if data_source == "Upload My Own CSV":
        uploaded_file = st.file_uploader("Upload CSV", type="csv", key="file_drop")
    
    demo_mode = st.toggle("Enable Demo Mode", value=True, key="demo_toggle")

# --- 5. DATA FLOW MANAGEMENT ---
# Initialize session state so data persists between slider moves
if 'active_df' not in st.session_state:
    st.session_state['active_df'] = load_nasa_gistemp()

if data_source == "Upload My Own CSV" and uploaded_file:
    raw_data = pd.read_csv(uploaded_file, na_values="***")
    if st.button("🔍 Analyze & Map Data", key="analyze_btn"):
        with st.spinner("AI is analyzing dataset structure..."):
            # This works even without a key now!
            y_col, d_col = ai_detect_columns(raw_data, api_key)
            
            if y_col in raw_data.columns and d_col in raw_data.columns:
                processed = raw_data[[y_col, d_col]].copy()
                processed.columns = ['year', 'anomaly']
                processed = processed.apply(pd.to_numeric, errors='coerce').dropna()
                st.session_state['active_df'] = processed
                st.success(f"✅ Mapped: Time='{y_col}', Data='{d_col}'")
            else:
                st.error("Failed to map columns.")
elif data_source == "NASA GISTEMP (Auto)":
    st.session_state['active_df'] = load_nasa_gistemp()

# Use the data stored in session state
data = st.session_state['active_df']

# --- 6. WEEK 3: UI & COMPUTATIONS ---
st.title("🌊 Tide Tales")

# Ensure valid range for slider
min_yr, max_yr = int(data['year'].min()), int(data['year'].max())
if min_yr >= max_yr: max_yr = min_yr + 1

selected_range = st.slider("Select Time Range", min_yr, max_yr, (min_yr, max_yr), key="time_slider")

# Filter data
filtered = data[(data['year'] >= selected_range[0]) & (data['year'] <= selected_range[1])]

if not filtered.empty:
    # COMPUTE THE FACT PACK
    start_v = filtered['anomaly'].iloc[0]
    end_v = filtered['anomaly'].iloc[-1]
    net_change = end_v - start_v
    max_v = filtered['anomaly'].max()
    min_v = filtered['anomaly'].min()
    
    # Compute Trend (Polyfit)
    slope, intercept = np.polyfit(filtered['year'], filtered['anomaly'], 1)

    # EVIDENCE PANEL
    st.header("📊 Evidence Panel")
    fig = px.line(filtered, x='year', y='anomaly', 
                  title=f"Trend: {selected_range[0]} - {selected_range[1]}",
                  template="plotly_dark")
    fig.add_scatter(x=filtered['year'], y=slope*filtered['year'] + intercept, 
                    name="Trendline", line=dict(color='red', dash='dot'))
    st.plotly_chart(fig, use_container_width=True)

    # FACT PACK DISPLAY
    st.subheader("📋 The Fact Pack")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Net Change", f"{round(net_change, 2)}°C")
    c2.metric("Peak Anomaly", f"{round(max_v, 2)}°C")
    c3.metric("Trough Anomaly", f"{round(min_v, 2)}°C")
    c4.metric("Rate of Change", f"{round(slope, 3)}°C/yr")

    # TEMPLATE STORY
    st.divider()
    st.header("📖 The Narrative")
    
    if st.button("✨ Generate Story", key="story_btn"):
        template_story = f"""
        In the land of {loc}, between {selected_range[0]} and {selected_range[1]}, 
        the climate records show a total shift of {round(net_change, 2)} degrees. 
        
        The highest fever recorded was {round(max_v, 2)}°C. Currently, 
        the heat is moving at a rate of {round(slope, 3)} degrees every year.
        """
        
        if api_key and not demo_mode:
            st.info("AI Narrative Generation (Week 4 Focus)...")
        else:
            st.info("Generating Template Story from Calculated Stats")
            st.write(template_story)
            st.balloons()
else:
    st.error("No data found for the selected range.")
