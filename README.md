# 🌙 Traditional Astrology Calculator

A traditional (classical) natal chart calculator using **Swiss Ephemeris** for
sub-arcminute accuracy, validated against AstroSeek to within 0.01°.

Built from **William Lilly** (*Introduction to Astrology*) and **John Frawley**
(*The Horary Textbook*) — traditional rulerships, Regiomontanus houses, essential
dignities, receptions, antiscia, and Arabic Parts.

---

## Features

| Feature | Details |
|---|---|
| **Ephemeris** | pyswisseph (Swiss Ephemeris) — same engine as AstroSeek |
| **House system** | Regiomontanus (Frawley's explicit recommendation) |
| **Planets** | Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, North Node, Lilith |
| **Rulerships** | Traditional (Lilly) — Saturn rules Aquarius, Jupiter rules Pisces |
| **Essential dignities** | Domicile, Exaltation, Triplicity (day/night), Terms (Ptolemaic), Faces (Chaldean), Peregrine |
| **Debilities** | Detriment, Fall |
| **Aspects** | Conjunction, Opposition, Trine, Square, Sextile, Quincunx, Semi-sextile |
| **Antiscia** | Solstice points, conjunction/opposition by antiscion |
| **Arabic Parts** | Part of Fortune (day/night formula per Lilly) |
| **Chart image** | AstroSeek wheel, populated with locally-computed positions |
| **Geocoding** | Nominatim (OpenStreetMap) — no API key required |

---

## Local Setup

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/astrology-calculator.git
cd astrology-calculator

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## Deploy to Streamlit Cloud (free)

1. Push this repo to GitHub
2. Go to https://share.streamlit.io
3. Click **New app** → select your repo → `app.py`
4. Click **Deploy**

No secrets or API keys needed. All dependencies install automatically from `requirements.txt`.

> **Note on pyswisseph on Streamlit Cloud:** The Swiss Ephemeris built-in
> planetary data covers 1800–2400 AD without any extra files. Chiron requires
> the `seas_18.se1` asteroid file; it is omitted from this version for
> compatibility. Add it to a `/ephe/` folder and call `swe.set_ephe_path('ephe')`
> if you need it.

---

## Project Structure

```
astrology-calculator/
├── app.py              # Streamlit UI
├── engine.py           # Calculation engine (Swiss Ephemeris)
├── requirements.txt
├── .streamlit/
│   └── config.toml     # Dark theme
└── README.md
```

---

## Accuracy Validation

Test case: 1970-01-01 00:00 local time, Varna, Bulgaria (UTC+2)

| Planet | Our calc | AstroSeek | Diff |
|---|---|---|---|
| Sun | 280.071° | 280.07° | 0.001° |
| Moon | 189.655° | 189.65° | 0.005° |
| Mercury | 298.974° | 298.97° | 0.004° |
| Venus | 274.348° | 274.34° | 0.008° |
| Mars | 342.174° | 342.17° | 0.004° |
| Ascendant | 186.245° | 186.24° | 0.005° |
| MC | 97.407° | 97.40° | 0.007° |

---

## Roadmap

- [ ] LLM-powered interpretation (Groq free tier / GPT-4o-mini)
- [ ] Horary chart mode (radicality check per Lilly)
- [ ] Receptions table (mutual reception, mutual debility)
- [ ] Primary directions / profections
- [ ] PDF export
- [ ] Synastry / composite charts

---

## Sources

- William Lilly, *Introduction to Astrology* (1647)
- John Frawley, *The Horary Textbook* (2005)
- Swiss Ephemeris: https://www.astro.com/swisseph/
