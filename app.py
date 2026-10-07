import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from datetime import datetime

st.set_page_config(
    page_title="Low Scoring + HT Draw Finder",
    page_icon="⚽",
    layout="centered"
)

# ====================== CUSTOM CSS (Better Mobile Frontend) ======================
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    .stApp {
        max-width: 700px;
        margin: auto;
    }
    h1 {
        font-size: 1.6rem !important;
        text-align: center;
    }
    .match-card {
        background: #1e2130;
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 12px;
        border-left: 5px solid #00c853;
    }
    .league {
        font-size: 0.8rem;
        color: #aaa;
        margin-bottom: 4px;
    }
    .fixture {
        font-size: 1.15rem;
        font-weight: 600;
        margin-bottom: 6px;
    }
    .score {
        font-size: 0.95rem;
        color: #00e676;
    }
    .meta {
        font-size: 0.85rem;
        color: #bbb;
    }
</style>
""", unsafe_allow_html=True)

st.title("⚽ Low Scoring Fixtures")
st.caption("Defensive teams • Low scoring • Good for 0-0 / 1-1 / HT Draw")

# ====================== SETTINGS ======================
MIN_MATCHES = 8
MAX_RATIO = 1.05          # Goals scored/conceded ≤ matches played (slightly flexible)

# ====================== HELPER ======================
def get_soup(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36"
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            return BeautifulSoup(r.content, "html.parser")
    except:
        pass
    return None

def clean_num(text):
    try:
        return float(re.sub(r"[^\d.]", "", str(text)))
    except:
        return 0

# ====================== SCRAPER ======================
@st.cache_data(ttl=1800, show_spinner=False)
def scrape_matches():
    results = []

    leagues = [
        ("Serie A", "https://www.soccerstats.com/latest.asp?league=italy"),
        ("Ligue 1", "https://www.soccerstats.com/latest.asp?league=france"),
        ("La Liga", "https://www.soccerstats.com/latest.asp?league=spain"),
        ("Bundesliga", "https://www.soccerstats.com/latest.asp?league=germany"),
        ("Premier League", "https://www.soccerstats.com/latest.asp?league=england"),
        ("Eredivisie", "https://www.soccerstats.com/latest.asp?league=netherlands"),
        ("Primeira Liga", "https://www.soccerstats.com/latest.asp?league=portugal"),
        ("Championship", "https://www.soccerstats.com/latest.asp?league=england2"),
        ("Serie B", "https://www.soccerstats.com/latest.asp?league=italy2"),
    ]

    for league_name, url in leagues:
        soup = get_soup(url)
        if not soup:
            continue

        # Extract team stats
        team_data = {}
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) < 7:
                    continue
                team = cols[0].get_text(strip=True)
                if len(team) < 3:
                    continue
                try:
                    mp = clean_num(cols[1].get_text())
                    gf = clean_num(cols[5].get_text())
                    ga = clean_num(cols[6].get_text())
                    if mp >= MIN_MATCHES:
                        team_data[team] = {
                            "mp": mp,
                            "gf": gf,
                            "ga": ga,
                            "gf_r": gf / mp,
                            "ga_r": ga / mp
                        }
                except:
                    continue

        # Look for match fixtures on the page
        for a in soup.find_all("a", href=True):
            text = a.get_text(" ", strip=True)
            if " vs " in text or " - " in text:
                parts = re.split(r"\s+vs\s+|\s+-\s+", text, flags=re.IGNORECASE)
                if len(parts) == 2:
                    home = parts[0].strip()
                    away = parts[1].strip()

                    h = team_data.get(home)
                    a_ = team_data.get(away)

                    if h and a_:
                        # Core filter you requested
                        if (h["gf_r"] <= MAX_RATIO and h["ga_r"] <= MAX_RATIO and
                            a_["gf_r"] <= MAX_RATIO and a_["ga_r"] <= MAX_RATIO):

                            combined_gpg = (h["gf"] + a_["gf"] + h["ga"] + a_["ga"]) / (h["mp"] + a_["mp"])
                            low_score = max(0, round(100 - (combined_gpg * 38), 1))

                            results.append({
                                "league": league_name,
                                "fixture": f"{home} vs {away}",
                                "low_score": low_score,
                                "gpg": round(combined_gpg, 2),
                                "home_stats": f"{h['gf']:.0f}/{h['mp']:.0f} • {h['ga']:.0f} GA",
                                "away_stats": f"{a_['gf']:.0f}/{a_['mp']:.0f} • {a_['ga']:.0f} GA"
                            })

        time.sleep(1.1)

    # Clean & sort
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.drop_duplicates(subset=["fixture"])
        df = df.sort_values("low_score", ascending=False)
    return df

# ====================== UI ======================
with st.spinner("Scraping latest data... (15-25 seconds)"):
    df = scrape_matches()

if df is None or df.empty:
    st.warning("No strong matches found right now.")
    st.info("The sites may be temporarily blocking requests. Try again in a few minutes.")
else:
    st.success(f"Found {len(df)} matching fixtures")

    for _, row in df.iterrows():
        st.markdown(f"""
        <div class="match-card">
            <div class="league">{row['league']}</div>
            <div class="fixture">{row['fixture']}</div>
            <div class="score">Low Scoring Score: {row['low_score']} &nbsp;|&nbsp; Combined GPG: {row['gpg']}</div>
            <div class="meta">
                Home: {row['home_stats']}<br>
                Away: {row['away_stats']}
            </div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")
st.caption("Only showing teams where Goals Scored & Goals Conceded ≤ Matches Played. Higher score = better for 0-0 / 1-1 / HT Draw.")
