import streamlit as st
import pandas as pd
import plotly.express as px
import anthropic
import requests
import time
import numpy as np

# --- 1. APP CONFIGURATION ---
st.set_page_config(
    page_title="Tide Tales", 
    layout="wide", 
    page_icon="🌊",
    initial_sidebar_state="expanded"
)

# --- 2. THE LOCATION ENGINE (Accurate Detection) ---
@st.cache_data(ttl=3600)
def get_accurate_location():
    """Tries multiple services to find the user's city."""
    # Try Service 1: ipapi.co (Generally good for India)
    try:
        data = requests.get('https://ipapi.co/json/', timeout=5).json()
        if data.get('city'):
            return f"{data.get('city')}, {data.get('country_name')}"
    except:
        pass

    # Try Service 2: ip-api.com (Fallback)
    try:
        data = requests.get('http://ip-api.com/json/', timeout=5).json()
        if data.get('city'):
            return f"{data.get('city')}, {data.get('country')}"
    except:
        pass
    
    return "Bhubaneswar, India" # Default if all else fails

# --- 3. THE DATA LOADING ENGINE ---
@st.cache_data
def fetch_nasa_data():
    """Fetches and cleans the official NASA GISTEMP dataset."""
    url = "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv"
    try:
        # NASA CSVs start with a title row, so we skip it
        df = pd.read_csv(url, skiprows=1, na_values="***")
        # J-D is the standard NASA column for Annual Mean Anomaly
        if 'Year' in df.columns and 'J-D' in df.columns:
            df_clean = df[['Year', 'J-D']].copy()
            df_clean.columns = ['year', 'anomaly']
            df_clean['year'] = pd.to_numeric(df_clean['year'], errors='coerce')
            df_clean['anomaly'] = pd.to_numeric(df_clean['anomaly'], errors='coerce')
            return df_clean.dropna()
    except Exception as e:
        st.error(f"NASA Connection Error: {e}")
    return pd.DataFrame({'year': [2000, 2024], 'anomaly': [0.4, 1.1]})

# --- 4. THE COLUMN DETECTION ENGINE (AI + Robust Fallback) ---
def detect_data_columns(df, api_key=None):
    """Identifies which column is Time and which is Data."""
    cols = df.columns.tolist()
    
    # --- STEP 1: If API Key exists, use Claude ---
    if api_key:
        try:
            client = anthropic.Anthropic(api_key=api_key)
            sample = df.head(5).to_string()
            prompt = f"Analyze these CSV headers: {cols}. Here is a sample: {sample}. Tell me which column is Year/Time and which is the Data/Anomaly. Return ONLY: Year: [col], Data: [col]"
            
            response = client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )
            result = response.content[0].text
            y_name = result.split("Year:")[1].split("\n")[0].strip()
            d_name = result.split("Data:")[1].split("\n")[0].strip()
            return y_name, d_name
        except Exception as e:
            st.warning(f"AI Mapping failed, using internal logic. Error: {e}")

    # --- STEP 2: Robust Heuristic Fallback (Fake AI) ---
    detected_year = None
    detected_data = None
    
    # Find Year: Look for 4-digit numbers or keywords
    for c in cols:
        col_str = str(c).lower()
        if any(k in col_str for k in ['year', 'yr', 'date', 'time', 'period']):
            detected_year = c
            break
    
    if not detected_year:
        # Check values if names don't match
        for c in cols:
            first_vals = pd.to_numeric(df[c], errors='coerce').dropna()
            if not first_vals.empty:
                if 1700 < first_vals.iloc[0] < 2100:
                    detected_year = c
                    break

    # Find Data: Look for climate keywords
    for c in cols:
        if c == detected_year: continue
        col_str = str(c).lower()
        if any(k in col_str for k in ['temp', 'anom', 'val', 'j-d', 'annual', 'gistemp', 'sst']):
            detected_data = c
            break
            
    # Ultimate Fallback: Just take whatever is left
    if not detected_year: detected_year = cols[0]
    if not detected_data: 
        remaining_cols = [c for c in cols if c != detected_year]
        detected_data = remaining_cols[0] if remaining_cols else cols[0]
        
    return detected_year, detected_data

# --- 5. SIDEBAR LOGIC ---
with st.sidebar:
    st.title("🌊 Tide Tales Settings")
    st.markdown("Use these controls to adjust the narrative context.")
    st.divider()
    
    # API Key
    api_key = st.text_input("Anthropic API Key", type="password", key="sidebar_api_key")
    
    # Location Fix
    raw_loc = get_accurate_location()
    st.write(f"Detected Location: **{raw_loc}**")
    user_location = st.text_input("📍 Confirm/Edit Location", value=raw_loc, key="sidebar_location")
    
    st.divider()
    
    # Data Selection
    source_choice = st.radio(
        "Data Source", 
        ["Official NASA GISTEMP", "Manual CSV Upload"], 
        key="sidebar_source"
    )
    
    user_file = None
    if source_choice == "Manual CSV Upload":
        user_file = st.file_uploader("Upload CSV", type="csv", key="sidebar_uploader")
    
    demo_mode = st.toggle("Enable Demo Mode", value=True, key="sidebar_demo")

# --- 6. DATA PROCESSING FLOW ---
# Initialize session state so data isn't lost on rerun
if 'current_df' not in st.session_state:
    st.session_state['current_df'] = fetch_nasa_data()

# Logic for custom uploads
if source_choice == "Manual CSV Upload" and user_file:
    # Handle NASA files which might need skiprows
    try:
        # Peek at the file
        test_df = pd.read_csv(user_file, nrows=5)
        user_file.seek(0) # Reset
        
        # Logic to check if Row 0 is junk (common in NASA files)
        if "Land-Ocean" in str(test_df.columns[0]):
            df_to_map = pd.read_csv(user_file, skiprows=1, na_values="***")
        else:
            df_to_map = pd.read_csv(user_file, na_values="***")
            
        if st.button("🔍 Analyze & Map Data Structure", key="btn_analyze"):
            with st.spinner("Analyzing columns..."):
                y_col, d_col = detect_data_columns(df_to_map, api_key)
                
                # Double check the names exist
                if y_col in df_to_map.columns and d_col in df_to_map.columns:
                    st.success(f"Success! Mapping **{y_col}** as Time and **{d_col}** as Data.")
                    final_df = df_to_map[[y_col, d_col]].copy()
                    final_df.columns = ['year', 'anomaly']
                    final_df = final_df.apply(pd.to_numeric, errors='coerce').dropna()
                    st.session_state['current_df'] = final_df
                else:
                    st.error(f"Mapping failed. Found '{y_col}' and '{d_col}' but they don't exist in file.")
    except Exception as e:
        st.error(f"File Error: {e}")

elif source_choice == "Official NASA GISTEMP":
    st.session_state['current_df'] = fetch_nasa_data()

# Final Clean Up of the active data
data = st.session_state['current_df'].copy()
data['year'] = pd.to_numeric(data['year'], errors='coerce')
data['anomaly'] = pd.to_numeric(data['anomaly'], errors='coerce')
data = data.dropna()

# --- 7. MAIN DASHBOARD ---
st.title("🌊 Tide Tales")

# Time Range Slider
min_yr, max_yr = int(data['year'].min()), int(data['year'].max())
if min_yr >= max_yr: max_yr = min_yr + 1
selected_years = st.slider("Select Time Range", min_yr, max_yr, (min_yr, max_yr), key="main_slider")

# Filter Data
filtered = data[(data['year'] >= selected_years[0]) & (data['year'] <= selected_years[1])]

if not filtered.empty:
    # --- MATH: THE FACT PACK ---
    start_val = filtered['anomaly'].iloc[0]
    end_val = filtered['anomaly'].iloc[-1]
    net_change = end_val - start_val
    peak_val = filtered['anomaly'].max()
    trough_val = filtered['anomaly'].min()
    
    # Regression for the Trendline
    slope, intercept = np.polyfit(filtered['year'], filtered['anomaly'], 1)

    # --- UI: EVIDENCE PANEL ---
    st.header("📊 Evidence Panel")
    fig = px.line(
        filtered, x='year', y='anomaly', 
        title=f"Climate Observation: {selected_years[0]} - {selected_years[1]}",
        template="plotly_dark",
        labels={'year': 'Year', 'anomaly': 'Temperature Anomaly (°C)'}
    )
    # Add Trendline
    fig.add_scatter(
        x=filtered['year'], 
        y=slope*filtered['year'] + intercept, 
        name="Mathematical Trend", 
        line=dict(color='red', dash='dot')
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- UI: FACT PACK ---
    st.subheader("📋 The Fact Pack (Calculated)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Net Shift", f"{round(net_change, 2)}°C")
    c2.metric("Warming Rate", f"{round(slope, 3)}°C/yr")
    c3.metric("Highest Peak", f"{round(peak_val, 2)}°C")
    c4.metric("Lowest Trough", f"{round(trough_val, 2)}°C")

    # --- UI: NARRATIVE (Week 3 Deliverable) ---
    st.divider()
    st.header("📖 Local Narrative")
    
    if st.button("✨ Weave Narrative", key="btn_weave"):
        # Template story that proves Week 3 math is working
        story = f"""
        In the land of {user_location}, a story is being written by the shifting tides. 
        Between the years {selected_years[0]} and {selected_years[1]}, the physical world 
        has transformed by {round(net_change, 2)} degrees. 
        
        The peaks of this fever reached {round(peak_val, 2)}°C, while the troughs fell to {round(trough_val, 2)}°C. 
        Currently, the land warms at a measured pace of {round(slope, 3)} degrees every single year.
        """
        
        if api_key and not demo_mode:
            st.info("AI Mode: Claude is reading the Fact Pack for Week 4 integration...")
            # (Week 4 Code will go here)
        else:
            st.info("Demo Mode: Generating Narrative from Calculated Stats")
            st.write(story)
            st.balloons()
else:
    st.error("The selected range contains no data. Please adjust the slider.")
