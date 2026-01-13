import streamlit as st
import pandas as pd
import time
import requests

# 1. SETUP
st.set_page_config(page_title="TideTales", layout="wide")

# 2. SIDEBAR
with st.sidebar:
    st.title("🌿 TideTales Settings")
    api_key = st.text_input("Anthropic API Key", type="password")
    
    try:
        geo = requests.get('https://ipapi.co/json/').json()
        loc = f"{geo.get('city', 'Kolkata')}, {geo.get('country_name', 'India')}"
    except:
        loc = "your local region"
    
    st.write(f"📍 **Context:** {loc}")
    uploaded_file = st.file_uploader("Optional: Upload CSV", type="csv")
    
    st.divider()
    # If no file is uploaded, we use this sample data
    use_sample = st.checkbox("Use Sample Climate Data", value=True)

# 3. MAIN UI
st.title("🌿Tide Tales")
st.markdown("### *Bridging Science and Folklore*")

# Logic to determine which data to use
if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.info("Using your uploaded data.")
elif use_sample:
    # Creating a small fake dataset about rising temperatures
    df = pd.DataFrame({
        'Year': [2020, 2021, 2022, 2023, 2024, 2025],
        'Avg_Temp_C': [30.1, 30.4, 30.8, 31.2, 31.5, 31.9],
        'Salinity_Level': [12, 13, 15, 18, 20, 22]
    })
    st.info("Using Sample Climate Data (Sundarbans Context).")
else:
    st.warning("Please upload a file or check 'Use Sample Data' in the sidebar.")
    st.stop()

# THE TRIGGER
if st.button("✨ Weave 1500-Word Narrative"):
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🌍 English Narrative")
        eng_placeholder = st.empty()
        
    with col2:
        st.subheader(f"🗣️ Local Voice ({loc})")
        loc_placeholder = st.empty()

    if not api_key:
        # --- IMPROVED DEMO MODE LOGIC ---
        st.toast("Running in Demo Mode (No API Key)")
        
        eng_story = [
            "Chapter 1: The Altered Rhythm. The elders always said the river had a pulse, but according to the data (Avg Temp: 31.9C), that pulse is quickening. ",
            "The salt levels have climbed to 22%, a number the mangroves do not recognize. ",
            "In the village of the delta, the spirits of the ancestors are whispering about the heat... ",
            "This story would continue for 1500 words, weaving the salinity metrics into the legend of Bonbibi. "
        ] * 10 # This makes it long
        
        loc_story = [
            "প্রথম অধ্যায়: পরিবর্তিত ছন্দ। বড়োরা বলতেন নদীর একটা নাড়ি আছে, কিন্তু উপাত্ত বলছে সেই নাড়ি এখন দ্রুত ছুটছে। ",
            "লবণাক্ততা এখন ২২ শতাংশে পৌঁছেছে, যা ম্যানগ্রোভ বন আগে কখনো দেখেনি। ",
            "বদ্বীপের গ্রামে পূর্বপুরুষদের আত্মা উত্তাপের কথা বলছে... ",
            "এই কাহিনী ১৫০০ শব্দ জুড়ে চলিবে, যেখানে লবণের মাত্রা আর বনবিবির উপাখ্যান এক হয়ে মিশে যাবে।"
        ] * 10

        # Simulate real-time streaming for English
        full_eng = ""
        for snippet in eng_story:
            for word in snippet.split():
                full_eng += word + " "
                eng_placeholder.markdown(full_eng + "▌")
                time.sleep(0.05) # Speed of reading
        eng_placeholder.markdown(full_eng)

        # Simulate real-time streaming for Local
        full_loc = ""
        for snippet in loc_story:
            for word in snippet.split():
                full_loc += word + " "
                loc_placeholder.markdown(full_loc + "▌")
                time.sleep(0.05)
        loc_placeholder.markdown(full_loc)
        
        st.balloons()
        
    else:
        # --- REAL AI LOGIC ---
        # (This section will run only if you paste your actual API key)
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        
        with st.spinner("Claude is weaving the epic..."):
            # Full AI streaming code goes here
            st.write("AI connection active. Generating 1500 words...")
