from __future__ import annotations

import re
from datetime import datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_URL = "https://clinicaltrials.gov/api/v2/studies"
PAGE_SIZE = 1000

ACTIVE_STATUSES = {"Recruiting", "Active Not Recruiting", "Enrolling By Invitation", "Not Yet Recruiting"}
PHASE_ORDER = ["Early Phase 1", "Phase 1", "Phase 1/2", "Phase 2", "Phase 2/3", "Phase 3", "Phase 4", "Not Applicable"]
LATE_STAGE = {"Phase 2/3", "Phase 3"}

PALETTE = ["#5B8DEF", "#36C5A8", "#F2B84B", "#E66B8A"]
SEQUENTIAL = ["#1A1F2B", "#2E4A7A", "#5B8DEF"]

SPONSOR_PRESETS = {
    "Johnson & Johnson": 'Janssen OR "Johnson & Johnson"',
    "Pfizer": "Pfizer",
    "Merck": '"Merck Sharp" OR "Merck & Co"',
    "AstraZeneca": "AstraZeneca",
    "Novartis": "Novartis",
    "Roche": '"Hoffmann-La Roche" OR Genentech',
    "Bristol Myers Squibb": "Bristol-Myers Squibb",
    "Eli Lilly": '"Eli Lilly"',
    "AbbVie": "AbbVie",
    "Amgen": "Amgen",
}

COMMON_CONDITIONS = [
    "Lung Cancer", "Breast Cancer", "Prostate Cancer", "Colorectal Cancer", "Multiple Myeloma",
    "Leukemia", "Lymphoma", "Melanoma", "Alzheimer Disease", "Parkinson Disease", "Depression",
    "Schizophrenia", "Multiple Sclerosis", "Type 2 Diabetes", "Obesity", "Heart Failure",
    "Hypertension", "Rheumatoid Arthritis", "Psoriasis", "Crohn Disease", "Ulcerative Colitis",
    "Asthma", "COPD", "HIV", "Hepatitis B", "COVID-19", "RSV", "Pulmonary Arterial Hypertension",
]

st.set_page_config(page_title="Clinical Trials Explorer", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 2.5rem; max-width: 1240px;}
    h1 {font-weight: 700; letter-spacing: -0.02em; margin-bottom: 0;}
    h4 {font-weight: 600; margin: 0.25rem 0 0.25rem 0;}
    [data-testid="stMetricLabel"] p {font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; opacity: 0.65;}
    [data-testid="stMetricValue"] {font-size: 1.75rem; font-weight: 600;}
    .stTabs [data-baseweb="tab"] {font-weight: 500;}
    .co-card {background:#1A1F2B; border-radius:10px; padding:16px 18px; border-top:3px solid var(--c); height:100%;}
    .co-name {font-size:0.82rem; letter-spacing:0.05em; text-transform:uppercase; opacity:0.7; margin-bottom:6px;}
    .co-big {font-size:2rem; font-weight:700; line-height:1.1;}
    .co-sub {font-size:0.78rem; opacity:0.6; margin-bottom:12px;}
    .co-grid {display:grid; grid-template-columns:1fr 1fr; gap:8px 16px; font-size:0.85rem;}
    .co-grid span {opacity:0.6; display:block; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.04em;}
    .co-grid b {font-weight:600;}
    .up {color:#36C5A8;} .down {color:#E66B8A;}
    .insight {background:#161B26; border-radius:10px; padding:14px 18px; margin-bottom:10px; border-left:3px solid #5B8DEF; font-size:0.95rem;}
    .kicker {font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em; opacity:0.55; margin-bottom:2px;}
    .kpi {background:#1A1F2B; border-radius:10px; padding:14px 18px; border-top:3px solid #5B8DEF;}
    .kpi .co-big {font-size:1.7rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_trials(condition: str, sponsor: str, keyword: str, max_studies: int) -> tuple[pd.DataFrame, int]:
    params = {"pageSize": min(PAGE_SIZE, max_studies), "countTotal": "true", "format": "json"}
    if condition:
        params["query.cond"] = condition
    if sponsor:
        params["query.spons"] = sponsor
    if keyword:
        params["query.term"] = keyword

    rows, total = [], 0
    while len(rows) < max_studies:
        resp = requests.get(API_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        total = data.get("totalCount", total)
        rows.extend(parse_study(s) for s in data.get("studies", []))
        token = data.get("nextPageToken")
        if not token:
            break
        params["pageToken"] = token

    return prep(pd.DataFrame(rows[:max_studies])), total


def parse_study(study: dict) -> dict:
    p = study.get("protocolSection", {})
    ident = p.get("identificationModule", {})
    status = p.get("statusModule", {})
    design = p.get("designModule", {})
    sponsor = p.get("sponsorCollaboratorsModule", {})
    conds = p.get("conditionsModule", {})
    locs = p.get("contactsLocationsModule", {}).get("locations", [])

    return {
        "NCT ID": ident.get("nctId"),
        "Title": ident.get("briefTitle"),
        "Status": status.get("overallStatus", "UNKNOWN"),
        "Phase": clean_phase(design.get("phases") or ["NA"]),
        "Start Date": status.get("startDateStruct", {}).get("date"),
        "Enrollment": design.get("enrollmentInfo", {}).get("count"),
        "Lead Sponsor": sponsor.get("leadSponsor", {}).get("name"),
        "Conditions": ", ".join(conds.get("conditions", [])),
        "Countries": sorted({loc.get("country") for loc in locs if loc.get("country")}),
        "Sites": len(locs),
    }


def clean_phase(phases: list[str]) -> str:
    if phases == ["NA"]:
        return "Not Applicable"
    if phases == ["EARLY_PHASE1"]:
        return "Early Phase 1"
    labels = [ph.replace("EARLY_PHASE1", "1").replace("PHASE", "") for ph in phases]
    return "Phase " + "/".join(labels)


def prep(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df["Status"] = df["Status"].map(lambda s: s.replace("_", " ").title() if isinstance(s, str) else s)
    df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
    df["Start Year"] = df["Start Date"].dt.year
    df["Enrollment"] = pd.to_numeric(df["Enrollment"], errors="coerce")
    return df


def autocomplete(container, label, options, default=None, placeholder="Start typing...", key=None):
    return container.selectbox(
        label, options, index=options.index(default) if default in options else None,
        placeholder=placeholder, accept_new_options=True, key=key,
    ) or ""


def style(fig, height=340, legend=False):
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=8, b=0),
        xaxis_title=None,
        yaxis_title=None,
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text=""),
        bargap=0.35,
    )
    fig.update_xaxes(showgrid=False)
    return fig


def section(title: str, note: str | None = None):
    st.markdown(f"#### {title}")
    if note:
        st.caption(note)


def metric_row(items: list[tuple[str, str]]):
    for col, (label, value) in zip(st.columns(len(items)), items):
        col.markdown(f'<div class="kpi"><div class="co-name">{label}</div><div class="co-big">{value}</div></div>',
                     unsafe_allow_html=True)
    st.write("")


def chart(fig, **kwargs):
    st.plotly_chart(style(fig, **kwargs), config={"displayModeBar": False})

def company_card(row, color):
    g = row["3-yr growth"]
    gtxt = "—" if pd.isna(g) else f'<b class="{"up" if g >= 0 else "down"}">{g:+.0f}%</b>'
    return f'''<div class="co-card" style="--c:{color}">
      <div class="co-name">{row["Company"]}</div>
      <div class="co-big">{row["Active"]:,}</div><div class="co-sub">active trials</div>
      <div class="co-grid">
        <div><span>Total</span><b>{row["Total trials"]:,}</b></div>
        <div><span>Late-stage active</span><b>{row["Late-stage active"]:,}</b></div>
        <div><span>3-yr growth</span>{gtxt}</div>
        <div><span>Countries</span><b>{row["Countries"]}</b></div>
      </div></div>'''

def insights_html(lines):
    return "".join('<div class="insight">' + re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", l) + "</div>" for l in lines)


def growth_rate(df: pd.DataFrame, recent: range, prior: range) -> float | None:
    r = df["Start Year"].isin(recent).sum()
    p = df["Start Year"].isin(prior).sum()
    return None if p == 0 else (r - p) / p * 100


def render_explorer():
    c1, c2, c3, c4 = st.columns([2, 2, 2, 1.2])
    condition = autocomplete(c1, "Condition", COMMON_CONDITIONS, default="Lung Cancer", key="cond")
    sponsor_pick = autocomplete(c2, "Sponsor", list(SPONSOR_PRESETS), placeholder="Any sponsor", key="spons")
    sponsor = SPONSOR_PRESETS.get(sponsor_pick, sponsor_pick)
    keyword = c3.text_input("Keyword", placeholder="e.g. immunotherapy")
    max_studies = c4.number_input("Max studies", 100, 5000, 1000, step=100)

    if not (condition or sponsor or keyword):
        st.info("Enter a condition, sponsor, or keyword to get started.")
        return

    try:
        with st.spinner("Loading trials..."):
            df, total = fetch_trials(condition.strip(), sponsor.strip(), keyword.strip(), int(max_studies))
    except requests.RequestException as e:
        st.error(f"Couldn't reach ClinicalTrials.gov: {e}")
        return

    if df.empty:
        st.warning("No trials matched that search. Try broadening it.")
        return

    with st.expander("Filters"):
        f1, f2 = st.columns(2)
        status_pick = f1.multiselect("Status", sorted(df["Status"].unique()))
        phase_pick = f2.multiselect("Phase", [p for p in PHASE_ORDER if p in set(df["Phase"])])
    if status_pick:
        df = df[df["Status"].isin(status_pick)]
    if phase_pick:
        df = df[df["Phase"].isin(phase_pick)]

    median = df["Enrollment"].median()
    metric_row([
        ("Matching trials", f"{total:,}"),
        ("Loaded", f"{len(df):,}"),
        ("Currently active", f"{df['Status'].isin(ACTIVE_STATUSES).sum():,}"),
        ("Median enrollment", f"{int(median):,}" if pd.notna(median) else "—"),
    ])

    left, right = st.columns(2, gap="large")
    with left:
        section("Trials by phase")
        phase_counts = df["Phase"].value_counts().reindex(PHASE_ORDER).dropna().reset_index()
        phase_counts.columns = ["Phase", "Trials"]
        chart(px.bar(phase_counts, x="Phase", y="Trials", color_discrete_sequence=PALETTE))
    with right:
        section("Trials by status")
        status_counts = df["Status"].value_counts().sort_values().reset_index()
        status_counts.columns = ["Status", "Trials"]
        chart(px.bar(status_counts, x="Trials", y="Status", orientation="h", color_discrete_sequence=PALETTE))

    left, right = st.columns(2, gap="large")
    with left:
        section("Trials started per year", "2000 onward")
        yearly = df.dropna(subset=["Start Year"]).groupby("Start Year").size().reset_index(name="Trials")
        yearly = yearly[yearly["Start Year"] >= 2000]
        chart(px.line(yearly, x="Start Year", y="Trials", color_discrete_sequence=PALETTE))
    with right:
        section("Top lead sponsors")
        top_sponsors = df["Lead Sponsor"].value_counts().head(10).sort_values().reset_index()
        top_sponsors.columns = ["Sponsor", "Trials"]
        chart(px.bar(top_sponsors, x="Trials", y="Sponsor", orientation="h", color_discrete_sequence=PALETTE))

    countries = df.explode("Countries").dropna(subset=["Countries"])
    if not countries.empty:
        section("Where trials run")
        country_counts = countries["Countries"].value_counts().reset_index()
        country_counts.columns = ["Country", "Trials"]
        fig = px.choropleth(country_counts, locations="Country", locationmode="country names",
                            color="Trials", color_continuous_scale=SEQUENTIAL)
        fig.update_geos(showframe=False, showcoastlines=False, projection_type="natural earth",
                        showland=True, landcolor="#1A1F2B", showcountries=True,
                        countrycolor="#0E1117", bgcolor="rgba(0,0,0,0)")
        chart(fig, height=420)

    section("Trial details")
    table = df.copy()
    table["Link"] = "https://clinicaltrials.gov/study/" + table["NCT ID"]
    table["Countries"] = table["Countries"].apply(lambda c: ", ".join(c[:5]) + ("…" if len(c) > 5 else ""))
    table["Start Date"] = table["Start Date"].dt.date
    cols = ["NCT ID", "Title", "Status", "Phase", "Start Date", "Enrollment", "Lead Sponsor", "Countries", "Link"]
    st.dataframe(table[cols], width="stretch", hide_index=True,
                 column_config={"Link": st.column_config.LinkColumn("Link", display_text="View")})
    st.download_button("Download CSV", table[cols].to_csv(index=False),
                       file_name="clinical_trials.csv", mime="text/csv")


def render_landscape():
    c1, c2, c3 = st.columns([2, 3, 1.2])
    area = autocomplete(c1, "Therapeutic area", COMMON_CONDITIONS, default="Lung Cancer", key="area")
    picks = c2.multiselect("Sponsors to compare", list(SPONSOR_PRESETS),
                           default=["Johnson & Johnson", "Pfizer", "Merck"], max_selections=4)
    per_sponsor = c3.number_input("Max per sponsor", 100, 3000, 1000, step=100)

    if not area or len(picks) < 2:
        st.info("Choose a therapeutic area and at least two sponsors.")
        return

    frames, totals = [], {}
    try:
        with st.spinner("Loading trials..."):
            for name in picks:
                df, total = fetch_trials(area.strip(), SPONSOR_PRESETS[name], "", int(per_sponsor))
                totals[name] = total
                if not df.empty:
                    frames.append(df.assign(Company=name))
    except requests.RequestException as e:
        st.error(f"Couldn't reach ClinicalTrials.gov: {e}")
        return

    if not frames:
        st.warning("None of these sponsors have trials in that area. Try a broader term.")
        return

    df = pd.concat(frames, ignore_index=True)
    companies = [p for p in picks if p in set(df["Company"])]
    colors = dict(zip(picks, PALETTE))

    this_year = datetime.now().year
    recent = range(this_year - 3, this_year)
    prior = range(this_year - 6, this_year - 3)
    recent_label = f"{recent.start}–{recent.stop - 1}"
    prior_label = f"{prior.start}–{prior.stop - 1}"

    rows = []
    for name in companies:
        d = df[df["Company"] == name]
        late = d["Phase"].isin(LATE_STAGE)
        active = d["Status"].isin(ACTIVE_STATUSES)
        rows.append({
            "Company": name,
            "Total trials": totals[name],
            "Active": int(active.sum()),
            "Late-stage": int(late.sum()),
            "Late-stage active": int((late & active).sum()),
            f"Started {recent_label}": int(d["Start Year"].isin(recent).sum()),
            "3-yr growth": growth_rate(d, recent, prior),
            "Countries": d.explode("Countries")["Countries"].nunique(),
        })
    score = pd.DataFrame(rows)

    lead_late = score.loc[score["Late-stage active"].idxmax()]
    lead_active = score.loc[score["Active"].idxmax()]
    lead_global = score.loc[score["Countries"].idxmax()]
    growth = score.dropna(subset=["3-yr growth"])

    lines = [
        f"**{lead_late['Company']}** has the deepest late-stage pipeline in {area.lower()}, "
        f"with {lead_late['Late-stage active']} active Phase 2/3 and Phase 3 trials.",
        f"**{lead_active['Company']}** has the most active trials overall ({lead_active['Active']}).",
        f"**{lead_global['Company']}** has the broadest footprint, running trials in {lead_global['Countries']} countries.",
    ]
    if not growth.empty:
        fast = growth.loc[growth["3-yr growth"].idxmax()]
        lines.append(
            f"**{fast['Company']}** has the strongest momentum: trial starts changed "
            f"{fast['3-yr growth']:+.0f}% in {recent_label} compared with {prior_label}."
        )

    for col, (_, row) in zip(st.columns(len(score)), score.iterrows()):
        col.markdown(company_card(row, colors[row["Company"]]), unsafe_allow_html=True)
    st.write("")
    section("Key takeaways")
    st.markdown(insights_html(lines), unsafe_allow_html=True)
    left, right = st.columns(2, gap="large")
    with left:
        section("Pipeline by phase")
        phase = df.groupby(["Phase", "Company"]).size().reset_index(name="Trials")
        phase = phase[phase["Phase"] != "Not Applicable"]
        chart(px.bar(phase, x="Phase", y="Trials", color="Company", barmode="group",
                     category_orders={"Phase": PHASE_ORDER, "Company": picks},
                     color_discrete_map=colors), legend=True)
    with right:
        section("Phase mix", "Share of each company's pipeline")
        mix = df[df["Phase"] != "Not Applicable"].groupby(["Company", "Phase"]).size().reset_index(name="Trials")
        mix["Share"] = mix["Trials"] / mix.groupby("Company")["Trials"].transform("sum") * 100
        fig = px.bar(mix, x="Share", y="Company", color="Phase", orientation="h",
                     category_orders={"Phase": PHASE_ORDER, "Company": companies[::-1]},
                     color_discrete_sequence=["#2E3A55", "#3D5A8C", "#4F78BD", "#5B8DEF", "#36C5A8", "#F2B84B", "#E66B8A"])
        fig.update_xaxes(ticksuffix="%", range=[0, 100])
        chart(fig, legend=True, height=340)
    left, right = st.columns(2, gap="large")
    with left:
        section("Momentum", "Trials started per year")
        yearly = (df[df["Start Year"].between(this_year - 10, this_year - 1)]
                  .groupby(["Start Year", "Company"]).size().reset_index(name="Trials"))
        chart(px.line(yearly, x="Start Year", y="Trials", color="Company",
                      category_orders={"Company": picks}, color_discrete_map=colors), legend=True)
    with right:
        section("Top countries")
        geo = df.explode("Countries").dropna(subset=["Countries"])
        top_countries = geo["Countries"].value_counts().head(6).index
        heat = (geo[geo["Countries"].isin(top_countries)]
                .groupby(["Company", "Countries"]).size().unstack(fill_value=0)
                .reindex(index=companies, columns=top_countries, fill_value=0))
        fig = px.imshow(heat, text_auto=True, aspect="auto", color_continuous_scale=SEQUENTIAL,
                        labels={"x": "", "y": "", "color": "Trials"})
        fig.update_coloraxes(showscale=False)
        chart(fig, height=80 + 60 * len(companies))
    st.caption(
        "Sponsor matching uses ClinicalTrials.gov's sponsor and collaborator search, so trials where a company "
        "is a collaborator are included. Growth compares trial start dates and excludes the current partial year."
    )


st.title("Clinical Trials Explorer")
st.caption("Live data from ClinicalTrials.gov")

landscape_tab, explore_tab = st.tabs(["Competitive Landscape", "Explore Trials"])
with landscape_tab:
    render_landscape()
with explore_tab:
    render_explorer()
