#!/usr/bin/env python3
"""Interactive draft board for 9 teams: 5 starters + 2 reserves each.

Usage examples:
  python draft_board.py
  python draft_board.py --auto
  python draft_board.py --players-file players.txt
"""
import argparse
import json
import os

NUM_TEAMS = 9
STARTERS = 5
RESERVES = 2
PICKS_PER_TEAM = STARTERS + RESERVES


DEFAULT_PLAYERS = [f"Player {i}" for i in range(1, NUM_TEAMS * PICKS_PER_TEAM + 1)]


def generate_snake_order(num_teams, rounds):
    order = []
    for r in range(rounds):
        if r % 2 == 0:
            order.extend(list(range(num_teams)))
        else:
            order.extend(list(reversed(range(num_teams))))
    return order


def interactive_draft(players):
    available = players.copy()
    teams = [{"name": f"Team {i+1}", "starters": [], "reserves": []} for i in range(NUM_TEAMS)]
    rounds = PICKS_PER_TEAM
    order = generate_snake_order(NUM_TEAMS, rounds)
    total_picks = NUM_TEAMS * rounds
    for pick_index, team_idx in enumerate(order):
        round_no = pick_index // NUM_TEAMS + 1
        role = "starter" if round_no <= STARTERS else "reserve"
        team = teams[team_idx]
        print(f"\nPick {pick_index+1}/{total_picks} — {team['name']} ({role})")
        for i, p in enumerate(available, start=1):
            print(f"{i:2d}. {p}")
        while True:
            choice = input("Enter player number or name (or 'q' to quit): ").strip()
            if choice.lower() == 'q':
                print("Draft aborted.")
                return teams, available
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(available):
                    player = available.pop(idx)
                    break
                else:
                    print("Invalid number.")
            else:
                exact = [p for p in available if p.lower() == choice.lower()]
                if len(exact) == 1:
                    player = exact[0]
                    available.remove(player)
                    break
                contains = [p for p in available if choice.lower() in p.lower()]
                if len(contains) == 1:
                    player = contains[0]
                    available.remove(player)
                    break
                if len(contains) > 1:
                    print("Multiple matches:", ", ".join(contains[:10]))
                else:
                    print("No match.")
        if role == "starter":
            team['starters'].append(player)
        else:
            team['reserves'].append(player)
        print(f"Selected: {player}")
    return teams, available


def save_board(teams, path="draft_board.json"):
    out = {"teams": teams}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"Saved draft board to {path}")


def main():
    parser = argparse.ArgumentParser(description="Interactive draft board for 9 teams")
    parser.add_argument("--players-file", help="optional file with one player per line")
    parser.add_argument("--auto", action="store_true", help="auto-run draft by assigning top available to teams in order")
    args = parser.parse_args()
    if args.players_file and os.path.exists(args.players_file):
        with open(args.players_file, encoding="utf-8") as f:
            players = [line.strip() for line in f if line.strip()]
    else:
        players = DEFAULT_PLAYERS
    if len(players) < NUM_TEAMS * PICKS_PER_TEAM:
        print(f"Warning: only {len(players)} players, expected {NUM_TEAMS * PICKS_PER_TEAM}. Draft may fail.")
    if args.auto:
        teams = [{"name": f"Team {i+1}", "starters": [], "reserves": []} for i in range(NUM_TEAMS)]
        rounds = PICKS_PER_TEAM
        order = generate_snake_order(NUM_TEAMS, rounds)
        for pick_index, team_idx in enumerate(order):
            round_no = pick_index // NUM_TEAMS + 1
            role = "starter" if round_no <= STARTERS else "reserve"
            player = players.pop(0)
            if role == "starter":
                teams[team_idx]['starters'].append(player)
            else:
                teams[team_idx]['reserves'].append(player)
        save_board(teams)
    else:
        teams, remaining = interactive_draft(players)
        save_board(teams)


if __name__ == "__main__":
    main()
