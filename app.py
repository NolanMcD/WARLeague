import pandas as pd
import streamlit as st
import os
from datetime import datetime


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


TEAMS: dict[str, dict[str, object]] = {
    "Spence": {
        "owner": "Spence",
        "starters": [
            "Bobby Witt Jr.",
            "Garrett Crochet",
            "Ronald Acuña Jr.",
            "Roman Anthony",
            "Jeremy Peña",
        ],
        "reserves": ["Wilyer Abreu", "James Wood"],
    },
    "Mav": {
        "owner": "Mav",
        "starters": [
            "Shohei Ohtani",
            "Yoshinobu Yamamoto",
            "Wyatt Langford",
            "Jesús Luzardo",
            "Shea Langeliers",
        ],
        "reserves": ["Bryan Woo", "Willy Adames"],
    },
    "Kev": {
        "owner": "Kev",
        "starters": [
            "Paul Skenes",
            "Cristopher Sánchez",
            "Geraldo Perdomo",
            "Matt Olson",
            "Nico Hoerner",
        ],
        "reserves": ["Zach Neto", "Jackson Merrill"],
    },
    "Ben": {
        "owner": "Ben",
        "starters": [
            "Cal Raleigh",
            "José Ramírez",
            "Mookie Betts",
            "Logan Webb",
            "Kyle Schwarber",
        ],
        "reserves": ["Hunter Greene", "Colson Montgomery"],
    },
    "Aaron": {
        "owner": "Aaron",
        "starters": [
            "Juan Soto",
            "Nick Kurtz",
            "Corbin Carroll",
            "Max Fried",
            "Brice Turang",
        ],
        "reserves": ["Will Smith", "Kazuma Okamoto"],
    },
    "Nolan": {
        "owner": "Nolan",
        "starters": [
            "Aaron Judge",
            "Kyle Tucker",
            "Francisco Lindor",
            "Maikel Garcia",
            "Trea Turner",
        ],
        "reserves": ["Nolan McLean", "Chris Sale"],
    },
    "Emilio": {
        "owner": "Emilio",
        "starters": [
            "Gunnar Henderson",
            "Corey Seager",
            "Yordan Alvarez",
            "Elly De La Cruz",
            "Adley Rutschman",
        ],
        "reserves": ["Austin Riley", "Cole Ragans"],
    },
    "Gabe": {
        "owner": "Gabe",
        "starters": [
            "Julio Rodríguez",
            "Vladimir Guerrero Jr.",
            "Ketel Marte",
            "Matt Chapman",
            "Byron Buxton",
        ],
        "reserves": ["Freddy Peralta", "Mike Trout"],
    },
    "Bailey": {
        "owner": "Bailey",
        "starters": [
            "Fernando Tatis Jr.",
            "Tarik Skubal",
            "Junior Caminero",
            "Pete Crow-Armstrong",
            "Jazz Chisholm Jr.",
        ],
        "reserves": ["William Contreras", "Daulton Varsho"],
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
            "Starter WAR": summary["Starter WAR"],
            "Reserve WAR": summary["Reserve WAR"],
            "Total WAR": summary["Total WAR"],
        }
        for team_name, team_data in TEAMS.items()
        for summary in [team_summary(team_name, team_data, war_map)]
    ]
    df = pd.DataFrame(rows).sort_values("Starter WAR", ascending=False, ignore_index=True)
    df.index = df.index + 1
    return df


def render_team(team_name: str, team_data: dict[str, object], war_map: dict[str, float]) -> None:
    summary = team_summary(team_name, team_data, war_map)
    st.markdown(f"### ⚾ {summary['Team']}")
    st.write("**Starter roster**")
    st.dataframe(pd.DataFrame(summary["Starter Rows"]), width='stretch')
    st.write("**Reserve roster**")
    st.dataframe(pd.DataFrame(summary["Reserve Rows"]), width='stretch')
    st.markdown(
        f"**Starter WAR:** {summary['Starter WAR']}   |   **Reserve WAR:** {summary['Reserve WAR']}   |   **Total WAR:** {summary['Total WAR']}"
    )


def load_transactions() -> pd.DataFrame:
    transactions_file = "transactions.csv"
    if os.path.exists(transactions_file):
        return pd.read_csv(transactions_file)
    return pd.DataFrame(columns=["Date", "Owner 1", "Owner 2", "Description", "WAR Adjustment"])


st.set_page_config(page_title="WAR League Scorebook", layout="wide")
st.title("WAR League Scorebook")

scores_df = build_scores()
war_map = player_war_map(scores_df)

team_tab, leaderboard_tab, transactions_tab = st.tabs(["Fantasy Teams", "Leaderboard", "Transactions"])

with team_tab:
    st.subheader("Fantasy team standings")
    summary_df = build_team_summary_df(war_map)
    st.dataframe(summary_df, width='stretch')
    st.markdown("---")
    st.subheader("Team WAR Visualization")
    chart_data = summary_df[["Team", "Total WAR"]].sort_values("Total WAR", ascending=False).set_index("Team")
    st.bar_chart(chart_data)
    st.markdown("---")
    for team_name, team_data in TEAMS.items():
        with st.expander(f"⚾ {team_name}", expanded=False):
            render_team(team_name, team_data, war_map)

with leaderboard_tab:
    query = st.text_input("Search player (partial match):", value="", key="leaderboard_query")
    if query.strip():
        mask = scores_df["Player"].str.contains(query, case=False, na=False)
        results = scores_df[mask]
        st.subheader(f"Matches for: {query}")
        st.dataframe(results, width='stretch')
    else:
        st.subheader("Leaderboard")
        st.dataframe(scores_df, width='stretch')

    st.download_button(
        "Download CSV",
        data=scores_df.to_csv(index=False).encode("utf-8"),
        file_name="morescore.csv",
        mime="text/csv",
    )

with transactions_tab:
    st.subheader("Transaction Log")
    st.info("Transactions are managed via the transactions.csv file. Update the CSV to add new transactions.")
    
    transactions_df = load_transactions()
    if not transactions_df.empty:
        st.dataframe(transactions_df, width='stretch')
        
        csv = transactions_df.to_csv(index=False)
        st.download_button(
            "Download Transaction Log",
            data=csv.encode("utf-8"),
            file_name="transactions.csv",
            mime="text/csv",
        )
    else:
        st.info("No transactions logged yet")
