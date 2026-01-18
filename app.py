import streamlit as st
import pandas as pd
import plotly.express as px
import anthropic
import requests
import time
import numpy as np

# --- 1. SETUP ---
st.set_page_config(page_title="Tide Tales", layout="wide", page_icon="🌊")

# --- 2. DATA INGESTION (NASA + Upload Logic) ---
@st.cache_data
def load_nasa_gistemp():
    url = "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv"
    df = pd.read_csv(url, skiprows=1, na_values="***")
    df_clean = df[['Year', 'J-D']].copy()
    df_clean.columns = ['year', 'anomaly']
    # Force numeric and drop rows that aren't real numbers
    df_clean['year'] = pd.to_numeric(df_clean['year'], errors='coerce')
    df_clean['anomaly'] = pd.to_numeric(df_clean['anomaly'], errors='coerce')
    return df_clean.dropna()

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("🌊 Tide Tales")
    st.divider()
    
    api_key = st.text_input("Anthropic API Key", type="password")
    
    # Auto-detect location
    try:
        geo = requests.get('https://ipapi.co/json/').json()
        loc = f"{geo.get('city', 'Kolkata')}, {geo.get('country_name', 'India')}"
    except:
        loc = "your local region"
    
    st.write(f"📍 **Cultural Context:** {loc}")
    
    st.divider()
    # Week 3 Feature: Data Source Toggle
    data_source = st.radio("Select Data Source", ["NASA GISTEMP (Auto)", "Upload My Own CSV"])
    
    uploaded_file = None
    if data_source == "Upload My Own CSV":
        uploaded_file = st.file_uploader("Upload CSV", type="csv")
    
    demo_mode = st.toggle("Enable Demo Mode", value=True)

# --- 4. DATA PROCESSING ---
if uploaded_file:
    # Handle user-uploaded data
    raw_data = pd.read_csv(uploaded_file)
    # Basic cleaning for user data (assumes first two columns are Year/Value)
    raw_data.columns = ['year', 'anomaly']
    data = raw_data.apply(pd.to_numeric, errors='coerce').dropna()
else:
    # Use hardcoded NASA data
    data = load_nasa_gistemp()

# --- WEEK 3: DATE RANGE SELECTION ---
min_year, max_year = int(data['year'].min()), int(data['year'].max())
selected_years = st.slider("Select Time Range", min_year, max_year, (min_year, max_year))

# Filter data based on slider
filtered_data = data[(data['year'] >= selected_years[0]) & (data['year'] <= selected_years[1])]

# --- WEEK 3: THE FACT PACK (Numpy Computations) ---
# 1. Start/End/Change
start_val = filtered_data['anomaly'].iloc[0]
end_val = filtered_data['anomaly'].iloc[-1]
net_change = end_val - start_val

# 2. Max/Min
max_val = filtered_data['anomaly'].max()
min_val = filtered_data['anomaly'].min()

# 3. Trend (Polyfit)
# We find the slope of the line (anomaly per year)
slope, intercept = np.polyfit(filtered_data['year'], filtered_data['anomaly'], 1)

# --- 5. MAIN INTERFACE ---
st.title("🌊 Tide Tales")

# EVIDENCE PANEL
st.header("📊 Evidence Panel")
fig = px.line(filtered_data, x='year', y='anomaly', 
              title=f"Climate Trend ({selected_years[0]} - {selected_years[1]})",
              template="plotly_dark")
# Add the trendline visually
fig.add_scatter(x=filtered_data['year'], y=slope*filtered_data['year'] + intercept, 
                name="Trendline", line=dict(color='red', dash='dot'))
st.plotly_chart(fig, use_container_width=True)

# THE FACT PACK DISPLAY
st.subheader("📋 The Fact Pack")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Net Change", f"{round(net_change, 2)}°C")
c2.metric("Peak Anomaly", f"{round(max_val, 2)}°C")
c3.metric("Trough Anomaly", f"{round(min_val, 2)}°C")
c4.metric("Rate of Change", f"{round(slope, 3)}°C/yr")

# --- WEEK 3: TEMPLATE-BASED STORY (No LLM yet) ---
st.divider()
st.header("📖 The Narrative")

if st.button("✨ Generate Story"):
    # This is the "Week 3 Deliverable": A story that uses the calculated stats
    template_story = f"""
    In the land of {loc}, the story of the climate has shifted significantly. 
    Between the years {selected_years[0]} and {selected_years[1]}, our records show 
    that the world's temperature breath changed by {round(net_change, 2)} degrees. 
    
    The highest peak of this fever reached {round(max_val, 2)}°C, while the 
    lowest trough was {round(min_val, 2)}°C. Currently, the heat is increasing 
    at a rate of {round(slope, 3)} degrees every single year. 
    
    This is not a myth, but the measured truth of the tides.
    """
    
    if api_key and not demo_mode:
        # (AI Logic would go here for Week 4)
        st.write("AI Narrative Generation (Coming in Week 4)...")
    else:
        # Week 3 Deliverable: Template Story based on actual Fact Pack
        st.info("Demo Mode: Generating Template Story from Calculated Stats")
        st.write(template_story)
        st.balloons()
