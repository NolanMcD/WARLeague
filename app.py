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
