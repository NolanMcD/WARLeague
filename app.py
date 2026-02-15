import pandas as pd
import streamlit as st
import json

# integrate draft board
import draft_board


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


st.set_page_config(page_title="WAR League Scorebook", layout="wide")
st.title("WAR League Scorebook")

df = build_scores()

query = st.text_input("Search player (partial match):", value="")
if query.strip():
    mask = df["Player"].str.contains(query, case=False, na=False)
    results = df[mask]
    st.subheader(f"Matches for: {query}")
    st.dataframe(results, use_container_width=True)
else:
    st.subheader("Leaderboard")
    st.dataframe(df, use_container_width=True)

st.download_button(
    "Download CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="morescore.csv",
    mime="text/csv",
)


st.header("Draft Board")

# Interactive Streamlit draft flow using session state
if 'db_started' not in st.session_state:
    st.session_state.db_started = False

col1, col2 = st.columns([3, 1])
with col1:
    uploaded = st.file_uploader("Upload players file (one player per line)")
    st.write("Or use the default sample players list.")
    if st.button("Initialize Draft"):
        if uploaded is not None:
            text = uploaded.getvalue().decode('utf-8')
            players = [l.strip() for l in text.splitlines() if l.strip()]
        else:
            players = draft_board.DEFAULT_PLAYERS.copy()
        teams = [{"name": f"Team {i+1}", "starters": [], "reserves": []} for i in range(draft_board.NUM_TEAMS)]
        rounds = draft_board.PICKS_PER_TEAM
        order = draft_board.generate_snake_order(draft_board.NUM_TEAMS, rounds)
        st.session_state.db_players = players
        st.session_state.db_available = players.copy()
        st.session_state.db_teams = teams
        st.session_state.db_order = order
        st.session_state.db_pick_index = 0
        st.session_state.db_rounds = rounds
        st.session_state.db_total_picks = len(order)
        st.session_state.db_started = True
        st.session_state.db_history = []

with col2:
    if st.button("Auto-complete remaining picks") and st.session_state.db_started:
        players = st.session_state.db_available
        teams = st.session_state.db_teams
        order = st.session_state.db_order
        pick_index = st.session_state.db_pick_index
        while pick_index < len(order) and players:
            team_idx = order[pick_index]
            round_no = pick_index // draft_board.NUM_TEAMS + 1
            role = "starter" if round_no <= draft_board.STARTERS else "reserve"
            player = players.pop(0)
            if role == "starter":
                teams[team_idx]['starters'].append(player)
            else:
                teams[team_idx]['reserves'].append(player)
            st.session_state.db_history.append((pick_index, team_idx, player))
            pick_index += 1
        st.session_state.db_available = players
        st.session_state.db_teams = teams
        st.session_state.db_pick_index = pick_index

if st.session_state.db_started:
    pick_index = st.session_state.db_pick_index
    total = st.session_state.db_total_picks
    if pick_index >= total:
        st.success("Draft complete")
        st.subheader("Draft Results")
        st.json({"teams": st.session_state.db_teams})
        st.download_button("Download draft JSON", data=json.dumps({"teams": st.session_state.db_teams}, indent=2), file_name="draft_board.json", mime="application/json")
    else:
        order = st.session_state.db_order
        team_idx = order[pick_index]
        round_no = pick_index // draft_board.NUM_TEAMS + 1
        role = "starter" if round_no <= draft_board.STARTERS else "reserve"
        team = st.session_state.db_teams[team_idx]
        st.write(f"Pick {pick_index+1}/{total} — {team['name']} ({role})")
        available = st.session_state.db_available
        # show a small searchable selectbox by slicing available if very large
        choice = st.selectbox("Choose player", options=available)
        cols = st.columns([1,1,1])
        if cols[0].button("Confirm Pick"):
            if choice in available:
                available.remove(choice)
                if role == "starter":
                    team['starters'].append(choice)
                else:
                    team['reserves'].append(choice)
                st.session_state.db_history.append((pick_index, team_idx, choice))
                st.session_state.db_pick_index += 1
                st.session_state.db_available = available
                st.session_state.db_teams[team_idx] = team
                st.experimental_rerun()
        if cols[1].button("Skip (auto pick)"):
            if available:
                player = available.pop(0)
                if role == "starter":
                    team['starters'].append(player)
                else:
                    team['reserves'].append(player)
                st.session_state.db_history.append((pick_index, team_idx, player))
                st.session_state.db_pick_index += 1
                st.session_state.db_available = available
                st.session_state.db_teams[team_idx] = team
                st.experimental_rerun()
        if cols[2].button("Undo last") and st.session_state.db_history:
            last = st.session_state.db_history.pop()
            last_pick_idx, last_team_idx, last_player = last
            # revert
            t = st.session_state.db_teams[last_team_idx]
            if last_player in t.get('starters', []):
                t['starters'].remove(last_player)
            if last_player in t.get('reserves', []):
                t['reserves'].remove(last_player)
            st.session_state.db_available.insert(0, last_player)
            st.session_state.db_teams[last_team_idx] = t
            st.session_state.db_pick_index = last_pick_idx
            st.experimental_rerun()

