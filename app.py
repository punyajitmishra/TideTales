import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import anthropic
import requests
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Tide Tales", layout="wide", page_icon="🌊")

# Initialize persistent memory
if 'user_location' not in st.session_state:
    st.session_state['user_location'] = "Bhubaneswar, India"
if 'data_mapped' not in st.session_state:
    st.session_state['data_mapped'] = None
if 'sci_metadata' not in st.session_state:
    st.session_state['sci_metadata'] = None

# --- 2. SIDEBAR ---
with st.sidebar:
    st.title("🌊 Tide Tales Settings")
    api_key = st.text_input("Anthropic API Key", type="password", key="api_key")
    
    # Manual location override to ensure accuracy
    st.session_state['user_location'] = st.text_input(
        "📍 Location Context", 
        value=st.session_state['user_location'], 
        key="loc_input"
    )
    
    st.divider()
    uploaded_file = st.file_uploader("Step 1: Upload Scientific CSV", type="csv")
    st.info("The AI will automatically identify the science type and columns upon analysis.")

# --- 3. THE AI DATA INTERPRETER (The "Sniffer") ---
def ai_interpret_data(df, api_key):
    """AI scans the file snippet to define the 'physics' of the dashboard."""
    client = anthropic.Anthropic(api_key=api_key)
    sample = df.head(10).to_string()
    headers = df.columns.tolist()
    
    prompt = f"""
    Analyze this dataset sample and identify its purpose for a climate dashboard.
    SAMPLE DATA:
    {sample}
    
    HEADERS: {headers}
    
    IDENTIFY:
    1. Which column is the Time (Year or Date)?
    2. Which column is the primary Measurement (Value/Anomaly)?
    3. What is the unit (e.g., °C, ppm, mm, AQI Index)?
    4. What is the Science Label (e.g., Air Quality, Sea Level Rise, Global Warming)?
    
    RETURN ONLY IN THIS FORMAT:
    YearCol: [name]
    DataCol: [name]
    Unit: [unit]
    Label: [label]
    """
    
    response = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )
    res = response.content[0].text
    
    # Parsing the AI's response into a dictionary
    mapping = {}
    for line in res.strip().split('\n'):
        if ':' in line:
            key, val = line.split(':', 1)
            mapping[key.strip()] = val.strip()
    return mapping

# --- 4. MAIN INTERFACE LOGIC ---
st.title("🌊 Tide Tales")

if uploaded_file:
    # Use pandas to read any standard CSV
    raw_df = pd.read_csv(uploaded_file, na_values="***")
    
    # Analyze button triggers the AI "Sniffer"
    if st.button("🔍 AI: Interpret Data Structure"):
        if not api_key:
            st.error("Please enter an API Key in the sidebar.")
        else:
            with st.spinner("AI is analyzing file structure and science type..."):
                try:
                    mapping = ai_interpret_data(raw_df, api_key)
                    
                    # Create the standardized dataframe for the plotter
                    y_col, d_col = mapping['YearCol'], mapping['DataCol']
                    clean_df = raw_df[[y_col, d_col]].copy()
                    clean_df.columns = ['year', 'val']
                    clean_df['year'] = pd.to_numeric(clean_df['year'], errors='coerce')
                    clean_df['val'] = pd.to_numeric(clean_df['val'], errors='coerce')
                    
                    st.session_state['data_mapped'] = clean_df.dropna()
                    st.session_state['sci_metadata'] = mapping
                    st.success(f"AI identified this as {mapping['Label']} data.")
                except Exception as e:
                    st.error(f"Mapping failed: {e}")

# --- 5. NUMPY PLOTTER & DASHBOARD ---
if st.session_state['data_mapped'] is not None:
    data = st.session_state['data_mapped']
    meta = st.session_state['sci_metadata']
    
    # 5a. Time range selection
    min_y, max_y = int(data['year'].min()), int(data['year'].max())
    selected_range = st.slider("Select Time Range", min_y, max_y, (min_y, max_y))
    f_df = data[(data['year'] >= selected_range[0]) & (data['year'] <= selected_range[1])]

    # 5b. NUMPY MATH (The Fact Pack)
    slope, intercept = np.polyfit(f_df['year'], f_df['val'], 1)
    net_change = f_df['val'].iloc[-1] - f_df['val'].iloc[0]
    
    # 5c. DYNAMIC PLOTTING
    st.header(f"📊 Evidence: {meta['Label']}")
    fig = px.line(f_df, x='year', y='val', template="plotly_dark", 
                  labels={'year': 'Year', 'val': meta['Unit']},
                  title=f"Observing {meta['Label']} in {st.session_state['user_location']}")
    
    # Adding the red dotted Trendline via Numpy
    fig.add_scatter(x=f_df['year'], y=slope*f_df['year'] + intercept, 
                    name="Mathematical Trend", line=dict(color='red', dash='dot'))
    st.plotly_chart(fig, use_container_width=True)

    # Display Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Net Shift", f"{round(net_change, 2)} {meta['Unit']}")
    c2.metric("Trend Rate", f"{round(slope, 4)} / yr")
    c3.metric("Peak Record", round(f_df['val'].max(), 2))

    # --- 6. AI STORY WRITER (NO SCAFFOLD - FULL CREATIVITY) ---
    st.divider()
    if st.button("✨ Weave 1500-Word Narrative"):
        if not api_key:
            st.error("API Key required.")
        else:
            # The "Wiggle Room" Prompt - No chapters, total narrative freedom
            prompt = f"""
            Identify as a Cultural Data Sentinel and a master literary novelist.
            LOCATION: {st.session_state['user_location']}
            DATA: {meta['Label']} change in {meta['Unit']}. 
            TIMEFRAME: {selected_range[0]} to {selected_range[1]}.
            FACTS: Net change of {round(net_change, 2)}. Trend rate of {round(slope, 4)} per year.

            TASK:
            Write a 1,500-word immersive story grounded in this data. 
            1. FULL CREATIVE FREEDOM: Do not use a fixed scaffold or chaptered structure. 
            2. NARRATIVE PHYSICS: The scientific data is the inescapable atmosphere of the world. Integrate the numbers (e.g., the trend rate, the peak) naturally into the prose as metaphors or physical realities.
            3. CULTURE: Use the folklore, local myths, and specific storytelling metaphors of {st.session_state['user_location']}.
            4. INTEGRITY: The data is the truth, not the villain.
            
            FORMAT: Write the FULL story in English, then the FULL story in the local vernacular of {st.session_state['user_location']}. Use [ENGLISH] and [LOCAL] markers.
            """
            
            client = anthropic.Anthropic(api_key=api_key)
            col_e, col_l = st.columns(2)
            e_p, l_p = col_e.empty(), col_l.empty()
            full_resp = ""
            
            with client.messages.stream(
                model="claude-3-5-sonnet-20240620",
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                for text in stream.text_stream:
                    full_resp += text
                    if "[LOCAL]" in full_resp:
                        parts = full_resp.split("[LOCAL]")
                        e_text = parts[0].replace("[ENGLISH]", "").strip()
                        l_text = parts[1].strip()
                        e_p.markdown(e_text); l_p.markdown(l_text + " ▌")
                    else:
                        e_p.markdown(full_resp.replace("[ENGLISH]", "").strip() + " ▌")
            st.balloons()
else:
    st.info("👈 Please upload a scientific CSV file and click 'Interpret' to begin.")
