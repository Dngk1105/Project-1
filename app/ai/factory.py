from app.ai.ai_interface import BaseAI
from app.ai.test_ai import TestAI
from app.ai.random_ai import RandomAI
from app.ai.demo_prob_ai import DemoProbAI
from app.ai.prob_ai import ProbAI



def get_ai_instance(game):
    """
    Tạo instance AI dựa theo game.ai.name (trùng với tên class)
    """
    ai_name = getattr(game.ai, "name", None)
    if not ai_name:
        raise ValueError("game.ai.name chưa được thiết lập!")

    cls = globals().get(ai_name)
    if cls is None:
        raise ValueError(f"Không tìm thấy lớp AI có tên: {ai_name}")
    if not issubclass(cls, BaseAI):
        raise TypeError(f"{ai_name} không kế thừa BaseAI!")

    return cls(game)
