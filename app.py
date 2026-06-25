import pandas as pd
import streamlit as st
import os


TEAM_COLUMNS = ["Team", "Owner", "Role", "Player"]
TRANSACTION_COLUMNS = ["Date", "Owner 1", "Owner 2", "Description", "WAR Adjustment"]


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

    df = pd.DataFrame(
        [{"Player": k, "WAR": v} for k, v in combined.items()]
    ).sort_values("WAR", ascending=False, ignore_index=True)

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
        player = str(row["Player"]).strip()

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
    return df.set_index("Player")["WAR"].to_dict()


def lookup_player_war(name: str, war_map: dict[str, float]) -> float:
    return round(war_map.get(name, 0.0), 1)


def team_player_rows(player_names: list[str], war_map: dict[str, float]) -> list[dict[str, object]]:
    return [
        {"Player": name, "WAR": lookup_player_war(name, war_map)}
        for name in player_names
    ]


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
            "Adjustment": summary["Adjustment"],
            "Total WAR": summary["Total WAR"],
        }
        for team_name, team_data in teams.items()
        for summary in [team_summary(team_name, team_data, war_map, adjustments)]
    ]
    df = pd.DataFrame(rows).sort_values("Starter WAR", ascending=False, ignore_index=True)
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
    st.dataframe(pd.DataFrame(summary["Starter Rows"]), width="stretch")
    st.write("Reserve roster")
    st.dataframe(pd.DataFrame(summary["Reserve Rows"]), width="stretch")
    st.markdown(
        f"Starter WAR: {summary['Starter WAR']}   |   Reserve WAR: {summary['Reserve WAR']}   |   Adjustment: {summary['Adjustment']}   |   Total WAR: {summary['Total WAR']}"
    )


def load_transactions() -> pd.DataFrame:
    transactions_file = "transactions.csv"
    if os.path.exists(transactions_file):
        return pd.read_csv(transactions_file)
    return pd.DataFrame(columns=TRANSACTION_COLUMNS)


def render_summary_metrics(summary_df: pd.DataFrame, unmatched_count: int, transactions_df: pd.DataFrame) -> None:
    leader = summary_df.iloc[0] if not summary_df.empty else None
    last_transaction = "None"
    if not transactions_df.empty and "Date" in transactions_df.columns:
        dates = pd.to_datetime(transactions_df["Date"], errors="coerce").dropna()
        if not dates.empty:
            last_transaction = dates.max().strftime("%Y-%m-%d")

    cols = st.columns(5)
    cols[0].metric("Leader", leader["Team"] if leader is not None else "None")
    cols[1].metric("Starter WAR", f"{leader['Starter WAR']:.1f}" if leader is not None else "0.0")
    cols[2].metric("League WAR", f"{summary_df['Total WAR'].sum():.1f}" if not summary_df.empty else "0.0")
    cols[3].metric("Unmatched", unmatched_count)
    cols[4].metric("Last Move", last_transaction)


st.set_page_config(page_title="WAR League Scorebook", layout="wide")
st.title("WAR League Scorebook")

scores_df = build_scores()
war_map = player_war_map(scores_df)
teams = load_teams()
transactions_df = load_transactions()
adjustments = transaction_adjustments(transactions_df)
unmatched_players = unmatched_roster_players(teams, war_map)

team_tab, leaderboard_tab, transactions_tab = st.tabs(["Fantasy Teams", "Leaderboard", "Transactions"])

with team_tab:
    st.subheader("Fantasy team standings")
    summary_df = build_team_summary_df(teams, war_map, adjustments)
    render_summary_metrics(summary_df, len(unmatched_players), transactions_df)

    if unmatched_players:
        with st.expander("Roster names not found in WAR data", expanded=True):
            st.dataframe(pd.DataFrame(unmatched_players), width="stretch")

    st.dataframe(summary_df, width="stretch")
    for team_name, team_data in teams.items():
        with st.expander(team_name, expanded=False):
            render_team(team_name, team_data, war_map, adjustments)

with leaderboard_tab:
    query = st.text_input("Search player (partial match):", value="", key="leaderboard_query")
    if query.strip():
        mask = scores_df["Player"].str.contains(query, case=False, na=False)
        results = scores_df[mask]
        st.subheader(f"Matches for: {query}")
        st.dataframe(results, width="stretch")
    else:
        st.subheader("Leaderboard")
        st.dataframe(scores_df, width="stretch")

    st.download_button(
        "Download CSV",
        data=scores_df.to_csv(index=False).encode("utf-8"),
        file_name="morescore.csv",
        mime="text/csv",
    )

with transactions_tab:
    st.subheader("Transaction Log")
    st.info("Transactions are managed via the transactions.csv file. WAR Adjustment is applied to Owner 1 in the standings.")

    if not transactions_df.empty:
        st.dataframe(transactions_df, width="stretch")
        
        csv = transactions_df.to_csv(index=False)
        st.download_button(
            "Download Transaction Log",
            data=csv.encode("utf-8"),
            file_name="transactions.csv",
            mime="text/csv",
        )
    else:
        st.info("No transactions logged yet")
