import json
from app import db, socketio
from app.models import ShipPlacement, Player
import sqlalchemy as sa
import random
from abc import ABC, abstractmethod
from app.game_logic.base_logic import GameLogic


#---------------Trừu tượng~------------------------- Hiện tại không quan trọng lắm!

class AIInterface(ABC):
    """
    Interface quy định mọi AI phải có 2 hàm chính:
    - place_ships(): cách AI đặt tàu
    - make_shot(): cách AI chọn ô để bắn
    """

    @abstractmethod
    def place_ships(self):
        pass

    @abstractmethod
    def make_shot(self, attacker_name: str, target_name: str) -> dict:
        """
        Chọn ô để bắn.

        Returns:
            dict: {
                "result": str,  # ví dụ: "hit", "miss", "sunk", "invalid"
                "x": int,
                "y": int
            }
        """
        pass


class BaseAI(GameLogic, AIInterface, ABC):
    """
    Base class cho tất cả AI.
    Kế thừa toàn bộ logic của GameLogic,
    đồng thời buộc các lớp con phải định nghĩa cách đặt tàu và bắn.
    """

    def __init__(self, game, name=None):
        super().__init__(game)
        self.game = game
        self.name = name or (game.ai.name if game.ai else "AI bot")

    @abstractmethod
    def place_ships(self):
        """Hàm bắt buộc: đặt tàu cho AI."""
        pass

    @abstractmethod
    def make_shot(self, attacker_name: str, target_name: str) -> dict:
        """
        Hàm bắt buộc: chọn tọa độ để bắn.
        Phải return dict có dạng: {"result": "", "x": , "y": }
        """
        pass
    

#---------------------------------------AI chính-----------------------------------------------------

class TestAI(BaseAI):
    """
    AI Này sinh ra là để test
    Chọn nước bắn ngẫu nhiên thôi
    """
    def place_ships(self):
        print(f"[DEBUG] TestAI.place_ships() -> bắt đầu đặt tàu cho {self.name}")
        self.auto_place_ships(self.name)

    def make_shot(self, attacker_name, target_name):
        board = self.get_board(target_name)
        if not board:
            print(f"[ERROR] Không tìm thấy bảng của {target_name}")
            return {"result": "invalid", "x": -1, "y": -1}


        # Chọn ô ngẫu nhiên chưa bắn
        possible_moves = [(x, y) for x in range(10) for y in range(10)
                          if board[x][y] not in (2, 3, 4)]
        if not possible_moves:
            print("[DEBUG] AI không còn ô nào để bắn.")
            return {"result": "invalid", "x": -1, "y": -1}

        x, y = random.choice(possible_moves)
        print(f"[DEBUG] {self.name} bắn vào ({x}, {y}) của {target_name}")

        result_data = self.shoot(attacker_name, target_name, x, y)
        result_data['x'] = x
        result_data['y'] = y
        db.session.commit()
        
        return result_data


class RandomAI(BaseAI):
    """
        AI đặt tàu một cách ngẫu nhiên 
        Bắn dựa trên phổ xác xuất của player và tất cả player (tỉ lệ 3 : 7)
    """
    def place_ships(self):
        print(f"[DEBUG] RandomAI.place_ships() -> bắt đầu đặt tàu cho {self.name}")
        self.auto_place_ships(self.name)
        
    def make_shot(self, attacker_name, target_name):
        from app.queries import overall_probability_matrix
        overall_prob = overall_probability_matrix()
        
        target = db.session.scalar(
            sa.select(Player)
            .where(Player.playername == target_name)
        )
        player_prob = target.ship_probability_matrix
        
        import numpy
        overall_prob_np = numpy.array(overall_prob, dtype=float)
        player_prob_np = numpy.array(player_prob, dtype=float)
        
        #Ma trận để con này quyết định phát bắn 
        strategic_mat = overall_prob_np * 0.7 + player_prob_np * 0.3
        
        
        #Phần còn lại xử lí như bình thường 
        board = self.get_board(target_name)
        if not board:
            print(f"[ERROR] Không tìm thấy bảng của {target_name}")
            return {"result": "invalid", "x": -1, "y": -1}
        
        best_val = -1e9
        for x in range(10):
            for y in range(10):
                if (board[x][y] in (2, 3, 4)):
                    strategic_mat[x][y] = -1e9
                    continue
                if strategic_mat[x][y] > best_val:
                    best_val = strategic_mat[x][y]
                    best_x, best_y = x, y
                    
        x, y = best_x, best_y 
        print(f"[DEBUG] {self.name} bắn vào ({x}, {y}) của {target_name}")

        result_data = self.shoot(attacker_name, target_name, x, y)
        result_data['x'] = x
        result_data['y'] = y
        db.session.commit()
        
        return result_data
                    
        


# ----------------------------------- Linh tinh -------------------------------------

def get_ai_instance(game):
    """
    Tạo instance AI dựa theo game.ai.name -> cần khớp tên class và tên của AI 
    """
    ai_name = getattr(game.ai, "name", None)
    if not ai_name:
        raise ValueError("game.ai.name chưa được thiết lập!")

    # Tìm class AI trong module hiện tại
    cls = globals().get(ai_name)
    if cls is None:
        raise ValueError(f"Không tìm thấy lớp AI có tên: {ai_name}")
    if not issubclass(cls, BaseAI):
        raise TypeError(f"{ai_name} không kế thừa BaseAI!")

    return cls(game)