WARLeague Draft Board

This repository contains a Streamlit app `app.py` and a standalone draft script `draft_board.py`.

Draft script
- `draft_board.py`: interactive snake-order draft for 9 teams (5 starters + 2 reserves). Usage:

```powershell
python draft_board.py             # interactive
python draft_board.py --auto      # auto-assign top players
python draft_board.py --players-file players.txt
```

Streamlit integration
- `app.py` now includes a **Draft Board** section with a button `Run Auto Draft and Show Results` that runs an automatic draft using the sample players and displays/downloads `draft_board.json`.

Testing
1. Run the auto draft script directly:

```powershell
python .\draft_board.py --auto
```

2. Launch the Streamlit app and click the draft button:

```powershell
streamlit run app.py
```
