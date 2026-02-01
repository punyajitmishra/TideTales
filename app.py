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
# --- 6. DATA PROCESSING (REFACTORED) ---

# Track the current source to detect changes
if 'current_source' not in st.session_state:
    st.session_state['current_source'] = source_choice

# If the source changes, clear the active_df so it reloads
if st.session_state['current_source'] != source_choice:
    st.session_state['current_source'] = source_choice
    if source_choice == "NASA GISTEMP (Global)":
        st.session_state['active_df'] = fetch_nasa_gistemp()
    else:
        st.session_state['active_df'] = None # Wait for upload

# Logic for CSV Upload
if source_choice == "Upload My Own CSV":
    if user_file is not None:
        # Use a secondary session state to see if we've already processed this specific file
        if st.session_state.get('last_uploaded_file') != user_file.name:
            try:
                peek = pd.read_csv(user_file, nrows=2)
                user_file.seek(0)
                skip = 1 if "Land-Ocean" in str(peek.columns[0]) else 0
                raw_df = pd.read_csv(user_file, skiprows=skip, na_values="***")
                
                # Auto-sniff columns immediately or on button
                y_name, d_name = ai_sniff_columns(raw_df, api_key)
                
                if y_name in raw_df.columns and d_name in raw_df.columns:
                    processed = raw_df[[y_name, d_name]].copy()
                    processed.columns = ['year', 'anomaly']
                    processed['year'] = pd.to_numeric(processed['year'], errors='coerce')
                    processed['anomaly'] = pd.to_numeric(processed['anomaly'], errors='coerce')
                    
                    # Store in session state permanently
                    st.session_state['active_df'] = processed.dropna()
                    st.session_state['last_uploaded_file'] = user_file.name
                    st.success(f"Loaded: {y_name} & {d_name}")
            except Exception as e:
                st.error(f"Load Error: {e}")
    else:
        st.info("Please upload a CSV file to begin.")

# Fallback/Initialization for NASA
if st.session_state.get('active_df') is None and source_choice == "NASA GISTEMP (Global)":
    st.session_state['active_df'] = fetch_nasa_gistemp()

# Assign data for the rest of the app
if st.session_state.get('active_df') is not None:
    data = st.session_state['active_df'].copy()
else:
    st.warning("No data available to plot.")
    st.stop() # Prevents errors in the math section

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
                    prompt = f"""
                    You are a master storyteller and cultural researcher.
                    DATA CONTEXT (The Truth):
                    - Science: {sci['label']}
                    - Period: {selected_range[0]} to {selected_range[1]}
                    - Net Change: {round(net_shift, 2)} {sci['unit']}
                    - Warming Rate: {round(slope, 3)} per year
                    - Peak: {round(peak, 2)}, Trough: {round(trough, 2)}
                    
                    LOCATION: {st.session_state['user_location']}
                    
                    TASK:
                    Write a 1,500-word immersive story. 
                    1. Use the specific folklore and rhythmic storytelling style of {st.session_state['user_location']}.
                    2. The data is the environment, not a villain.
                    3. Structure in 5 chapters.
                    4. Output the full story in English, then the full story in the local vernacular language of {st.session_state['user_location']}.
                    
                    FORMAT: Use [ENGLISH] and [LOCAL] markers.
                    """

                    # Setup Two-Column Layout for the Real AI
                    col_eng, col_loc = st.columns(2)
                    with col_eng:
                        st.subheader("🌍 English Epic")
                        eng_p = st.empty()
                    with col_loc:
                        st.subheader(f"🗣️ Local Voice ({st.session_state['user_location']})")
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
                    st.balloons()

                except Exception as e:
                    st.error(f"AI Error: {e}")
        
        else:
            # THE PROCEDURAL DEMO ENGINE (Your existing backup logic)
            loc = st.session_state['user_location']
            intensity = "a frantic gallop" if slope > 0.015 else "a steady, relentless climb"
            impact = "the world has broken its ancient promises" if abs(net_shift) > 1.0 else "the balance is beginning to fray"

            ch1_v = [
                f"In the ancient memory of the people of **{loc}**, the wind once spoke a language of predictable seasons. But since **{selected_range[0]}**, a new dialect has emerged—one written in the language of {sci['metaphor']}.",
                f"The soil of **{loc}** has its own way of keeping time. Long before we had the records starting in **{selected_range[0]}**, the ancestors knew the rhythm of the {sci['element']}. Now, that rhythm has faltered."
            ]
            ch2_v = [
                f"Science confirms what our hearts suspected. Our trendline moves at {intensity} ({round(slope, 3)} units/yr). In the year of the peak (**{round(peak, 2)}**), the very stones of {loc} seemed to weep.",
                f"The math does not lie. Moving at **{round(slope, 3)} per year**, the {sci['element']} is undergoing {intensity}."
            ]
            ch3_v = [
                f"There is a legend in **{loc}** about a mirror of spirits. Today, that mirror is clouded. The trough of **{round(trough, 2)}** is a ghost of a cooler past.",
                f"The measurement stands today at **{round(val_end, 2)}**. The trough of **{round(trough, 2)}** is a milestone we are leaving behind."
            ]
            
            # [Add your other ch_v lists here if they aren't already in your code]

            story_chapters = [
                   f"""
                ### Chapter 1: The Omens of {sci['element']}
                {random.choice(ch1_v)} 
                They spoke of the 'Great Cycle,' a time when the world behaved according to the laws 
                laid down by the ancestors. Long before the records began, 
                the earth of **{loc}** had its own way of keeping time—measured in the arrival of the 
                first monsoon and the depth of the winter frost. Every tree, every stone, and every 
                breath of wind was a syllable in a long, predictable song.
                
                But the data reveals a shift of **{round(net_shift, 2)} {sci['unit']}**, a change that 
                is felt in the drying of the wells and the heat of the noon-day sun. 
                This isn't just a digit on a spreadsheet; it is the reason the mango blossoms are late, 
                and why the spirits of the woods in **{loc}** seem restless. The old songs no longer 
                describe the rhythm of the rains. The science calls it an anomaly; the folklore calls it 'The Unraveling.' 
                It is as if {impact}, and we are left to interpret the new, harsh dialect of the earth.
                """,
                f"""
                ### Chapter 2: The Quickening Fever
                {random.choice(ch2_v)} 
                Think of the massive momentum required to shift the entire climate of a region. 
                The measurement of {sci['label']} is no longer a fluctuation; it is a transformation. 
                It is a silent thief that steals the moisture from the fields before the seeds can take hold, 
                moving with a speed that outpaces the migration of the birds.
                
                In the year that the measurement touched the peak of **{round(peak, 2)}**, 
                the very stones of **{loc}** seemed to remember a coolness they may never feel again. 
                This is the truth of the **{sci['metaphor']}**: it does not ask permission to 
                transform the physics of our home. It is a fever that does not break at night. 
                We see it in the data points, which are the scars of a changing world, documented 
                with cold precision yet lived with hot intensity by every living soul here.
                """,
                f"""
                ### Chapter 3: The Ghost of the Mirror
                {random.choice(ch3_v)} 
                Folklore tells us of a mirror once held by the forest spirits—a mirror that showed the 
                true health of the world. Today, that mirror is clouded, its surface cracked by the 
                weight of the unseen. The trough of **{round(trough, 2)}** is now a ghost—a remnant 
                of a more stable, cooler past that is receding into the fog of history. 
                The children of **{loc}** listen to stories of cold winters the same way they listen 
                to fables of dragons; for them, the world of the trough is a legend they cannot touch.
                
                The measurement stands today at **{round(val_end, 2)}**, far from the reflection we once knew. 
                In **{loc}**, the activists know that the decimal points are only the skeleton of the truth. 
                The 'Wiggle Room' between the data and our lives is where the narrative lives—where the 
                rising value of {sci['unit']} meets the enduring spirit of a people. 
                It is in this space that we find the courage to name the change, and in naming it, 
                we begin to reclaim our relationship with the land.
                """,
                f"""
                ### Chapter 4: The Convergence of Tides
                As we stand at the end of this record in **{selected_range[1]}**, the story of 
                **{loc}** is far from over. The rising lines on our Evidence Panel are the map of 
                a new territory, one where scientific truth and local song must converge. 
                The data points are the milestones of our journey, but the folklore is the map 
                that helps us find our way home through the changing tides.
                
                To save the land, we must understand both. The narrative of the **{sci['label']}** 
                is a struggle written in the language of units, but told with the heart 
                of a people who refuse to let their home be defined by an anomaly. We are the 
                authors of the next chapter, drafting the song of our survival. The tides are 
                rising, but our voices are rising with them in **{loc}**.
                """
            ]
            
            for chap in story_chapters:
                st.markdown(chap)
                time.sleep(0.7)
            st.balloons()
