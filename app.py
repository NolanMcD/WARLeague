import pandas as pd
import streamlit as st
import os
import inspect
import subprocess
from html import escape


TEAM_COLUMNS = ["Team", "Owner", "Role", "Player"]
TRANSACTION_COLUMNS = ["Date", "Owner 1", "Owner 2", "Description", "WAR Adjustment"]
TEAM_COLOR_PALETTE = [
    "#d98f8f",
    "#e1b95f",
    "#a9c977",
    "#78bea8",
    "#7fb4e4",
    "#9d8fe1",
    "#dc8ab5",
    "#a99c8f",
    "#8dacbf",
    "#b8aa6f",
]


def show_dataframe(df: pd.DataFrame) -> None:
    if "width" in inspect.signature(st.dataframe).parameters:
        st.dataframe(df, width="stretch")
    else:
        st.dataframe(df, use_container_width=True)


def fix_encoding(name: str) -> str:
    try:
        return name.encode("ISO-8859-1").decode("UTF-8")
    except UnicodeError:
        return name


def load_bwar(path: str) -> dict[str, float]:
    data = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                fields = line.strip().split(",")
                if len(fields) < 3:
                    continue
                player_name = fields[1]
                try:
                    war = float(fields[2])
                    data[fix_encoding(player_name)] = war
                except ValueError:
                    continue  # Skip lines with invalid WAR values
    except FileNotFoundError:
        st.warning(f"bWAR file '{path}' not found. Using empty data.")
    except Exception as e:
        st.error(f"Error loading bWAR file: {e}")
    return data


def load_fwar(path: str) -> dict[str, float]:
    data = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                fields = line.strip().split("\t")
                if len(fields) < 7:
                    continue
                player_name = fields[0].replace('"', "")
                try:
                    war = float(fields[6].replace('"', ""))
                    data[fix_encoding(player_name)] = war
                except ValueError:
                    continue  # Skip lines with invalid WAR values
    except FileNotFoundError:
        st.warning(f"fWAR file '{path}' not found. Using empty data.")
    except Exception as e:
        st.error(f"Error loading fWAR file: {e}")
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

    df = pd.DataFrame([{"Player": k, "WAR": v} for k, v in combined.items()], columns=["Player", "WAR"])
    if not df.empty:
        df = df.sort_values("WAR", ascending=False, ignore_index=True)

    return df


@st.cache_data
def load_teams(path: str = "teams.csv") -> dict[str, dict[str, object]]:
    if not os.path.exists(path):
        st.error(f"Team file '{path}' not found.")
        return {}

    try:
        df = pd.read_csv(path)
    except Exception as e:
        st.error(f"Error loading team file: {e}")
        return {}

    missing_columns = [column for column in TEAM_COLUMNS if column not in df.columns]
    if missing_columns:
        st.error(f"Team file is missing columns: {', '.join(missing_columns)}")
        return {}

    teams: dict[str, dict[str, object]] = {}
    for _, row in df.dropna(subset=["Team", "Player"]).iterrows():
        team_name = str(row["Team"]).strip()
        owner = str(row["Owner"]).strip() if pd.notna(row["Owner"]) else team_name
        role = str(row["Role"]).strip().lower()
        player = fix_encoding(str(row["Player"]).strip())

        if not team_name or not player:
            continue

        team = teams.setdefault(team_name, {"owner": owner, "starters": [], "reserves": []})
        if role == "starter":
            team["starters"].append(player)
        elif role == "reserve":
            team["reserves"].append(player)
        else:
            st.warning(f"Skipping '{player}' on '{team_name}' because role '{role}' is not starter or reserve.")

    return teams


def player_war_map(df: pd.DataFrame) -> dict[str, float]:
    if df.empty or "Player" not in df.columns or "WAR" not in df.columns:
        return {}
    return df.set_index("Player")["WAR"].to_dict()


def lookup_player_war(name: str, war_map: dict[str, float]) -> float:
    return round(war_map.get(name, 0.0), 1)


def team_player_rows(player_names: list[str], war_map: dict[str, float]) -> list[dict[str, object]]:
    return [
        {"Player": name, "WAR": lookup_player_war(name, war_map)}
        for name in player_names
    ]


def build_player_team_map(teams: dict[str, dict[str, object]]) -> dict[str, str]:
    player_teams = {}
    for team_name, team_data in teams.items():
        for role in ("starters", "reserves"):
            for player in team_data[role]:
                player_teams[player] = team_name
    return player_teams


def build_team_color_map(teams: dict[str, dict[str, object]]) -> dict[str, str]:
    return {
        team_name: TEAM_COLOR_PALETTE[index % len(TEAM_COLOR_PALETTE)]
        for index, team_name in enumerate(teams.keys())
    }


def leaderboard_with_teams(scores_df: pd.DataFrame, player_teams: dict[str, str]) -> pd.DataFrame:
    leaderboard_df = scores_df.copy()
    leaderboard_df["Team"] = leaderboard_df["Player"].map(player_teams).fillna("")
    return leaderboard_df[["Player", "Team", "WAR"]]


def show_leaderboard(df: pd.DataFrame, team_colors: dict[str, str]) -> None:
    rows = []
    for _, row in df.iterrows():
        team = str(row["Team"])
        color = team_colors.get(team, "transparent")
        rows.append(
            "<tr style='background-color: {color};'>"
            "<td>{player}</td>"
            "<td>{team}</td>"
            "<td style='text-align: right;'>{war:.1f}</td>"
            "</tr>".format(
                color=color,
                player=escape(str(row["Player"])),
                team=escape(team),
                war=float(row["WAR"]),
            )
        )

    table_html = f"""
    <style>
        .leaderboard-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.95rem;
        }}
        .leaderboard-table th,
        .leaderboard-table td {{
            border-bottom: 1px solid rgba(49, 51, 63, 0.15);
            padding: 0.45rem 0.65rem;
        }}
        .leaderboard-table th {{
            background-color: #f6f7f9;
            color: #31333f;
            font-weight: 600;
            text-align: left;
        }}
    </style>
    <table class="leaderboard-table">
        <thead>
            <tr>
                <th>Player</th>
                <th>Team</th>
                <th style="text-align: right;">WAR</th>
            </tr>
        </thead>
        <tbody>{"".join(rows)}</tbody>
    </table>
    """
    st.markdown(table_html, unsafe_allow_html=True)


def transaction_adjustments(transactions_df: pd.DataFrame) -> dict[str, float]:
    if transactions_df.empty or "Owner 1" not in transactions_df.columns or "WAR Adjustment" not in transactions_df.columns:
        return {}

    df = transactions_df.copy()
    df["WAR Adjustment"] = pd.to_numeric(df["WAR Adjustment"], errors="coerce").fillna(0.0)
    adjustments = df.groupby("Owner 1")["WAR Adjustment"].sum().to_dict()
    return {str(owner): round(adjustment, 1) for owner, adjustment in adjustments.items()}


def unmatched_roster_players(teams: dict[str, dict[str, object]], war_map: dict[str, float]) -> list[dict[str, str]]:
    rows = []
    for team_name, team_data in teams.items():
        for role in ("starters", "reserves"):
            for player in team_data[role]:
                if player not in war_map:
                    rows.append({"Team": team_name, "Role": role[:-1].title(), "Player": player})
    return rows


def team_summary(
    team_name: str,
    team_data: dict[str, object],
    war_map: dict[str, float],
    adjustments: dict[str, float],
) -> dict[str, object]:
    starter_rows = team_player_rows(team_data["starters"], war_map)
    reserve_rows = team_player_rows(team_data["reserves"], war_map)
    starter_total = sum(row["WAR"] for row in starter_rows)
    reserve_total = sum(row["WAR"] for row in reserve_rows)
    adjustment = adjustments.get(team_name, adjustments.get(str(team_data["owner"]), 0.0))
    roster_total = starter_total + reserve_total
    return {
        "Team": team_name,
        "Starter WAR": round(starter_total, 1),
        "Reserve WAR": round(reserve_total, 1),
        "Roster WAR": round(roster_total, 1),
        "Adjustment": round(adjustment, 1),
        "Total WAR": round(roster_total + adjustment, 1),
        "Starter Rows": starter_rows,
        "Reserve Rows": reserve_rows,
    }


def build_team_summary_df(
    teams: dict[str, dict[str, object]],
    war_map: dict[str, float],
    adjustments: dict[str, float],
) -> pd.DataFrame:
    rows = [
        {
            "Team": summary["Team"],
            "Starter WAR": summary["Starter WAR"],
            "Reserve WAR": summary["Reserve WAR"],
            "Roster WAR": summary["Roster WAR"],
            "Total WAR": summary["Total WAR"],
        }
        for team_name, team_data in teams.items()
        for summary in [team_summary(team_name, team_data, war_map, adjustments)]
    ]
    df = pd.DataFrame(
        rows,
        columns=["Team", "Starter WAR", "Reserve WAR", "Roster WAR", "Total WAR"],
    )
    if not df.empty:
        df = df.sort_values("Starter WAR", ascending=False, ignore_index=True)
    df.index = df.index + 1
    return df


def render_team(
    team_name: str,
    team_data: dict[str, object],
    war_map: dict[str, float],
    adjustments: dict[str, float],
) -> None:
    summary = team_summary(team_name, team_data, war_map, adjustments)
    st.markdown(f"### {summary['Team']}")
    st.write("Starter roster")
    show_dataframe(pd.DataFrame(summary["Starter Rows"]))
    st.write("Reserve roster")
    show_dataframe(pd.DataFrame(summary["Reserve Rows"]))
    st.markdown(
        f"Starter WAR: {summary['Starter WAR']}   |   Reserve WAR: {summary['Reserve WAR']}   |   Total WAR: {summary['Total WAR']}"
    )


def load_transactions() -> pd.DataFrame:
    transactions_file = "transactions.csv"
    if os.path.exists(transactions_file):
        return pd.read_csv(transactions_file)
    return pd.DataFrame(columns=TRANSACTION_COLUMNS)


def last_update_date() -> str:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cs"],
            check=True,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        date = result.stdout.strip()
        if date:
            return date
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    try:
        return pd.Timestamp(os.path.getmtime(__file__), unit="s").strftime("%Y-%m-%d")
    except OSError:
        return "Unknown"


def render_summary_metrics(summary_df: pd.DataFrame, unmatched_count: int) -> None:
    leader = summary_df.iloc[0] if not summary_df.empty else None

    cols = st.columns(5)
    cols[0].metric("Leader", leader["Team"] if leader is not None else "None")
    cols[1].metric("Starter WAR", f"{leader['Starter WAR']:.1f}" if leader is not None else "0.0")
    cols[2].metric("League WAR", f"{summary_df['Total WAR'].sum():.1f}" if not summary_df.empty else "0.0")
    cols[3].metric("Unmatched", unmatched_count)
    cols[4].metric("Last Update", last_update_date())


st.set_page_config(page_title="WAR League Scorebook", layout="wide")
st.title("WAR League Scorebook")

scores_df = build_scores()
war_map = player_war_map(scores_df)
teams = load_teams()
player_teams = build_player_team_map(teams)
team_colors = build_team_color_map(teams)
transactions_df = load_transactions()
adjustments = transaction_adjustments(transactions_df)
unmatched_players = unmatched_roster_players(teams, war_map)

team_tab, leaderboard_tab, transactions_tab = st.tabs(["Fantasy Teams", "Leaderboard", "Transactions"])

with team_tab:
    st.subheader("Fantasy team standings")
    summary_df = build_team_summary_df(teams, war_map, adjustments)
    render_summary_metrics(summary_df, len(unmatched_players))

    if unmatched_players:
        with st.expander("Roster names not found in WAR data", expanded=True):
            show_dataframe(pd.DataFrame(unmatched_players))

    show_dataframe(summary_df)
    for team_name, team_data in teams.items():
        with st.expander(team_name, expanded=False):
            render_team(team_name, team_data, war_map, adjustments)

with leaderboard_tab:
    leaderboard_df = leaderboard_with_teams(scores_df, player_teams)
    query = st.text_input("Search player (partial match):", value="", key="leaderboard_query")
    if query.strip():
        mask = leaderboard_df["Player"].str.contains(query, case=False, na=False)
        results = leaderboard_df[mask]
        st.subheader(f"Matches for: {query}")
        show_leaderboard(results, team_colors)
    else:
        st.subheader("Leaderboard")
        show_leaderboard(leaderboard_df, team_colors)

    st.download_button(
        "Download CSV",
        data=leaderboard_df.to_csv(index=False).encode("utf-8"),
        file_name="morescore.csv",
        mime="text/csv",
    )

with transactions_tab:
    st.subheader("Transaction Log")
    st.info("Transactions are managed via the transactions.csv file. WAR Adjustment is applied to Owner 1 in the standings.")

    if not transactions_df.empty:
        show_dataframe(transactions_df)
        
        csv = transactions_df.to_csv(index=False)
        st.download_button(
            "Download Transaction Log",
            data=csv.encode("utf-8"),
            file_name="transactions.csv",
            mime="text/csv",
        )
    else:
        st.info("No transactions logged yet")
