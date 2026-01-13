import streamlit as st
import pandas as pd
import plotly.express as px
import anthropic
import requests

# --- 1. SETUP & REBRANDING ---
st.set_page_config(page_title="Tide Tales", layout="wide", page_icon="🌊")

# --- 2. DATA INGESTION (NASA GISTEMP Hardcoded) ---
@st.cache_data
def load_nasa_gistemp():
    # Official NASA GISS Land-Ocean Temperature Index
    url = "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv"
    
    # NASA's CSV has metadata headers and repeats column names every 20 lines.
    # na_values="***" handles NASA's way of marking missing data.
    df = pd.read_csv(url, skiprows=1, na_values="***")
    
    # Select 'Year' and 'J-D' (Annual Mean Anomaly)
    df_clean = df[['Year', 'J-D']].copy()
    df_clean.columns = ['year', 'anomaly']
    
    # Clean up non-numeric rows (NASA's repeated headers)
    df_clean = df_clean[pd.to_numeric(df_clean['year'], errors='coerce').notnull()]
    df_clean['year'] = df_clean['year'].astype(int)
    df_clean['anomaly'] = df_clean['anomaly'].astype(float)
    
    return df_clean

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("🌊 Tide Tales")
    st.markdown("*Bridging the gap between scientific truth and cultural song.*")
    st.divider()
    
    api_key = st.text_input("Anthropic API Key", type="password")
    
    # Auto-detect location for cultural context
    try:
        geo = requests.get('https://ipapi.co/json/').json()
        loc = f"{geo.get('city', 'Unknown City')}, {geo.get('country_name', 'Unknown Country')}"
    except:
        loc = "your local region"
    
    st.write(f"📍 **Cultural Context:** {loc}")
    st.divider()
    st.caption("Data Source: NASA GISTEMP v4")

# --- 4. MAIN INTERFACE ---
st.title("🌊 Tide Tales")
st.subheader("Visual Evidence & Folklore Narrative")

try:
    # Load and clean the data
    data = load_nasa_gistemp()
    
    # --- WEEK 2: THE EVIDENCE PANEL ---
    with st.container():
        st.header("📊 Evidence Panel")
        
        # Plotly Line Chart
        fig = px.line(data, x='year', y='anomaly', 
                      labels={'year': 'Year', 'anomaly': 'Temp Anomaly (°C)'},
                      title="Global Temperature Anomalies (1880 - Present)",
                      template="plotly_dark")

        # Customizing the chart for activists: clear, bold, and high-contrast
        fig.add_hline(y=0, line_dash="dash", line_color="white", annotation_text="Baseline (1951-1980)")
        fig.update_traces(line_color='#00D4FF', line_width=3)
        fig.update_layout(hovermode="x unified")
        
        st.plotly_chart(fig, use_container_width=True)

    # --- WEEK 3 PREVIEW: THE FACT PACK ---
    col1, col2, col3 = st.columns(3)
    latest_anomaly = data['anomaly'].iloc[-1]
    start_anomaly = data['anomaly'].iloc[0]
    total_change = latest_anomaly - start_anomaly

    with col1:
        st.metric("Latest Record", f"{latest_anomaly}°C")
    with col2:
        st.metric("Historical Change", f"+{round(total_change, 2)}°C")
    with col3:
        st.metric("Period Tracked", f"{len(data)} Years")

    # --- THE NARRATIVE GENERATOR ---
    st.divider()
    if st.button("✨ Weave 1500-Word Narrative"):
        if not api_key:
            st.error("Please enter your Anthropic API Key in the sidebar.")
        else:
            # We take the most recent 30 years to give Claude context
            recent_context = data.tail(30).to_string(index=False)
            
            client = anthropic.Anthropic(api_key=api_key)
            
            # The "Two-Column" placeholders
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🌍 English Tale")
                eng_p = st.empty()
            with c2:
                st.subheader(f"🗣️ Local Voice ({loc})")
                loc_p = st.empty()

            prompt = f"""
            Using this NASA data: {recent_context}
            Write a 1500-word immersive epic story set in {loc}.
            Structure: Use the specific folklore, myths, and rhythmic storytelling patterns of {loc}.
            The data is the environment, not a villain.
            Write the full story in English, then the full story in the local vernacular of {loc}.
            Use the markers [ENGLISH] and [LOCAL] to separate them.
            """

            # Streaming logic
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

            st.balloons()

except Exception as e:
    st.error(f"Error loading NASA data: {e}")
