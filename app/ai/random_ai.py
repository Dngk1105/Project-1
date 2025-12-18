import numpy
import sqlalchemy as sa
from app import db
from app.models import Player
from app.ai.ai_interface import BaseAI


class RandomAI(BaseAI):
    """
    AI đặt tàu ngẫu nhiên, bắn theo xác suất (player vs overall)
    """

    def place_ships(self):
        print(f"[DEBUG] RandomAI.place_ships() -> bắt đầu đặt tàu cho {self.name}")
        self.auto_place_ships(self.name)

    def make_shot(self, attacker_name, target_name):
        from app.game_logic.queries import overall_probability_matrix
        overall_prob = overall_probability_matrix()

        target = db.session.scalar(
            sa.select(Player).where(Player.playername == target_name)
        )
        player_prob = target.ship_probability_matrix

        overall_prob_np = numpy.array(overall_prob, dtype=float)
        player_prob_np = numpy.array(player_prob, dtype=float)
        strategic_mat = overall_prob_np * 0.7 + player_prob_np * 0.3

        board = self.get_board(target_name)
        if not board:
            print(f"[ERROR] Không tìm thấy bảng của {target_name}")
            return {"result": "invalid", "x": -1, "y": -1}

        best_val = -1e9
        best_x = best_y = -1
        for x in range(10):
            for y in range(10):
                if board[x][y] in (2, 3, 4):
                    strategic_mat[x][y] = -1e9
                    continue
                if strategic_mat[x][y] > best_val:
                    best_val = strategic_mat[x][y]
                    best_x, best_y = x, y

        x, y = best_x, best_y
        print(f"[DEBUG] {self.name} bắn vào ({x}, {y}) của {target_name}")

        result_data = self.shoot(attacker_name, target_name, x, y)
        result_data.update({"x": x, "y": y})
        db.session.commit()

        return result_data
