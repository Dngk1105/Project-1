import random
from abc import ABC, abstractmethod
from app.game_logic.base_logic import GameLogic
from app.game_logic.place_ships_strat import ShipPlacementStrategy
from app import socketio


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
            dict: {"result": str, "x": int, "y": int}
        """
        pass


class BaseAI(ShipPlacementStrategy, AIInterface, ABC):
    """
    Base class cho tất cả AI.
    """

    def __init__(self, game, name=None):
        super().__init__(game)
        self.game = game
        self.name = name or (game.ai.name if game.ai else "AI bot")
        
    def log_action(self, message: str, **kwargs):
        """
        Gửi log hành động của AI tới client qua socket.

        Args:
            message (str): Nội dung log
            **kwargs: Dữ liệu mở rộng tuỳ loại AI (VD: matrix, heatmap, hướng bắn, v.v.)
        """
        data = {
            "ai_name": self.name,
            "game_id": self.game.id,
            "message": message
        }

        # Thêm dữ liệu mở rộng nếu có
        for key, value in kwargs.items():
            data[key] = value

        socketio.emit("ai_log_update", data, to=str(self.game.id))

    @abstractmethod
    def place_ships(self):
        pass

    @abstractmethod
    def make_shot(self, attacker_name: str, target_name: str) -> dict:
        pass
