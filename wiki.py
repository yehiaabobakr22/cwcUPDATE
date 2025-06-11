import requests
from bs4 import BeautifulSoup
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from zoneinfo import ZoneInfo
import json

# إعدادات Google Sheets
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1tszZet3ePbSkPM6YBsyBnZ3tmmHgA4YJPz86KTotFZs/edit#gid=0"

def clean_and_convert(raw_date, raw_time):
    raw_date = raw_date.split('(')[0].replace('\xa0', ' ').strip()
    raw_time = raw_time.replace('\xa0', ' ').strip()

    import re
    match = re.match(r"(\d{1,2}:\d{2}) (am|pm)([A-Z]{3})", raw_time, re.IGNORECASE)
    if match:
        time_str = match.group(1) + ' ' + match.group(2)
        tz_abbr = match.group(3)
    else:
        return "Invalid time format"

    dt_naive = datetime.strptime(f"{raw_date} {time_str}", "%B %d, %Y %I:%M %p")

    tz_map = {
        "EDT": "America/New_York",
        "EST": "America/New_York",
        "CDT": "America/Chicago",
        "PDT": "America/Los_Angeles",
        "PST": "America/Los_Angeles",
    }

    if tz_abbr not in tz_map:
        return "Unknown timezone"

    dt_local = dt_naive.replace(tzinfo=ZoneInfo(tz_map[tz_abbr]))
    dt_cairo = dt_local.astimezone(ZoneInfo("Africa/Cairo"))
    return dt_cairo.strftime("%Y-%m-%d %H:%M")

def fetch_and_send(json_data):
    try:
        creds = Credentials.from_service_account_info(json_data, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ])
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_url(SPREADSHEET_URL)
        sheet = spreadsheet.sheet1

        url = "https://en.wikipedia.org/wiki/2025_FIFA_Club_World_Cup#Schedule"
        res = requests.get(url)
        soup = BeautifulSoup(res.text, "html.parser")

        dates = [d.get_text(strip=True) for d in soup.find_all(class_="fdate")]
        times = [t.get_text(strip=True) for t in soup.find_all(class_="ftime")]
        home_teams = [h.get_text(strip=True) for h in soup.find_all(class_="fhome")]
        away_teams = [a.get_text(strip=True) for a in soup.find_all(class_="faway")]
        home_scores = [h.get_text(strip=True) for h in soup.find_all(class_="fhgoal")]
        away_scores = [a.get_text(strip=True) for a in soup.find_all(class_="fagoal")]

        num_matches = min(len(dates), len(times), len(home_teams), len(away_teams), len(home_scores), len(away_scores))
        if num_matches == 0:
            st.info("No matches found.")
            return

        data = []
        for i in range(num_matches):
            full_dt = clean_and_convert(dates[i], times[i])
            if full_dt == "Invalid time format" or full_dt == "Unknown timezone":
                match_date = dates[i]
                match_time = times[i]
            else:
                match_date, match_time = full_dt.split(" ")

            match_name = f"{home_teams[i]} vs {away_teams[i]}"
            row = [
                match_date,
                match_time,
                match_name,
                home_teams[i],
                away_teams[i],
                home_scores[i],
                away_scores[i]
            ]
            data.append(row)

        sheet.batch_clear(["B:H"])
        # إعداد الصفوف كاملة (العنوان + البيانات)
        all_rows = [
                       ["Match Date", "Match Time", "Match Name", "Home Team", "Away Team", "Home Score", "Away Score"]
                   ] + data

        # تحديث من B1 إلى H (حسب عدد الصفوف)
        end_row = len(all_rows)
        sheet.update(f"B1:H{end_row}", all_rows)

        st.success("Matches updated successfully!")
    except Exception as e:
        st.error(f"Error occurred: {e}")

# Streamlit UI
st.title("Club World Cup Scraper")
st.markdown("Upload your Google Service Account JSON to update matches to Google Sheets.")

uploaded_file = st.file_uploader("Upload Service Account JSON")

if uploaded_file:
    try:
        json_data = json.load(uploaded_file)
        if st.button("Update Matches"):
            fetch_and_send(json_data)
    except Exception as e:
        st.error(f"Invalid JSON file: {e}")
