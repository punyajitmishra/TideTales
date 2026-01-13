import streamlit as st
import pandas as pd
import plotly.express as px
import anthropic
import requests
import time

# --- 1. SETUP & REBRANDING ---
st.set_page_config(page_title="Tide Tales", layout="wide", page_icon="🌊")

# --- 2. DATA INGESTION (NASA GISTEMP) ---
@st.cache_data
def load_nasa_gistemp():
    url = "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv"
    # Skip metadata and handle NASA's missing value marker
    df = pd.read_csv(url, skiprows=1, na_values="***")
    df_clean = df[['Year', 'J-D']].copy()
    df_clean.columns = ['year', 'anomaly']
    # Clean out repeated header rows
    df_clean = df_clean[pd.to_numeric(df_clean['year'], errors='coerce').notnull()]
    df_clean['year'] = df_clean['year'].astype(int)
    df_clean['anomaly'] = df_clean['anomaly'].astype(float)
    return df_clean

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("🌊 Tide Tales")
    st.markdown("*Bridging science and folklore.*")
    st.divider()
    
    api_key = st.text_input("Anthropic API Key", type="password", help="Enter your key to enable real AI storytelling.")
    
    # Auto-detect location
    try:
        geo = requests.get('https://ipapi.co/json/').json()
        loc = f"{geo.get('city', 'Kolkata')}, {geo.get('country_name', 'India')}"
    except:
        loc = "your local region"
    
    st.write(f"📍 **Cultural Context:** {loc}")
    
    st.divider()
    demo_mode = st.toggle("Enable Demo Mode", value=not bool(api_key), help="Check this to see the UI in action without an API key.")
    st.caption("Data Source: NASA GISTEMP v4")

# --- 4. MAIN INTERFACE ---
st.title("🌊 Tide Tales")

try:
    data = load_nasa_gistemp()
    
    # EVIDENCE PANEL
    st.header("📊 Evidence Panel")
    fig = px.line(data, x='year', y='anomaly', 
                  labels={'year': 'Year', 'anomaly': 'Temp Anomaly (°C)'},
                  title="Global Temperature Anomalies (1880 - Present)",
                  template="plotly_dark")
    fig.add_hline(y=0, line_dash="dash", line_color="white", annotation_text="Baseline")
    fig.update_traces(line_color='#00D4FF', line_width=3)
    st.plotly_chart(fig, use_container_width=True)

    # FACT PACK PREVIEW
    c1, c2, c3 = st.columns(3)
    latest = data['anomaly'].iloc[-1]
    total_change = latest - data['anomaly'].iloc[0]
    c1.metric("Latest Anomaly", f"{latest}°C")
    c2.metric("Total Warming", f"+{round(total_change, 2)}°C")
    c3.metric("Data Quality", "NASA Verified")

    # NARRATIVE GENERATOR
    st.divider()
    if st.button("✨ Weave 1500-Word Narrative"):
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🌍 English Tale")
            eng_p = st.empty()
        with col2:
            st.subheader(f"🗣️ Local Voice ({loc})")
            loc_p = st.empty()

        if demo_mode and not api_key:
            # --- SAFE DEMO STREAMING ---
            demo_eng = [
                f"Chapter 1: The Rising Heat. In the streets of {loc}, the air holds a new weight. ",
                f"The NASA data shows a spike of {latest}°C, a fever that the land has never felt before. ",
                "The elders speak of the tides, but these tides follow a rhythm dictated by numbers on a screen. ",
                "This story would continue for 1500 words, weaving the thermal anomalies into the local myths. "
            ] * 15 # Provides enough length to test the look
            
            demo_loc = [
                f"প্রথম অধ্যায়: ক্রমবর্ধমান উত্তাপ। {loc}-এর রাস্তায় আজ এক নতুন ভারী বাতাস। ",
                f"নাসার উপাত্ত বলছে {latest}°C-এর এক অদ্ভুত জ্বর, যা এই মাটি আগে কখনো অনুভব করেনি। ",
                "বড়োরা জোয়ারের কথা বলেন, কিন্তু এই জোয়ার এখন স্ক্রিনের সংখ্যার ছন্দে চলে। ",
                "এই কাহিনী ১৫০০ শব্দ জুড়ে চলিবে, যেখানে তাপমাত্রার পরিবর্তনের সাথে স্থানীয় রূপকথা মিলেমিশে এক হবে।"
            ] * 15

            full_e, full_l = "", ""
            # Stream English first, then Local (to simulate the split logic)
            for chunk in demo_eng:
                full_e += chunk
                eng_p.markdown(full_e + "▌")
                time.sleep(0.1)
            eng_p.markdown(full_e)

            for chunk in demo_loc:
                full_l += chunk
                loc_p.markdown(full_l + "▌")
                time.sleep(0.1)
            loc_p.markdown(full_l)
            st.balloons()

        elif api_key:
            # --- REAL CLAUDE STREAMING ---
            client = anthropic.Anthropic(api_key=api_key)
            recent_context = data.tail(30).to_string(index=False)
            prompt = f"Data: {recent_context}\nLocation: {loc}\nWrite a 1500-word story in [ENGLISH] and [LOCAL] segments using local folklore style."
            
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
        else:
            st.error("Please enter an API Key or enable Demo Mode.")

except Exception as e:
    st.error(f"Error: {e}")
