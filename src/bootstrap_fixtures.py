import json
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

FLAG: dict[str, str] = {
    "Mexico": "🇲🇽", "USA": "🇺🇸", "United States": "🇺🇸", "Canada": "🇨🇦",
    "Argentina": "🇦🇷", "Brazil": "🇧🇷", "Colombia": "🇨🇴", "Uruguay": "🇺🇾",
    "Ecuador": "🇪🇨", "Venezuela": "🇻🇪", "Paraguay": "🇵🇾", "Bolivia": "🇧🇴",
    "Germany": "🇩🇪", "France": "🇫🇷", "Spain": "🇪🇸", "Portugal": "🇵🇹",
    "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Netherlands": "🇳🇱", "Belgium": "🇧🇪", "Croatia": "🇭🇷",
    "Denmark": "🇩🇰", "Switzerland": "🇨🇭", "Serbia": "🇷🇸", "Norway": "🇳🇴",
    "Sweden": "🇸🇪", "Poland": "🇵🇱", "Ukraine": "🇺🇦", "Austria": "🇦🇹",
    "Turkey": "🇹🇷", "Slovakia": "🇸🇰", "Hungary": "🇭🇺",
    "Czech Republic": "🇨🇿", "Czechia": "🇨🇿",
    "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "Romania": "🇷🇴",
    "Bosnia-Herzegovina": "🇧🇦", "Bosnia and Herzegovina": "🇧🇦",
    "Morocco": "🇲🇦", "Senegal": "🇸🇳", "Nigeria": "🇳🇬", "Ghana": "🇬🇭",
    "Egypt": "🇪🇬", "DR Congo": "🇨🇩", "Congo DR": "🇨🇩", "South Africa": "🇿🇦",
    "Ivory Coast": "🇨🇮", "Tunisia": "🇹🇳", "Cameroon": "🇨🇲",
    "Algeria": "🇩🇿", "Cape Verde Islands": "🇨🇻", "Cape Verde": "🇨🇻",
    "Japan": "🇯🇵", "South Korea": "🇰🇷", "Korea Republic": "🇰🇷",
    "Saudi Arabia": "🇸🇦", "Iran": "🇮🇷", "Australia": "🇦🇺",
    "Uzbekistan": "🇺🇿", "Iraq": "🇮🇶", "Jordan": "🇯🇴",
    "Qatar": "🇶🇦", "New Zealand": "🇳🇿",
    "Haiti": "🇭🇹", "Curaçao": "🇨🇼",
    "Costa Rica": "🇨🇷", "Panama": "🇵🇦", "Honduras": "🇭🇳",
}

FD_URL = "https://api.football-data.org/v4/competitions/WC/matches"


def map_api_response(api_data: dict) -> list[dict]:
    fixtures, counters = [], {}
    for match in api_data.get("matches", []):
        if match.get("stage") != "GROUP_STAGE":
            continue
        group_raw = match.get("group", "")
        group = group_raw.replace("GROUP_", "")
        if not group or len(group) != 1:
            continue
        team_a = match["homeTeam"]["name"]
        team_b = match["awayTeam"]["name"]
        counters[group] = counters.get(group, 0) + 1
        fixtures.append({
            "match_id": f"{group}{counters[group]}",
            "group": group,
            "phase": "group",
            "team_a": team_a,
            "team_b": team_b,
            "flag_a": FLAG.get(team_a, "🏳"),
            "flag_b": FLAG.get(team_b, "🏳"),
            "date": match["utcDate"][:10],
            "kickoff_utc": match["utcDate"],
            "venue": match.get("venue", ""),
            "status": "pending",
            "result": None,
            "api_id": match["id"],
        })
    return fixtures


def generate_ko_bracket() -> list[dict]:
    slots = []
    r32 = [("1A","2B"),("1B","2A"),("1C","2D"),("1D","2C"),("1E","2F"),("1F","2E"),
           ("1G","2H"),("1H","2G"),("1I","2J"),("1J","2I"),("1K","2L"),("1L","2K"),
           ("3rd_1","3rd_2"),("3rd_3","3rd_4"),("3rd_5","3rd_6"),("3rd_7","3rd_8")]
    r32_dates = ["2026-06-27"]*4 + ["2026-06-28"]*4 + ["2026-06-29"]*4 + ["2026-06-30"]*4
    r32_venues = ["New York/NJ","Los Angeles","Dallas","San Francisco",
                  "Seattle","Miami","Houston","Atlanta",
                  "Philadelphia","Kansas City","Boston","Toronto",
                  "Vancouver","Mexico City","Guadalajara","Monterrey"]
    for i, (sa, sb) in enumerate(r32, 1):
        slots.append({"match_id": f"R32_{i}", "group": None, "phase": "round_of_32",
                      "team_a": None, "team_b": None, "flag_a": None, "flag_b": None,
                      "slot_a": sa, "slot_b": sb,
                      "date": r32_dates[i-1], "venue": r32_venues[i-1],
                      "status": "pending", "result": None})
    r16_dates = ["2026-07-06","2026-07-06","2026-07-07","2026-07-07",
                 "2026-07-08","2026-07-08","2026-07-09","2026-07-09"]
    r16_venues = ["New York/NJ","Dallas","Los Angeles","Miami",
                  "San Francisco","Houston","Atlanta","Seattle"]
    for i in range(1, 9):
        slots.append({"match_id": f"R16_{i}", "group": None, "phase": "round_of_16",
                      "team_a": None, "team_b": None, "flag_a": None, "flag_b": None,
                      "slot_a": f"W_R32_{2*i-1}", "slot_b": f"W_R32_{2*i}",
                      "date": r16_dates[i-1], "venue": r16_venues[i-1],
                      "status": "pending", "result": None})
    for i in range(1, 5):
        slots.append({"match_id": f"QF_{i}", "group": None, "phase": "quarter_final",
                      "team_a": None, "team_b": None, "flag_a": None, "flag_b": None,
                      "slot_a": f"W_R16_{2*i-1}", "slot_b": f"W_R16_{2*i}",
                      "date": ["2026-07-11","2026-07-11","2026-07-12","2026-07-12"][i-1],
                      "venue": ["New York/NJ","Los Angeles","Dallas","Miami"][i-1],
                      "status": "pending", "result": None})
    for i in range(1, 3):
        slots.append({"match_id": f"SF_{i}", "group": None, "phase": "semi_final",
                      "team_a": None, "team_b": None, "flag_a": None, "flag_b": None,
                      "slot_a": f"W_QF_{2*i-1}", "slot_b": f"W_QF_{2*i}",
                      "date": ["2026-07-14","2026-07-15"][i-1],
                      "venue": ["New York/NJ","Dallas"][i-1],
                      "status": "pending", "result": None})
    slots.append({"match_id": "TP_1", "group": None, "phase": "third_place",
                  "team_a": None, "team_b": None, "flag_a": None, "flag_b": None,
                  "slot_a": "L_SF_1", "slot_b": "L_SF_2",
                  "date": "2026-07-18", "venue": "Miami",
                  "status": "pending", "result": None})
    slots.append({"match_id": "FIN_1", "group": None, "phase": "final",
                  "team_a": None, "team_b": None, "flag_a": None, "flag_b": None,
                  "slot_a": "W_SF_1", "slot_b": "W_SF_2",
                  "date": "2026-07-19", "venue": "New York/NJ",
                  "status": "pending", "result": None})
    return slots


def main(output_path: str = "data/fixtures.json") -> None:
    key = os.environ.get("FOOTBALL_DATA_KEY")
    if not key:
        print("ERROR: FOOTBALL_DATA_KEY not set.\nGet a free key at https://www.football-data.org and add it to .env")
        sys.exit(1)

    print("Fetching WM 2026 fixtures from football-data.org...")
    resp = requests.get(FD_URL,
                        params={"stage": "GROUP_STAGE"},
                        headers={"X-Auth-Token": key},
                        timeout=30)
    resp.raise_for_status()
    group_fixtures = map_api_response(resp.json())
    ko_fixtures = generate_ko_bracket()
    all_fixtures = group_fixtures + ko_fixtures

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(all_fixtures, indent=2, ensure_ascii=False))
    print(f"Written {len(group_fixtures)} group + {len(ko_fixtures)} KO slots → {output_path}")


if __name__ == "__main__":
    main()
