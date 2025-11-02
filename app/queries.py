from app import db
from app.models import Player, AI, Game, ShipPlacement
import sqlalchemy as sa
import numpy

def overall():
    ''' Tổng quan toàn bộ game đấu '''
    total_players = db.session.scalar(
        sa.select(sa.func.count(Player.id))
    )
    
    total_games = db.session.scalar(
        sa.select(sa.func.count(Game.id))
        .where(Game.status == "finished")
    )
    
    human_vs_human = db.session.scalar(
        sa.select(sa.func.count(Game.id)).where(
            (Game.ai_id.is_(None)) & (Game.status == 'finished')
        )
    )
    
    human_vs_ai = db.session.scalar(
        sa.select(sa.func.count(Game.id)).where(
            (Game.ai_id.is_not(None)) & (Game.status == 'finished')
        )
    )
    
    human_win_vs_ai = db.session.scalar(
        sa.select(sa.func.count(Game.id))
        .join(Player, Game.player_id == Player.id)  
        .where(
            Game.ai_id.isnot(None),
            Game.status == "finished",
            Game.winner.isnot(None),
            Game.winner != Player.playername     
        )
    )

    human_win_rate_vs_ai = (
        (human_win_vs_ai / human_vs_ai * 100) if human_vs_ai > 0 else 0.0
    )
    
    
    avg_player_shots = db.session.scalar(sa.select(sa.func.avg(Game.player_shots)))
    avg_opponent_shots = db.session.scalar(sa.select(sa.func.avg(Game.opponent_shots)))
    avg_total_shots = (
        (avg_player_shots or 0) + (avg_opponent_shots or 0)
    )
    
    return {
        "total_players": total_players,
        "total_games": total_games,
        "human_vs_human": human_vs_human,
        "human_vs_ai": human_vs_ai,
        "human_win_rate_vs_ai": round(human_win_rate_vs_ai, 2),
        "avg_total_shots": round(avg_total_shots, 2)
    }
    
def overall_probability_matrix():
    '''Phổ xác xuất của tất cả người chơi'''
    players = db.session.scalars(
        sa.select(Player)
    ).all()
    
    matrix_sum = None
    count = 0
    
    for player in players:
        matrix = player.ship_probability_matrix
        if matrix != None:
            matrix_np = numpy.array(matrix, dtype=float)
            if matrix_sum is None:
                matrix_sum = matrix_np
            else:
                matrix_sum += matrix_np
            count += 1
    
    if count == 0:
        return None
    
    return (matrix_sum / count).tolist()