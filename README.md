# Clinical Trials Explorer

An interactive dashboard for exploring clinical research trends using live data from the [ClinicalTrials.gov API](https://clinicaltrials.gov/data-api/api).

### Competitive Landscape
Pick a therapeutic area and 2–4 pharma sponsors (e.g. Johnson & Johnson vs. Pfizer vs. Merck) to see:

- An auto-generated **key takeaways** summary: who leads late-stage, who's growing fastest, who's most global
- A **scorecard** of total, active, and late-stage trials, plus 3-year growth in trial starts
- **Pipeline by phase** side by side
- **Momentum**: trials started per year over the last decade
- A **geography heatmap** of where each company runs trials

Sponsor presets map each company to its main trial-running entities (e.g. J&J → Janssen) so counts aren't undercounted.

### Explore Trials
Search by condition, sponsor, or keyword to see:

- Trial counts by **phase** and **status**
- **Trends** in trials started per year
- **Top lead sponsors** in a therapeutic area
- A **world map** of where trials run
- A searchable table of trials with links, exportable to CSV

**Live demo:** _add your Streamlit Cloud link here_

## Tech stack
Python · Streamlit · pandas · Plotly · REST API (ClinicalTrials.gov v2)

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## How it works
The app queries the ClinicalTrials.gov v2 `/studies` endpoint, follows `nextPageToken` pagination, and flattens each study's nested JSON (identification, status, design, sponsor, and location modules) into a pandas DataFrame. Results are cached for an hour to limit API calls.

## Ideas for next steps
- Track average time from start to completion by phase
- Add NLP topic clustering on trial titles
