# app/socket_helpers.py
from flask import url_for
from app import socketio, db


#Xử lí kết quả phát bắn
def process_shot_result(game, result_data, attacker_name, target_name, x = None, y = None):
    """Phát sự kiện và cập nhật game sau khi có kết quả bắn"""
    #  Gửi kết quả bắn
    socketio.emit("shot_result", {
        "x": x if x is not None else result_data.get("x"),
        "y": y if y is not None else result_data.get("y"),
        "result": result_data["result"],
        "move_id": result_data.get("move_id"),
        "attacker": attacker_name,
        "target": target_name,
    }, to=str(game.id))

    #  Nếu có tàu bị chìm
    if result_data["result"] == "sunk":
        socketio.emit("ship_sunked", {
            "owner": result_data["owner"],
            "ship_name": result_data["ship_name"],
            "comp": result_data["comp"]
        }, to=str(game.id))

    #  Nếu có người thắng
    if result_data.get("winner"):
        game.status = "finished"
        game.winner = result_data["winner"]
        db.session.commit()

        redirect_url = url_for("game_detail", game_id=game.id)
        socketio.emit("game_over", {
            "winner": result_data["winner"],
            "redirect_url": redirect_url
        }, to=str(game.id))
        return True  # báo hiệu game kết thúc

    #  Cập nhật lượt
    if result_data["result"] in ["miss", "out_of_bounds"]:
        game.current_turn = target_name
    else:
        game.current_turn = attacker_name

    db.session.commit()

    #  Gửi sự kiện đổi lượt
    socketio.emit("turn_change", {
        "current_turn": game.current_turn,
        "is_ai_turn": (game.ai and game.current_turn == game.ai.name)
    }, to=str(game.id))

    return False  # game chưa kết thúc
