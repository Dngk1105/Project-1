from app import db, login
from datetime import datetime, timezone
import sqlalchemy as sa
import sqlalchemy.orm as so
from typing import Optional
from app import db, login
from flask_login import UserMixin
import json
import numpy

class Player(UserMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    playername: so.Mapped[str] = so.mapped_column(db.String(64), unique=True, index=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256), nullable=True)   #chưa dùng


    # Thống kê
    wins: so.Mapped[int] = so.mapped_column(default=0)
    losses: so.Mapped[int] = so.mapped_column(default=0)
    
    @property
    def ship_probability_matrix(self):
        from app.models import Game, ShipPlacement
        
        placements = db.session.scalars(
            sa.select(ShipPlacement.grid_data)
            .join(Game)
            .where( (ShipPlacement.owner == self.playername) & (Game.status == 'finished') )
        ).all()
        
        if not placements:
            return None

        maxtrix_sum = None
        numOfGrid = len(placements)
        
        for grid_json in placements:
            grid = json.loads(grid_json)
            grid_np = numpy.array(grid, dtype=float)
            # Chỉ giữ lại ô có tàu (1 hoặc 2), bỏ qua ô 0 và ô miss (3)
            grid_np = numpy.where((grid_np == 1) | (grid_np == 2) | (grid_np == 4), 1.0, 0.0)
            
            if maxtrix_sum is None:
                maxtrix_sum = grid_np
            else: 
                maxtrix_sum += grid_np
                
        return (maxtrix_sum / numOfGrid).tolist()

    @property
    def win_rate(self) -> float:
        total = self.wins + self.losses
        if total > 0:
            return self.wins / total 
        else: return 0 
        
    @property
    def games_played(self) -> int:
        from app.models import Game  # tránh Game không được khởi tạo
        count = db.session.scalar(
            sa.select(sa.func.count(Game.id)).where(
            ((Game.player_id == self.id) | (Game.opponent_id == self.id))
            & (Game.status == 'finished')
        )
        )
        return count or 0
    
    #Các trận đã chơi của player
    @property
    def matches(self):
        from app.models import Game, Player

        games = db.session.scalars(
            sa.select(Game)
            .where(
                (Game.player_id == self.id) | (Game.opponent_id == self.id)
            )
            .order_by(Game.timestamp.desc())
        ).all()

        # Dựng dữ liệu dạng dễ hiển thị cho template
        matches_data = []
        for g in games:
            if g.player_id == self.id:
                opponent = g.opponent.playername if g.opponent else "AI"
                result = "win" if g.winner == self.playername else "lose"
            else:
                opponent = g.player.playername  # Chắc chắn là người chơi
                result = "win" if g.winner == self.playername else "lose"

            matches_data.append({
                "game_id" : g.id,
                "opponent": opponent,
                "result": result,
                "timestamp": g.timestamp
            })

        return matches_data

    
    # Thống kê trận tham gia
    # Cần phân chia ra vì mỗi game có một host
        # người chơi chính
    games_as_player: so.WriteOnlyMapped["Game"] = so.relationship(
        back_populates="player",
        foreign_keys="Game.player_id"
    )

        # đối thủ
    games_as_opponent: so.WriteOnlyMapped["Game"] = so.relationship(
        back_populates="opponent",
        foreign_keys="Game.opponent_id"
    )

    def __repr__(self):
        return f"<Player {self.playername}>"
    
@login.user_loader
def load_user(id):
    return db.session.get(Player, int(id))
    
    
class AI(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(db.String(64), unique=True)
    description: so.Mapped[Optional[str]] = so.mapped_column(db.Text, nullable=True)

    
    # Thống kê hiệu suất
    wins: so.Mapped[int] = so.mapped_column(default=0)
    losses: so.Mapped[int] = so.mapped_column(default=0)

    games: so.WriteOnlyMapped["Game"] = so.relationship(back_populates="ai")

    @property
    def win_rate(self):
        total = self.wins + self.losses
        return self.wins / total if total > 0 else 0.0

    def __repr__(self):
        return f"<AI {self.name}>"
    
    
# Lưu thông tin 1 trận đấu
class Game(db.Model):
    # Cơ bản
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    timestamp: so.Mapped[datetime] = so.mapped_column(default=datetime.now(timezone.utc))

    # Kết quả trận
    winner: so.Mapped[str] = so.mapped_column(db.String(32))
    player_shots: so.Mapped[int] = so.mapped_column(default=0)
    opponent_shots: so.Mapped[int] = so.mapped_column(default=0)
    summary: so.Mapped[Optional[str]] = so.mapped_column(db.Text)   #Chưa dùng
    status: so.Mapped[str] = so.mapped_column(sa.String(16), default="pending")
    current_turn: so.Mapped[str] = so.mapped_column(sa.String(32), nullable=True)
    player_ready: so.Mapped[bool] = so.mapped_column(default=False)
    opponent_ready: so.Mapped[bool] = so.mapped_column(default=False)
    ai_ready: so.Mapped[bool] = so.mapped_column(default=False)



    # Quan hệ ORM
    player_id: so.Mapped[int] = so.mapped_column(db.ForeignKey("player.id"))
    ai_id: so.Mapped[Optional[int]] = so.mapped_column(db.ForeignKey("ai.id"), nullable=True)
    opponent_id: so.Mapped[Optional[int]] = so.mapped_column(db.ForeignKey("player.id"), nullable=True)
    
    player: so.Mapped["Player"] = so.relationship(
        back_populates="games_as_player", 
        foreign_keys=[player_id])
    opponent: so.Mapped["Player"] = so.relationship(
        back_populates="games_as_opponent", 
        foreign_keys=[opponent_id])
    ai: so.Mapped[Optional["AI"]] = so.relationship(
        back_populates="games",
        foreign_keys=[ai_id]
    )


    def __repr__(self):
        return f"<Game {self.id} winner={self.winner} status={self.status}>"    

#Thống kê trận đấu (chung)
class GameStats(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    algorithm_name: so.Mapped[str] = so.mapped_column(db.String(64))
    total_games: so.Mapped[int] = so.mapped_column(default=0)
    total_wins: so.Mapped[int] = so.mapped_column(default=0)
    avg_shots: so.Mapped[float] = so.mapped_column(default=0.0)

    def win_rate(self):
        return self.total_wins / self.total_games if self.total_games > 0 else 0.0
    
#Lưu tàu
class ShipPlacement(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    game_id: so.Mapped[int] = so.mapped_column(db.ForeignKey("game.id"))
    owner: so.Mapped[str] = so.mapped_column(db.String(16))  
    grid_data: so.Mapped[str] = so.mapped_column(db.Text)    
    ship_data: so.Mapped[Optional[str]] = so.mapped_column(db.Text, nullable=True)
    shot_data: so.Mapped[Optional[str]] = so.mapped_column(db.Text, nullable=True)
    
    # Quan hệ đến game
    #backref là ánh xạ ngược từ Game->ShipPlacement qua game.ship_placements
    game: so.Mapped["Game"] = so.relationship(backref="ship_placements")   
    

#Bảng lưu lịch sử game đấu
class GameMove(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    game_id: so.Mapped[int] = so.mapped_column(db.ForeignKey("game.id"))
    
    attacker_name: so.Mapped[str] = so.mapped_column(db.String(32))
    target_name: so.Mapped[str] = so.mapped_column(db.String(32))
    x: so.Mapped[int] = so.mapped_column(sa.Integer)
    y: so.Mapped[int] = so.mapped_column(sa.Integer)
    result: so.Mapped[str] = so.mapped_column(db.String(16))
    game_turn: so.Mapped[str] = so.mapped_column(db.String(32))
    
    
    prev_cell: so.Mapped[int] = so.mapped_column(sa.Integer)
    sunk_ship_name: so.Mapped[Optional[str]] = so.mapped_column(db.String(32), nullable=True)
    is_reverted: so.Mapped[bool] = so.mapped_column(default=False)

    game: so.Mapped["Game"] = so.relationship(backref="moves")