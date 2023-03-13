# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/dataStrcuture/04_data_extractor.ipynb.

# %% auto 0
__all__ = ['data_aggregator']

# %% ../../nbs/dataStrcuture/04_data_extractor.ipynb 3
import datetime
import json
from typing import Tuple

import numpy as np
import pandas as pd
from tqdm.auto import tqdm

from ..config.mongo import mongo_init
from .game_features import *
from .odds import *
from .team_lineup import *

# %% ../../nbs/dataStrcuture/04_data_extractor.ipynb 7
def data_aggregator(
    db_hosts: dict,  # All DB hosts.
    config: dict,  # Database config.
    db_host: str = "prod_atlas",  # Database host name.
    limit: int = None,  # Number of rows to extract.
) -> pd.DataFrame:  # Mapped games.
    "Returns and aggregates games information from multiple Db collections."

    def _get_odds_columns(
        odds: pd.DataFrame,
        market: str,
    ) -> Tuple:  # set of odds
        "Returns Odds for a given market."

        odds_1 = (
            odds[odds.market_type == market].odds1.values[0]
            if len(odds[odds.market_type == market]) > 0
            else None
        )
        odds_2 = (
            odds[odds.market_type == market].odds2.values[0]
            if len(odds[odds.market_type == market]) > 0
            else None
        )
        odds_x = (
            odds[odds.market_type == market].oddsX.values[0]
            if len(odds[odds.market_type == market]) > 0
            else None
        )

        line = (
            odds[odds.market_type == market].line_id.values[0]
            if len(odds[odds.market_type == market]) > 0
            else None
        )

        return odds_1, odds_2, odds_x, line

    def _filter_asian_lines(
        all_game_odds: pd.DataFrame,  # All markets for a given game.
    ) -> pd.core.indexes:
        "Returns indexes of the non-even lines."

        if all_game_odds is None:
            return None
        # Get asian market.
        df_asian = all_game_odds[all_game_odds["market_type"] == "asian"].copy()
        # Calculate delta between "odds1" and "odds2" columns
        df_asian["delta"] = abs(df_asian["odds1"] - 2.0) + abs(df_asian["odds2"] - 2.0)
        # Keep the line that has a minimum delta (even line).
        not_even_line_idx = df_asian.loc[
            ~(df_asian["delta"] == df_asian["delta"].min())
        ].index

        return not_even_line_idx

    def _odds(
        game_id: str,  # Real-analytics game identifier.
        game_date: datetime.datetime,  # Find the lastest data document prior to `date`.
    ) -> np.ndarray:  # Odds values.
        "Returns game Odds. It can be 1x2 or Asian Handicap."

        # Extract all odds(1x2, Asian handicap and Total).
        all_game_odds = MarketOdds.get_all_odds(ra_game_id=game_id, date=game_date)
        # No even lines indexes.
        not_even_line_idx = _filter_asian_lines(all_game_odds=all_game_odds)
        # Drop indexes.
        all_game_odds = all_game_odds.drop(index=not_even_line_idx)
        # Group by and Keep only once document per type of market.
        final_odds = all_game_odds.loc[
            all_game_odds.groupby("market_type")["received_at"].idxmax()
        ]
        # 1X2 odds.
        odds_1_1x2, odds_2_1x2, odds_x_1x2, _ = _get_odds_columns(final_odds, "1x2")

        # Asian Handicap.
        odds_1_ah, odds_2_ah, _, line_ah = _get_odds_columns(final_odds, "asian")

        # Total(Over/Under) odds.
        odds_1_total, odds_2_total, _, line_total = _get_odds_columns(final_odds, "total")

        return pd.DataFrame(
            {
                "preGameOdds1": odds_1_1x2,
                "preGameOddsX": odds_x_1x2,
                "preGameOdds2": odds_2_1x2,
                "preGameAhHome": odds_1_ah,
                "preGameAhAway": odds_2_ah,
                "LineId": line_ah,
                "preGameTotalHome": odds_1_ah,
                "preGameTotalAway": odds_2_ah,
                "totalLineId": line_total,
            },
            index=[0],
        )

    def _team_features(
        team_id: str,  # Real-analytics game identifier.
        game_date: datetime.datetime,  # Find the lastest data document prior to `date`.
    ) -> Tuple:  # Lineup values (name:position, ids, slots, formation name, timestamp).
        "Returns lineup features of a given team."

        # Lineup features.
        team_features = TeamSheet.get_latest(ra_team_id=team_id, date=game_date)

        # Team name.
        team_name = team_features.name
        # Players and positions.
        team_lineups_names = json.dumps(
            {player.name: player.position for player in team_features.starting}
        )
        # Players ids.
        team_lienups_ids = [player.opta_id for player in team_features.starting]
        # Players slots.
        team_lienups_slots = [player.slot for player in team_features.starting]
        # Formation name.
        formation_name = team_features.starting.first().formation
        # Lineup timestamp.
        lineup_time_stamp = team_features.received_at

        return pd.DataFrame(
            {
                "team_name": team_name,
                "team_lineups_names": [team_lineups_names],
                "team_lienups_ids": [team_lienups_ids],
                "team_lienups_slots": [team_lienups_slots],
                "formation_name": formation_name,
                "lineup_time_stamp": lineup_time_stamp,
            },
            index=[0],
        )

    # Connect to database.
    mongo_init(db_hosts=db_hosts, config=config, db_host=db_host)

    # Extract games.
    games = GameFeatures.get_all_games(limit=limit)
    games = pd.DataFrame(games.as_pymongo())

    # Filter Data.
    games = games[
        [
            "gameId",
            "game_optaId",
            "gameDate",
            "homeTeamId",
            "homeTeam_optaId",
            "awayTeamId",
            "awayTeam_optaId",
            "tgt_gd",
            "tgt_outcome",
        ]
    ]

    # Map results {homewin -> 0 , draw -> 1, awaywin -> 2}.
    games["tgt_outcome"] = games["tgt_outcome"].map({1.0: 0.0, 0.0: 2.0, 0.5: 1.0})

    # compute other features
    def _one_game(row):
        o_1x2_ah_total = _odds(
            game_id=row["gameId"],
            game_date=row["gameDate"],
        )

        ht_feats = _team_features(
            team_id=row["homeTeamId"], game_date=row["gameDate"]
        ).rename(
            columns={
                "team_name": "homeTeamName",
                "team_lineups_names": "homeTeamLineup",
                "team_lienups_ids": "homeTeamLineupIds",
                "team_lienups_slots": "homeTeamLineupSlots",
                "formation_name": "homeTeamFormation",
                "lineup_time_stamp": "home_team_lineup_received_at",
            },
        )

        at_feats = _team_features(
            team_id=row["awayTeamId"], game_date=row["gameDate"]
        ).rename(
            columns={
                "team_name": "awayTeamName",
                "team_lineups_names": "awayTeamLineup",
                "team_lienups_ids": "awayTeamLineupIds",
                "team_lienups_slots": "awayTeamLineupSlots",
                "formation_name": "awayTeamFormation",
                "lineup_time_stamp": "away_team_lineup_received_at",
            },
        )

        res = pd.concat([o_1x2_ah_total, ht_feats, at_feats], axis=1)
        res.loc[:, "gameId"] = row.gameId

        return res

    return games.merge(
        pd.concat(
            [_one_game(row) for _, row in tqdm(games.iterrows(), total=games.shape[0])]
        ).reset_index(drop=True),
        on="gameId",
        how="left",
    )
