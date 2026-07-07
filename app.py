import pandas as pd
import streamlit as st
import os
import inspect
import subprocess
import re
from datetime import date
from html import escape
from typing import Optional


TEAM_COLUMNS = ["Team", "Owner", "Role", "Player"]
TRANSACTION_COLUMNS = ["Date", "Week", "Team", "Type", "Player Out", "Player In"]
TRANSACTION_TYPES = ["Promotion/Demotion", "Add/Drop"]
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


def apply_transaction_ownership(
    player_teams: dict[str, str],
    transactions_df: pd.DataFrame,
) -> dict[str, str]:
    updated_player_teams = dict(player_teams)
    roster_players = set(player_teams)
    if transactions_df.empty:
        return updated_player_teams

    df = transactions_df.copy()
    if "Date" in df.columns:
        parsed_dates = pd.to_datetime(df["Date"], errors="coerce")
    else:
        parsed_dates = pd.Series(pd.NaT, index=df.index)
    df["_Date Sort"] = parsed_dates.fillna(pd.Timestamp.min)
    df = df.sort_values(["_Date Sort", "Team"], kind="stable")

    for _, row in df.iterrows():
        team = str(row.get("Team", "")).strip()
        transaction_type = str(row.get("Type", "")).strip()
        player_out = fix_encoding(str(row.get("Player Out", "")).strip())
        player_in = fix_encoding(str(row.get("Player In", "")).strip())

        if not team:
            continue

        if transaction_type == "Add/Drop":
            if player_out not in roster_players and player_in not in roster_players:
                continue
            if player_out and updated_player_teams.get(player_out) == team:
                del updated_player_teams[player_out]
            if player_in:
                updated_player_teams[player_in] = team
        elif transaction_type == "Promotion/Demotion":
            if player_out not in roster_players and player_in not in roster_players:
                continue
            if player_out:
                updated_player_teams[player_out] = team
            if player_in:
                updated_player_teams[player_in] = team

    return updated_player_teams


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
    roster_total = starter_total + reserve_total
    return {
        "Team": team_name,
        "Starter WAR": round(starter_total, 1),
        "Reserve WAR": round(reserve_total, 1),
        "Roster WAR": round(roster_total, 1),
        "Adjustment": 0.0,
        "Total WAR": round(roster_total, 1),
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
        df = df.sort_values("Total WAR", ascending=False, ignore_index=True)
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
        try:
            df = pd.read_csv(transactions_file)
        except Exception as e:
            st.error(f"Error loading transaction file: {e}")
            return pd.DataFrame(columns=TRANSACTION_COLUMNS)

        if "Team" not in df.columns and "Owner 1" in df.columns:
            df["Team"] = df["Owner 1"]
        for column in TRANSACTION_COLUMNS:
            if column not in df.columns:
                df[column] = ""
        df = df[TRANSACTION_COLUMNS].fillna("")
        for column in TRANSACTION_COLUMNS:
            df[column] = df[column].astype(str).str.strip()
        if "Date" in df.columns:
            parsed_dates = pd.to_datetime(df["Date"], errors="coerce")
            derived_weeks = parsed_dates.dt.strftime("%G-W%V").fillna("")
            df["Week"] = df["Week"].where(df["Week"].astype(str).str.strip() != "", derived_weeks)
        return df[TRANSACTION_COLUMNS]
    return pd.DataFrame(columns=TRANSACTION_COLUMNS)


def load_team_rows(path: str = "teams.csv") -> pd.DataFrame:
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
        except Exception as e:
            st.error(f"Error loading team file: {e}")
            return pd.DataFrame(columns=TEAM_COLUMNS)
        for column in TEAM_COLUMNS:
            if column not in df.columns:
                df[column] = ""
        return df[TEAM_COLUMNS]
    return pd.DataFrame(columns=TEAM_COLUMNS)


def save_team_rows(df: pd.DataFrame, path: str = "teams.csv") -> None:
    df[TEAM_COLUMNS].to_csv(path, index=False)


def save_transactions(df: pd.DataFrame, path: str = "transactions.csv") -> None:
    clean_df = df[TRANSACTION_COLUMNS].fillna("")
    for column in TRANSACTION_COLUMNS:
        clean_df[column] = clean_df[column].astype(str).str.strip()
    clean_df.to_csv(path, index=False)


def current_week_key(today: Optional[date] = None) -> str:
    today = today or date.today()
    iso_year, iso_week, _ = today.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def transactions_this_week(transactions_df: pd.DataFrame, team_name: str, week_key: str) -> pd.DataFrame:
    if transactions_df.empty:
        return transactions_df
    df = transactions_df.copy()
    if "Week" not in df.columns:
        df["Week"] = ""
    if "Team" not in df.columns:
        df["Team"] = ""
    return df[(df["Team"].astype(str) == team_name) & (df["Week"].astype(str) == week_key)]


def transaction_data_issues(transactions_df: pd.DataFrame, teams: dict[str, dict[str, object]]) -> list[dict[str, str]]:
    issues = []
    if transactions_df.empty:
        return issues

    valid_teams = set(teams.keys())
    week_pattern = re.compile(r"^\d{4}-W\d{2}$")
    parsed_dates = pd.to_datetime(transactions_df["Date"], errors="coerce")

    for index, row in transactions_df.iterrows():
        row_number = str(index + 2)
        date_value = str(row.get("Date", "")).strip()
        week_value = str(row.get("Week", "")).strip()
        team_value = str(row.get("Team", "")).strip()
        type_value = str(row.get("Type", "")).strip()

        if not date_value:
            issues.append({"Row": row_number, "Issue": "Missing Date"})
        elif pd.isna(parsed_dates.iloc[index]):
            issues.append({"Row": row_number, "Issue": f"Invalid Date '{date_value}'"})

        if not week_value:
            issues.append({"Row": row_number, "Issue": "Missing Week; weekly limits may not work"})
        elif not week_pattern.match(week_value):
            issues.append({"Row": row_number, "Issue": f"Week should look like 2026-W28, found '{week_value}'"})

        if not team_value:
            issues.append({"Row": row_number, "Issue": "Missing Team; weekly limits may not work"})
        elif team_value not in valid_teams:
            issues.append({"Row": row_number, "Issue": f"Team '{team_value}' is not in teams.csv"})

        if type_value and type_value not in TRANSACTION_TYPES:
            issues.append({"Row": row_number, "Issue": f"Unknown Type '{type_value}'"})

    duplicate_rows = transactions_df[
        transactions_df["Team"].astype(str).str.strip().ne("")
        & transactions_df["Week"].astype(str).str.strip().ne("")
        & transactions_df.duplicated(["Team", "Week"], keep=False)
    ]
    for _, row in duplicate_rows.iterrows():
        issues.append({
            "Row": "Multiple",
            "Issue": f"{row['Team']} has more than one transaction logged for {row['Week']}",
        })

    return issues


def free_agent_options(scores_df: pd.DataFrame, player_teams: dict[str, str]) -> list[str]:
    if scores_df.empty:
        return []
    return [
        str(row["Player"])
        for _, row in scores_df.iterrows()
        if str(row["Player"]) not in player_teams
    ]


def format_player_option(player: str, war_map: dict[str, float]) -> str:
    return f"{player} ({lookup_player_war(player, war_map):.1f} WAR)"


def log_transaction(
    transactions_df: pd.DataFrame,
    team_name: str,
    transaction_type: str,
    player_out: str,
    player_in: str,
) -> pd.DataFrame:
    row = {
        "Date": date.today().isoformat(),
        "Week": current_week_key(),
        "Team": team_name,
        "Type": transaction_type,
        "Player Out": player_out,
        "Player In": player_in,
    }
    return pd.concat([transactions_df, pd.DataFrame([row])], ignore_index=True)


def transaction_summary(row: pd.Series) -> str:
    transaction_type = str(row.get("Type", "")).strip()
    player_out = str(row.get("Player Out", "")).strip()
    player_in = str(row.get("Player In", "")).strip()

    if transaction_type == "Promotion/Demotion":
        if player_in and player_out:
            return f"Promoted {player_in} and demoted {player_out}"
        return "Promotion/Demotion"
    if transaction_type == "Add/Drop":
        if player_in and player_out:
            return f"Added {player_in} and dropped {player_out}"
        return "Add/Drop"
    return transaction_type or "transaction"


def swap_starter_and_reserve(team_name: str, starter: str, reserve: str) -> None:
    df = load_team_rows()
    starter_mask = (
        (df["Team"].astype(str) == team_name)
        & (df["Role"].astype(str).str.lower() == "starter")
        & (df["Player"].map(lambda value: fix_encoding(str(value).strip())) == starter)
    )
    reserve_mask = (
        (df["Team"].astype(str) == team_name)
        & (df["Role"].astype(str).str.lower() == "reserve")
        & (df["Player"].map(lambda value: fix_encoding(str(value).strip())) == reserve)
    )
    df.loc[starter_mask, "Role"] = "reserve"
    df.loc[reserve_mask, "Role"] = "starter"
    save_team_rows(df)


def replace_reserve(team_name: str, dropped_player: str, added_player: str) -> None:
    df = load_team_rows()
    reserve_mask = (
        (df["Team"].astype(str) == team_name)
        & (df["Role"].astype(str).str.lower() == "reserve")
        & (df["Player"].map(lambda value: fix_encoding(str(value).strip())) == dropped_player)
    )
    df.loc[reserve_mask, "Player"] = added_player
    save_team_rows(df)


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
transactions_df = load_transactions()
player_teams = apply_transaction_ownership(build_player_team_map(teams), transactions_df)
team_colors = build_team_color_map(teams)
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
    st.caption("Each team can make one transaction per ISO week. Transactions update the roster file immediately.")
    transaction_issues = transaction_data_issues(transactions_df, teams)
    if transaction_issues:
        with st.expander("Transaction log issues", expanded=True):
            show_dataframe(pd.DataFrame(transaction_issues))

    if not transactions_df.empty:
        display_transactions = transactions_df.sort_values(["Date", "Team"], ascending=[False, True], ignore_index=True)
        show_dataframe(display_transactions)
        
        csv = transactions_df.to_csv(index=False)
        st.download_button(
            "Download Transaction Log",
            data=csv.encode("utf-8"),
            file_name="transactions.csv",
            mime="text/csv",
        )
    else:
        st.info("No transactions logged yet")

    st.divider()
    st.subheader("Make a Transaction")

    if not teams:
        st.warning("No teams are available.")
    else:
        week_key = current_week_key()
        selected_team = st.selectbox("Team", options=list(teams.keys()), key="transaction_team")
        selected_team_data = teams[selected_team]
        weekly_transactions = transactions_this_week(transactions_df, selected_team, week_key)
        transaction_used = not weekly_transactions.empty

        if transaction_used:
            last_move = weekly_transactions.iloc[-1]
            st.warning(
                f"{selected_team} has already used its transaction for {week_key}: "
                f"{transaction_summary(last_move)}"
            )
        else:
            st.success(f"{selected_team} has a transaction available for {week_key}.")

        transaction_type = st.radio(
            "Transaction type",
            options=TRANSACTION_TYPES,
            horizontal=True,
            key="transaction_type",
        )

        if transaction_type == "Promotion/Demotion":
            starters = list(selected_team_data["starters"])
            reserves = list(selected_team_data["reserves"])
            if not starters or not reserves:
                st.info("This team needs at least one starter and one reserve to swap players.")
            else:
                with st.form("promotion_demotion_form"):
                    starter = st.selectbox(
                        "Demote starter",
                        options=starters,
                        format_func=lambda player: format_player_option(player, war_map),
                    )
                    reserve = st.selectbox(
                        "Promote reserve",
                        options=reserves,
                        format_func=lambda player: format_player_option(player, war_map),
                    )
                    submitted = st.form_submit_button("Submit Promotion/Demotion", disabled=transaction_used)

                if submitted:
                    latest_transactions = load_transactions()
                    if not transactions_this_week(latest_transactions, selected_team, week_key).empty:
                        st.error(f"{selected_team} has already used its transaction for {week_key}.")
                        st.stop()
                    description = (
                        f"Promoted {reserve} ({lookup_player_war(reserve, war_map):.1f} WAR) "
                        f"and demoted {starter} ({lookup_player_war(starter, war_map):.1f} WAR)"
                    )
                    swap_starter_and_reserve(selected_team, starter, reserve)
                    updated_transactions = log_transaction(
                        latest_transactions,
                        selected_team,
                        "Promotion/Demotion",
                        starter,
                        reserve,
                    )
                    save_transactions(updated_transactions)
                    st.cache_data.clear()
                    st.success(description)
                    st.rerun()

        if transaction_type == "Add/Drop":
            reserves = list(selected_team_data["reserves"])
            free_agents = free_agent_options(scores_df, player_teams)
            if not reserves:
                st.info("This team has no reserve player available to drop.")
            elif not free_agents:
                st.info("No eligible free agents are available from the leaderboard.")
            else:
                with st.form("add_drop_form"):
                    dropped_player = st.selectbox(
                        "Drop reserve",
                        options=reserves,
                        format_func=lambda player: format_player_option(player, war_map),
                    )
                    added_player = st.selectbox(
                        "Add free agent",
                        options=free_agents,
                        format_func=lambda player: format_player_option(player, war_map),
                    )
                    submitted = st.form_submit_button("Submit Add/Drop", disabled=transaction_used)

                if submitted:
                    latest_transactions = load_transactions()
                    if not transactions_this_week(latest_transactions, selected_team, week_key).empty:
                        st.error(f"{selected_team} has already used its transaction for {week_key}.")
                        st.stop()
                    description = (
                        f"Added {added_player} ({lookup_player_war(added_player, war_map):.1f} WAR) "
                        f"and dropped {dropped_player} ({lookup_player_war(dropped_player, war_map):.1f} WAR)"
                    )
                    replace_reserve(selected_team, dropped_player, added_player)
                    updated_transactions = log_transaction(
                        latest_transactions,
                        selected_team,
                        "Add/Drop",
                        dropped_player,
                        added_player,
                    )
                    save_transactions(updated_transactions)
                    st.cache_data.clear()
                    st.success(description)
                    st.rerun()
