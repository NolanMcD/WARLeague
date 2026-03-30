import pandas as pd
import streamlit as st


def fix_encoding(name: str) -> str:
    try:
        return name.encode("ISO-8859-1").decode("UTF-8")
    except UnicodeError:
        return name


def load_bwar(path: str) -> dict[str, float]:
    data = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            fields = line.strip().split(",")
            if len(fields) < 3:
                continue
            player_name = fields[1]
            war = float(fields[2])
            data[fix_encoding(player_name)] = war
    return data


def load_fwar(path: str) -> dict[str, float]:
    data = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            fields = line.strip().split("\t")
            if len(fields) < 7:
                continue
            player_name = fields[0].replace('"', "")
            war = float(fields[6].replace('"', ""))
            data[fix_encoding(player_name)] = war
    return data


def add_dicts(dict1: dict[str, float], dict2: dict[str, float]) -> dict[str, float]:
    result = dict(dict1)
    for k, v in dict2.items():
        result[k] = result.get(k, 0.0) + v
    return result


def round_dict_values(d: dict[str, float], ndigits: int = 1) -> dict[str, float]:
    return {k: round(v, ndigits) for k, v in d.items()}


@st.cache_data
def build_scores() -> pd.DataFrame:
    b = load_bwar("bWAR.txt")
    f = load_fwar("fwar2.txt")
    combined = add_dicts(b, f)
    combined = round_dict_values(combined, 1)

    df = pd.DataFrame(
        [{"Player": k, "WAR": v} for k, v in combined.items()]
    ).sort_values("WAR", ascending=False, ignore_index=True)

    return df


TEAMS: dict[str, dict[str, object]] = {
    "Team 1": {
        "owner": "Owner 1",
        "starters": [
            "Player A1",
            "Player A2",
            "Player A3",
            "Player A4",
            "Player A5",
        ],
        "reserves": ["Player A6", "Player A7"],
    },
    "Team 2": {
        "owner": "Owner 2",
        "starters": [
            "Player B1",
            "Player B2",
            "Player B3",
            "Player B4",
            "Player B5",
        ],
        "reserves": ["Player B6", "Player B7"],
    },
    "Team 3": {
        "owner": "Owner 3",
        "starters": [
            "Player C1",
            "Player C2",
            "Player C3",
            "Player C4",
            "Player C5",
        ],
        "reserves": ["Player C6", "Player C7"],
    },
    "Team 4": {
        "owner": "Owner 4",
        "starters": [
            "Player D1",
            "Player D2",
            "Player D3",
            "Player D4",
            "Player D5",
        ],
        "reserves": ["Player D6", "Player D7"],
    },
    "Team 5": {
        "owner": "Owner 5",
        "starters": [
            "Player E1",
            "Player E2",
            "Player E3",
            "Player E4",
            "Player E5",
        ],
        "reserves": ["Player E6", "Player E7"],
    },
    "Team 6": {
        "owner": "Owner 6",
        "starters": [
            "Player F1",
            "Player F2",
            "Player F3",
            "Player F4",
            "Player F5",
        ],
        "reserves": ["Player F6", "Player F7"],
    },
    "Team 7": {
        "owner": "Owner 7",
        "starters": [
            "Player G1",
            "Player G2",
            "Player G3",
            "Player G4",
            "Player G5",
        ],
        "reserves": ["Player G6", "Player G7"],
    },
    "Team 8": {
        "owner": "Owner 8",
        "starters": [
            "Player H1",
            "Player H2",
            "Player H3",
            "Player H4",
            "Player H5",
        ],
        "reserves": ["Player H6", "Player H7"],
    },
    "Team 9": {
        "owner": "Owner 9",
        "starters": [
            "Player I1",
            "Player I2",
            "Player I3",
            "Player I4",
            "Player I5",
        ],
        "reserves": ["Player I6", "Player I7"],
    },
}


def player_war_map(df: pd.DataFrame) -> dict[str, float]:
    return df.set_index("Player")["WAR"].to_dict()


def lookup_player_war(name: str, war_map: dict[str, float]) -> float:
    return round(war_map.get(name, 0.0), 1)


def team_player_rows(player_names: list[str], war_map: dict[str, float]) -> list[dict[str, object]]:
    return [
        {"Player": name, "WAR": lookup_player_war(name, war_map)}
        for name in player_names
    ]


def team_summary(team_name: str, team_data: dict[str, object], war_map: dict[str, float]) -> dict[str, object]:
    starter_rows = team_player_rows(team_data["starters"], war_map)
    reserve_rows = team_player_rows(team_data["reserves"], war_map)
    starter_total = sum(row["WAR"] for row in starter_rows)
    reserve_total = sum(row["WAR"] for row in reserve_rows)
    return {
        "Team": team_name,
        "Owner": team_data["owner"],
        "Starter WAR": round(starter_total, 1),
        "Reserve WAR": round(reserve_total, 1),
        "Total WAR": round(starter_total + reserve_total, 1),
        "Starter Rows": starter_rows,
        "Reserve Rows": reserve_rows,
    }


def build_team_summary_df(war_map: dict[str, float]) -> pd.DataFrame:
    rows = [
        {
            "Team": summary["Team"],
            "Owner": summary["Owner"],
            "Starter WAR": summary["Starter WAR"],
            "Reserve WAR": summary["Reserve WAR"],
            "Total WAR": summary["Total WAR"],
        }
        for team_name, team_data in TEAMS.items()
        for summary in [team_summary(team_name, team_data, war_map)]
    ]
    return pd.DataFrame(rows).sort_values("Total WAR", ascending=False, ignore_index=True)


def render_team(team_name: str, team_data: dict[str, object], war_map: dict[str, float]) -> None:
    summary = team_summary(team_name, team_data, war_map)
    st.markdown(f"### {team_name}: {summary['Owner']}")
    st.write("**Starter roster**")
    st.dataframe(pd.DataFrame(summary["Starter Rows"]), use_container_width=True)
    st.write("**Reserve roster**")
    st.dataframe(pd.DataFrame(summary["Reserve Rows"]), use_container_width=True)
    st.markdown(
        f"**Starter WAR:** {summary['Starter WAR']}   |   **Reserve WAR:** {summary['Reserve WAR']}   |   **Total WAR:** {summary['Total WAR']}"
    )


st.set_page_config(page_title="WAR League Scorebook", layout="wide")
st.title("WAR League Scorebook")

scores_df = build_scores()
war_map = player_war_map(scores_df)

team_tab, leaderboard_tab = st.tabs(["Fantasy Teams", "Leaderboard"])

with team_tab:
    st.subheader("Fantasy team standings")
    summary_df = build_team_summary_df(war_map)
    st.dataframe(summary_df, use_container_width=True)
    st.markdown("---")
    for team_name, team_data in TEAMS.items():
        with st.expander(f"{team_name}: {team_data['owner']}", expanded=False):
            render_team(team_name, team_data, war_map)

with leaderboard_tab:
    query = st.text_input("Search player (partial match):", value="", key="leaderboard_query")
    if query.strip():
        mask = scores_df["Player"].str.contains(query, case=False, na=False)
        results = scores_df[mask]
        st.subheader(f"Matches for: {query}")
        st.dataframe(results, use_container_width=True)
    else:
        st.subheader("Leaderboard")
        st.dataframe(scores_df, use_container_width=True)

    st.download_button(
        "Download CSV",
        data=scores_df.to_csv(index=False).encode("utf-8"),
        file_name="morescore.csv",
        mime="text/csv",
    )
