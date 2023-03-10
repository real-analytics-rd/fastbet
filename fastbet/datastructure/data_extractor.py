# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/dataStrcuture/04_data_extractor.ipynb.

# %% auto 0
__all__ = ['data_aggregator']

# %% ../../nbs/dataStrcuture/04_data_extractor.ipynb 3
import datetime
import json
from typing import Tuple

import pandas as pd
import numpy as np

from ..config.mongo import mongo_init
from .game_features import *
from .odds import *
from .team_lineup import * 

# %% ../../nbs/dataStrcuture/04_data_extractor.ipynb 6
def data_aggregator(
    db_hosts: dict,  # All DB hosts.
    config: dict,  # Database config.
    db_host: str = "prod_atlas",  # Database host name.
    limit: int = None,  # Number of rows to extract.
) -> pd.DataFrame:  # Mapped games.
    "Returns and aggregates games information from multiple Db collections."

    def _odds(
        game_id: str,  # Real-analytics game identifier.
        game_date: datetime.datetime,  # Find the lastest data document prior to `date`.
        market_type: str,  # Type of market required; should one of 1x2 and Asian Handicap.
    ) -> np.ndarray:  # Odds values.
        "Returns game Odds. It can be 1x2 or Asian Handicap."

        if market_type == "1x2":
            return MarketOdds.get_odds_features(
                ra_game_id=game_id, market=market_type, date=game_date
            )[["odds1", "oddsX", "odds2"]].values[0]
        else:
            return MarketOdds.get_latest(
                ra_game_id=game_id, market=market_type, date=game_date
            )[["odds1", "odds2", "line_id"]].values[0]

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
        team_lienups_ids = list(player.opta_id for player in team_features.starting)
        # Players slots.
        team_lienups_slots = list(player.slot for player in team_features.starting)
        # Formation name.
        formation_name = team_features.starting.first().formation
        # Lineup timestamp.
        lineup_time_stamp = team_features.received_at

        return (
            team_name,
            team_lineups_names,
            team_lienups_ids,
            team_lienups_slots,
            formation_name,
            lineup_time_stamp,
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

    # Add 1X2 odds.
    games[["preGameOdds1", "preGameOddsX", "preGameOdds2"]] = games.apply(
        lambda row: _odds(
            game_id=row["gameId"],
            game_date=row["gameDate"],
            market_type="1x2",
        ),
        axis="columns",
        result_type="expand",
    )

    # Add Asian handicap odds.
    games[["preGameAhHome", "preGameAhAway", "LineId"]] = games.apply(
        lambda row: _odds(
            game_id=row["gameId"],
            game_date=row["gameDate"],
            market_type="asian",
        ),
        axis="columns",
        result_type="expand",
    )

    # Add Home team lineup features.
    games[
        [
            "homeTeamName",
            "homeTeamLineup",
            "homeTeamLineupIds",
            "homeTeamLineupSlots",
            "homeTeamFormation",
            "home_team_lineup_received_at",
        ]
    ] = games.apply(
        lambda row: _team_features(
            team_id=row["homeTeamId"], game_date=row["gameDate"]
        ),
        axis="columns",
        result_type="expand",
    )

    # Add away team lineup features.
    games[
        [
            "awayTeamName",
            "awayTeamLineup",
            "awayTeamLineupIds",
            "awayTeamLineupSlots",
            "awayTeamFormation",
            "away_team_lineup_received_at",
        ]
    ] = games.apply(
        lambda row: _team_features(
            team_id=row["awayTeamId"], game_date=row["gameDate"]
        ),
        axis="columns",
        result_type="expand",
    )

    # Map results {homewin -> 0 , draw -> 1, awaywin -> 2}.
    games["tgt_outcome"] = games["tgt_outcome"].map({1.0: 0.0, 0.0: 2.0, 0.5: 1.0})

    return games