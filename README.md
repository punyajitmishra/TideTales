# Tide Tales

Tide Tales is a data-grounded climate story engine. It loads a climate time series, computes a transparent fact pack, renders the evidence as a chart, and generates a short narrative constrained to those facts.

## What it does

- Loads a built-in NASA GISTEMP-style fallback dataset for instant use.
- Accepts uploaded CSV files and auto-detects a year column plus a numeric value column.
- Computes start/end values, net change, trend, peak, trough, volatility, and trend fit.
- Shows a full evidence panel before and after generation.
- Generates a deterministic grounded narrative without an API key.
- Optionally uses Claude when `ANTHROPIC_API_KEY` is present.
- Saves recent runs to SQLite.
- Exports the fact pack as JSON and the story as text.

## Run locally

```bash
python -m pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5001`.

## CSV format

The uploader works best with one year/date-like column and one numeric measurement column.

Example:

```csv
year,value
2000,0.31
2001,0.44
2002,0.39
```

## Grounding model

The application computes the fact pack before any narrative is generated. The fallback narrative uses only those computed values. The optional Claude prompt sends only the fact pack and instructs the model not to invent numbers, sources, impacts, or local folklore.

## Limitations

The bundled dataset is a local fallback for development, not a live NASA download. Uploaded data is parsed heuristically, so unusual CSVs may need column names like `year`, `value`, `temperature`, `anomaly`, `sea_level`, or similar.
