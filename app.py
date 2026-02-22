import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import anthropic
import requests
import time

# --- 1. SETTINGS ---
st.set_page_config(page_title="Tide Tales", layout="wide", page_icon="🌊")

if 'user_location' not in st.session_state: st.session_state['user_location'] = "Bhubaneswar, India"
if 'data_mapped' not in st.session_state: st.session_state['data_mapped'] = None
if 'metadata' not in st.session_state: st.session_state['metadata'] = None

# --- 2. THE AI DATA INTERPRETER (The "Sniffer") ---
def interpret_file_structure(df, api_key):
    """Sends file sample to AI to return mapping and science context."""
    if not api_key:
        # Fallback for testing/demo
        return {"year": df.columns[0], "data": df.columns[1], "type": "Climate Data", "unit": "Units"}

    client = anthropic.Anthropic(api_key=api_key)
    sample = df.head(10).to_string()
    
    prompt = f"""
    Analyze this CSV sample and identify the structure for a climate dashboard.
    SAMPLE:
    {sample}

    TASK:
    1. Identify the 'Time/Year' column name.
    2. Identify the 'Primary Measurement' column name.
    3. Identify the Science Type (e.g. Temperature, AQI, Sea Level) and the Unit.

    RETURN ONLY THIS JSON FORMAT:
    {{
        "year": "column_name",
        "data": "column_name",
        "type": "Science Type",
        "unit": "Measurement Unit"
    }}
    """
    
    try:
        response = client.messages.create(model="claude-3-5-sonnet-20240620", max_tokens=150, messages=[{"role": "user", "content": prompt}])
        return eval(response.content[0].text) # Simple parsing for JSON
    except:
        return {"year": df.columns[0], "data": df.columns[1], "type": "Climate", "unit": "Units"}

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("🌊 Tide Tales")
    api_key = st.text_input("Anthropic API Key", type="password")
    st.session_state['user_location'] = st.text_input("📍 Your Location", value=st.session_state['user_location'])
    st.divider()
    uploaded_file = st.file_uploader("Step 1: Upload Scientific CSV", type="csv")

# --- 4. MAIN DASHBOARD ---
st.title("🌊 Tide Tales")

if uploaded_file:
    raw_df = pd.read_csv(uploaded_file, na_values="***")
    
    # Automatically interpret if not already done
    if st.session_state['metadata'] is None or st.button("🔄 Re-Analyze File"):
        with st.spinner("AI is reading and interpreting your file..."):
            meta = interpret_file_structure(raw_df, api_key)
            st.session_state['metadata'] = meta
            
            # Map the dataframe based on AI's findings
            clean_df = raw_df[[meta['year'], meta['data']]].copy()
            clean_df.columns = ['year', 'val']
            clean_df['year'] = pd.to_numeric(clean_df['year'], errors='coerce')
            clean_df['val'] = pd.to_numeric(clean_df['val'], errors='coerce')
            st.session_state['data_mapped'] = clean_df.dropna()

if st.session_state['data_mapped'] is not None:
    data = st.session_state['data_mapped']
    meta = st.session_state['metadata']
    
    # --- NUMPY PLOTTER ---
    min_y, max_y = int(data['year'].min()), int(data['year'].max())
    rng = st.slider("Select Time Range", min_y, max_y, (min_y, max_y), key="time_slider")
    f_df = data[(data['year'] >= rng[0]) & (data['year'] <= rng[1])]
    
    # Math trend
    slope, intercept = np.polyfit(f_df['year'], f_df['val'], 1)
    
    # Plotting using the AI-detected Labels
    st.header(f"📊 Evidence: {meta['type']}")
    fig = px.line(f_df, x='year', y='val', template="plotly_dark", 
                  labels={'year': 'Year', 'val': meta['unit']},
                  title=f"Trend of {meta['type']} in {st.session_state['user_location']}")
    
    fig.add_scatter(x=f_df['year'], y=slope*f_df['year'] + intercept, 
                    name="Mathematical Trendline", line=dict(color='red', dash='dot'))
    st.plotly_chart(fig, use_container_width=True)

    # Metrics
    c1, c2, c3 = st.columns(3)
    net = f_df['val'].iloc[-1] - f_df['val'].iloc[0]
    c1.metric("Net Change", f"{round(net, 2)} {meta['unit']}")
    c2.metric("Trend Slope", f"{round(slope, 4)} / yr")
    c3.metric("Peak Value", round(f_df['val'].max(), 2))

    # --- 5. THE CREATIVE STORYTELLER ---
    st.divider()
    if st.button("✨ Weave 1500-Word Narrative", key="weave_btn"):
        if not api_key:
            # DEMO FALLBACK
            st.info("Demo Mode: Generating a poetic summary...")
            st.write(f"In {st.session_state['user_location']}, the {meta['type']} is shifting at a pace of {round(slope, 4)}...")
        else:
            client = anthropic.Anthropic(api_key=api_key)
            
            # THE "WIGGLE ROOM" PROMPT
            prompt = f"""
            Identify as a Cultural Data Sentinel. 
            Write an immersive 1,500-word story for the people of {st.session_state['user_location']}.
            
            THE DATA CONTEXT:
            - Science: {meta['type']}
            - Net Change: {round(net, 2)} {meta['unit']}
            - Trend Speed: {round(slope, 4)} per year
            
            TASK:
            1. Use the local folklore and traditional myths of {st.session_state['user_location']} as the narrative soil.
            2. The scientific data is the "Atmosphere" or "Environment" of the story. It is the inescapable physical truth.
            3. You have full creative freedom. Do not use a fixed scaffold or chapters. 
            4. Integrate the numbers naturally into the prose (e.g. "the fever of 1.2 degrees" or "the 4mm rise of the hungry tides").
            5. Output: FULL story in English, followed by FULL story in the local vernacular of {st.session_state['user_location']}.
            
            FORMAT: [ENGLISH] ... [LOCAL]
            """

            col_e, col_l = st.columns(2)
            e_p, l_p = col_e.empty(), col_l.empty()
            full_resp = ""
            
            with client.messages.stream(model="claude-3-5-sonnet-20240620", max_tokens=8192, messages=[{"role": "user", "content": prompt}]) as stream:
                for text in stream.text_stream:
                    full_resp += text
                    if "[LOCAL]" in full_resp:
                        parts = full_resp.split("[LOCAL]")
                        eng_text = parts[0].replace("[ENGLISH]", "").strip()
                        loc_text = parts[1].strip()
                        e_p.markdown(eng_text); l_p.markdown(loc_text + " ▌")
                    else:
                        e_p.markdown(full_resp.replace("[ENGLISH]", "").strip() + " ▌")
            st.balloons()
