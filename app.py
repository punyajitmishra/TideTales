import concurrent.futures
import io
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template, request

try:
    import anthropic
except Exception:
    anthropic = None


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tidetales.db"
DATA_PATH = BASE_DIR / "data" / "gistemp_fallback.csv"

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

STORY_DELIMITER = "\n\n---VERNACULAR---\n\n"

# Token budgets, trimmed down from the original 1000/3000.
# Short stories target ~300-500 words (~700 tokens is plenty of headroom).
# Long stories target ~1000-1500 words (~2400 tokens is plenty of headroom).
MAX_TOKENS = {"Short": 700, "Long": 2400}
VERNACULAR_INFER_MAX_TOKENS = 20

# Non-Latin / non-alphabetic scripts (CJK, Indic, etc.) need more tokens to
# express the same word count as English, since tokenization is denser.
# Bump this toward 2.2 if Japanese/Chinese/etc. long stories still truncate.
VERNACULAR_TOKEN_MULTIPLIER = 4.5

DATASET_META = {
    "nasa_gistemp": {
        "id": "nasa_gistemp",
        "label": "NASA GISTEMP Global Temperature Anomaly",
        "unit": "deg C anomaly",
        "value_label": "Temperature anomaly",
        "source": "NASA GISS Surface Temperature Analysis v4",
        "citation_url": "https://data.giss.nasa.gov/gistemp/",
        "notes": "Annual global land-ocean temperature anomaly relative to the 1951-1980 baseline.",
    }
}


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                dataset_label TEXT NOT NULL,
                location TEXT NOT NULL,
                start_year INTEGER NOT NULL,
                end_year INTEGER NOT NULL,
                facts_json TEXT NOT NULL,
                story TEXT NOT NULL
            )
            """
        )


def ensure_fallback_data() -> None:
    if DATA_PATH.exists():
        return

    years = np.arange(1880, 2025)
    t = np.linspace(0, 1, len(years))
    vals = -0.22 + 1.42 * (t ** 1.72)
    vals += 0.06 * np.sin(np.linspace(0, 13 * np.pi, len(years)))
    vals += 0.025 * np.sin(np.linspace(0, 41 * np.pi, len(years)))
    vals = np.round(vals, 2)
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"year": years, "value": vals}).to_csv(DATA_PATH, index=False)


def load_default_data() -> pd.DataFrame:
    ensure_fallback_data()
    return pd.read_csv(DATA_PATH)


def normalize_uploaded_csv(file_storage) -> tuple[pd.DataFrame, dict]:
    raw = file_storage.read()
    if not raw:
        raise ValueError("Uploaded CSV is empty.")

    df = pd.read_csv(io.BytesIO(raw), na_values=["***", "NA", "N/A", ""])
    if df.empty:
        raise ValueError("Uploaded CSV has no rows.")

    year_col = find_year_col(df)
    value_col = find_value_col(df, year_col)
    clean = df[[year_col, value_col]].copy()
    clean.columns = ["year", "value"]
    clean = clean.apply(pd.to_numeric, errors="coerce").dropna()
    clean["year"] = clean["year"].astype(int)
    clean = clean.groupby("year", as_index=False)["value"].mean()
    clean = clean.sort_values("year")

    if clean.shape[0] < 3:
        raise ValueError("Need at least three numeric year/value rows.")

    label = request.form.get("dataset_label") or Path(file_storage.filename).stem or "Uploaded climate dataset"
    unit = request.form.get("unit") or "value"
    meta = {
        "id": "upload",
        "label": label,
        "unit": unit,
        "value_label": request.form.get("value_label") or value_col,
        "source": "User-uploaded CSV",
        "citation_url": "",
        "notes": f"Parsed from {file_storage.filename}; year column: {year_col}; value column: {value_col}.",
    }
    return clean, meta


def find_year_col(df: pd.DataFrame) -> str:
    candidates = [c for c in df.columns if str(c).strip().lower() in {"year", "yr", "date"}]
    if candidates:
        return candidates[0]
    for col in df.columns:
        numeric = pd.to_numeric(df[col], errors="coerce")
        if numeric.dropna().between(1800, 2100).mean() > 0.7:
            return col
    raise ValueError("Could not identify a year column.")


def find_value_col(df: pd.DataFrame, year_col: str) -> str:
    preferred_terms = ["anomaly", "temp", "temperature", "sst", "sea", "level", "co2", "aqi", "pm2", "value", "j-d"]
    numeric_cols = []
    for col in df.columns:
        if col == year_col:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        if series.notna().sum() >= 3:
            numeric_cols.append(col)
    if not numeric_cols:
        raise ValueError("Could not identify a numeric value column.")
    for term in preferred_terms:
        for col in numeric_cols:
            if term in str(col).lower():
                return col
    return numeric_cols[0]


def compute_facts(df: pd.DataFrame, start_year: int, end_year: int, meta: dict, location: str) -> dict:
    clean = df.apply(pd.to_numeric, errors="coerce").dropna()
    window = clean[(clean["year"] >= start_year) & (clean["year"] <= end_year)].copy()
    if window.shape[0] < 3:
        raise ValueError("Select a range with at least three data points.")

    years = window["year"].to_numpy(dtype=float)
    values = window["value"].to_numpy(dtype=float)
    slope, intercept = np.polyfit(years, values, 1)
    fitted = slope * years + intercept
    residual = values - fitted
    r2 = 1 - float(np.sum(residual ** 2) / np.sum((values - values.mean()) ** 2))

    start_value = float(values[0])
    end_value = float(values[-1])
    net_change = end_value - start_value
    peak_idx = int(np.argmax(values))
    trough_idx = int(np.argmin(values))
    volatility = float(np.std(np.diff(values))) if len(values) > 2 else 0.0
    direction = "warming" if net_change > 0 else "cooling" if net_change < 0 else "flat"

    allowed_numbers = [
        round(start_value, 3),
        round(end_value, 3),
        round(net_change, 3),
        round(float(slope), 5),
        int(window.iloc[0]["year"]),
        int(window.iloc[-1]["year"]),
        round(float(values[peak_idx]), 3),
        int(years[peak_idx]),
        round(float(values[trough_idx]), 3),
        int(years[trough_idx]),
    ]

    return {
        "location": location,
        "dataset": meta,
        "start_year": int(window.iloc[0]["year"]),
        "end_year": int(window.iloc[-1]["year"]),
        "points": int(window.shape[0]),
        "start_value": round(start_value, 3),
        "end_value": round(end_value, 3),
        "net_change": round(net_change, 3),
        "trend_per_year": round(float(slope), 5),
        "trend_per_decade": round(float(slope) * 10, 4),
        "peak": {"year": int(years[peak_idx]), "value": round(float(values[peak_idx]), 3)},
        "trough": {"year": int(years[trough_idx]), "value": round(float(values[trough_idx]), 3)},
        "volatility": round(volatility, 4),
        "r2": round(max(0.0, min(1.0, r2)), 3),
        "direction": direction,
        "allowed_numbers": allowed_numbers,
        "series": [{"year": int(y), "value": round(float(v), 3)} for y, v in zip(years, values)],
        "trend": [{"year": int(y), "value": round(float(v), 3)} for y, v in zip(years, fitted)],
    }


def climate_mood(label: str) -> dict:
    text = label.lower()
    if any(k in text for k in ["sea", "ocean", "tide", "sst", "water"]):
        return {"element": "water", "metaphor": "the waterline moving through memory", "accent": "blue"}
    if any(k in text for k in ["air", "aqi", "pm", "smog"]):
        return {"element": "air", "metaphor": "a pressure in the breath", "accent": "amber"}
    if any(k in text for k in ["co2", "carbon"]):
        return {"element": "carbon", "metaphor": "weight gathering in the sky", "accent": "violet"}
    return {"element": "heat", "metaphor": "heat entering the calendar", "accent": "red"}


def build_fallback_story(facts: dict, tone: str, length: str) -> str:
    mood = climate_mood(facts["dataset"]["label"])
    loc = facts["location"]
    unit = facts["dataset"]["unit"]
    fast = abs(facts["trend_per_decade"]) > 0.12
    tense = "urgent" if fast else "quiet but persistent"
    style = {
        "Scientific": "The record is plain",
        "Balanced": "The record has become a kind of local witness",
        "Mythic": "The old stories would call this an omen",
    }.get(tone, "The record has become a kind of local witness")

    paragraphs = [
        (
            f"{style}: between {facts['start_year']} and {facts['end_year']}, "
            f"{facts['dataset']['value_label']} near {loc} moved from "
            f"{facts['start_value']} to {facts['end_value']} {unit}. The net change is "
            f"{facts['net_change']} {unit}, and the fitted trend rises by "
            f"{facts['trend_per_decade']} {unit} per decade."
        ),
        (
            f"The highest point in this selected record is {facts['peak']['value']} {unit} "
            f"in {facts['peak']['year']}; the lowest is {facts['trough']['value']} {unit} "
            f"in {facts['trough']['year']}. That span gives the tale its shape: not a loose mood, "
            f"but {facts['points']} measurements arranged into a {tense} signal."
        ),
        (
            f"For {loc}, the metaphor is {mood['metaphor']}. It does not replace the science; "
            f"it gives the numbers somewhere human to land. A value can sit in a table forever, "
            f"but a change of {facts['net_change']} {unit} asks what daily life must now learn to notice."
        ),
    ]
    if length == "Long":
        paragraphs.append(
            f"The evidence panel is the anchor: every number in this story is visible beside the chart, "
            f"and the source is named before the prose begins. Tide Tales is most useful when it lets wonder "
            f"and accountability stand in the same room."
        )
    return "\n\n".join(paragraphs)


def _call_claude(client, prompt: str, max_tokens: int) -> str:
    response = client.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def _build_prompt(facts: dict, tone: str, length: str, language: str) -> str:
    length_instructions = (
        "- Write 300 to 500 words.\n"
        "- Use flowing prose, no section headings."
        if length != "Long" else
        "- Write 1000 to 1500 words.\n"
        "- Use section headings to structure the narrative.\n"
        "- Build a clear narrative arc: opening, development, significance, conclusion.\n"
        "- Explain what the trends mean for people living in this location."
    )
    return f"""Write a grounded climate data narrative for a public audience.

Rules:
- Use only the facts provided in the JSON below.
- Do not invent numbers, sources, impacts, deaths, policy claims, or local folklore.
- Mention the dataset source exactly once.
- Keep it vivid and verifiable.
- Finish the narrative completely. Never stop mid-sentence or mid-section.
- If token space is limited, shorten the story. Never end mid-sentence.
- End with a clear concluding paragraph.
- Write entirely in {language}.
- Use natural, native-level prose — do not translate English sentence structures literally.
- Preserve all numbers, dataset names, and source citations as-is.
- Tone: {tone}

Length:
{length_instructions}

FACTS:
{json.dumps({k: v for k, v in facts.items() if k not in ["series", "trend"]}, indent=2)}
"""


def _infer_vernacular(location: str, client) -> str | None:
    """
    Ask Claude what the dominant local language is for a location, even if
    that's the country's main national language (e.g. Japanese for Tokyo,
    Mandarin for Beijing) rather than only a regional minority language.
    Returns the language name, or None if English is the dominant language
    or no location was given.
    """
    if not location or not location.strip():
        return None
    try:
        response = client.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            max_tokens=VERNACULAR_INFER_MAX_TOKENS,
            messages=[{
                "role": "user",
                "content": (
                    f"What is the dominant everyday spoken language in '{location}'? "
                    "This includes the country's main national language if that's what "
                    "most residents speak day to day (e.g. Japanese for Tokyo, Mandarin "
                    "for Beijing, Tamil for Chennai) — not just minority regional languages. "
                    "Reply with ONLY the language name in English (e.g. 'Japanese', "
                    "'Mandarin Chinese', 'Tamil', 'Odia'). "
                    "If English is the dominant everyday language there (e.g. London, "
                    "New York, Sydney), or the location is unrecognized/ambiguous, "
                    "reply with exactly: none"
                ),
            }],
        )
        result = response.content[0].text.strip()
        if not result or result.lower() == "none":
            return None
        return result
    except Exception as e:
        print(f"CLAUDE VERNACULAR INFERENCE ERROR: {e}")
        return None


def build_ai_story(facts: dict, tone: str, length: str, api_key: str) -> str:
    if not api_key or anthropic is None:
        return build_fallback_story(facts, tone, length)

    try:
        client = anthropic.Anthropic(api_key=api_key, timeout=90.0)
        vernacular = _infer_vernacular(facts.get("location", ""), client)

        base_tokens = MAX_TOKENS.get(length, MAX_TOKENS["Short"])
        vernacular_tokens = int(base_tokens * VERNACULAR_TOKEN_MULTIPLIER)

        if not vernacular:
            return _call_claude(
                client, _build_prompt(facts, tone, length, "English"), base_tokens
            )

        # Run the English and vernacular calls in parallel, as two fully
        # separate Claude requests, to halve wall-clock time. Each gets its
        # own prompt and its own token budget — the vernacular call gets
        # extra headroom since non-Latin scripts tokenize more densely.
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            english_future = executor.submit(
                _call_claude, client, _build_prompt(facts, tone, length, "English"), base_tokens
            )
            vernacular_future = executor.submit(
                _call_claude, client, _build_prompt(facts, tone, length, vernacular), vernacular_tokens
            )
            english_story = english_future.result()
            vernacular_story = vernacular_future.result()

        return english_story + STORY_DELIMITER + vernacular_story

    except Exception as e:
        # Covers anthropic.APITimeoutError and everything else - always fall back
        # rather than letting a 500 reach the frontend.
        print(f"CLAUDE ERROR: {e}")
        return build_fallback_story(facts, tone, length)


def save_run(facts: dict, story: str) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            """
            INSERT INTO runs (
                created_at, dataset_label, location, start_year, end_year, facts_json, story
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.utcnow().isoformat(timespec="seconds") + "Z",
                facts["dataset"]["label"],
                facts["location"],
                facts["start_year"],
                facts["end_year"],
                json.dumps({k: v for k, v in facts.items() if k not in ["series", "trend"]}),
                story,
            ),
        )
        return int(cur.lastrowid)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/default-data")
def default_data():
    df = load_default_data()
    meta = DATASET_META["nasa_gistemp"]
    return jsonify(
        {
            "meta": meta,
            "min_year": int(df["year"].min()),
            "max_year": int(df["year"].max()),
            "series": df.to_dict(orient="records"),
        }
    )


@app.route("/api/upload", methods=["POST"])
def upload():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No CSV file supplied."}), 400
        df, meta = normalize_uploaded_csv(request.files["file"])
        return jsonify(
            {
                "meta": meta,
                "min_year": int(df["year"].min()),
                "max_year": int(df["year"].max()),
                "series": df.to_dict(orient="records"),
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/analyze", methods=["POST"])
def analyze():
    try:
        payload = request.get_json(force=True)
        meta = payload.get("meta") or DATASET_META["nasa_gistemp"]
        df = pd.DataFrame(payload["series"])
        facts = compute_facts(
            df,
            int(payload["start_year"]),
            int(payload["end_year"]),
            meta,
            payload.get("location") or "Bhubaneswar, India",
        )
        story = build_ai_story(
            facts,
            payload.get("tone") or "Balanced",
            payload.get("length") or "Short",
            os.environ.get("ANTHROPIC_API_KEY", ""),
        )
        run_id = save_run(facts, story)
        return jsonify({"run_id": run_id, "facts": facts, "story": story})
    except Exception as exc:
        print(f"ANALYZE ERROR: {exc}")
        return jsonify({"error": str(exc)}), 400


@app.route("/api/facts", methods=["POST"])
def facts_only():
    try:
        payload = request.get_json(force=True)
        meta = payload.get("meta") or DATASET_META["nasa_gistemp"]
        df = pd.DataFrame(payload["series"])
        facts = compute_facts(
            df,
            int(payload["start_year"]),
            int(payload["end_year"]),
            meta,
            payload.get("location") or "Bhubaneswar, India",
        )
        return jsonify({"facts": facts})
    except Exception as exc:
        print(f"FACTS ERROR: {exc}")
        return jsonify({"error": str(exc)}), 400


@app.route("/api/history")
def history():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, created_at, dataset_label, location, start_year, end_year
                FROM runs ORDER BY id DESC LIMIT 20
                """
            ).fetchall()
        return jsonify([dict(row) for row in rows])
    except Exception as exc:
        print(f"HISTORY ERROR: {exc}")
        return jsonify({"error": str(exc)}), 400


init_db()
ensure_fallback_data()
if __name__ == "__main__":
    app.run(debug=True, port=5001)
