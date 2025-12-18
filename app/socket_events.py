from app import socketio, db, app
from flask_socketio import emit, join_room, leave_room
from flask import request, current_app, url_for
from flask_login import current_user
from app.models import Game
from app.game_logic.base_logic import GameLogic
from app.game_logic.place_ships_strat import ShipPlacementStrategy
from app.ai.factory import get_ai_instance
from time import sleep

import threading
import time
import json

@socketio.on("join_room")
def handle_join(data):
    room = str(data.get("room"))
    join_room(room)
    print(f"{current_user.playername} joined room {room}")

    game = db.session.get(Game, int(room))
    if game and game.opponent_id is None and current_user.id != game.player_id:
        game.opponent_id = current_user.id
        game.status = "active"
        db.session.commit()
        emit("player_joined", {
            "game_id": int(room),
            "opponent_name": current_user.playername
        }, to=room, include_self=False)

@socketio.on("leave_room")
def handle_leave(data):
    room = str(data.get("room"))
    leave_room(room)
    print(f"{current_user.playername} left room {room}")

    game = db.session.get(Game, int(room))
    if not game:
        return

    # Nếu người rời là đối thủ
    if game.opponent_id == current_user.id:
        game.opponent_id = None
        game.status = "pending"
        db.session.commit()
        emit("opponent_left", {"game_id": int(room)}, to=room, include_self=False)

    # Nếu người rời là chủ phòng
    elif game.player_id == current_user.id:
        game.status = "canceled"
        db.session.commit()
        emit("game_canceled", {"game_id": int(room)}, to=room)
        

@socketio.on("cancel_game")
def handle_cancel(data):
    game_id = int(data.get("game_id"))
    game = db.session.get(Game, game_id)
    if game:
        game.status = "canceled"
        db.session.commit()
    emit("game_canceled", {"game_id": game_id}, to=str(game_id))
        
        
@socketio.on("place_ship")
def handle_place_ship(data):
    """Xử lý đặt tàu"""
    from app.game_logic.base_logic import GameLogic

    game_id = data["game_id"]
    ship_name = data["ship_name"]
    x, y = int(data["x"]), int(data["y"])
    orientation = data["orientation"]
    owner = data["owner"]

    game = db.session.get(Game, game_id)
    logic = GameLogic(game)
    board = logic.get_board(owner) or logic.init_board(owner)

    if not logic.can_place(board, x, y, logic.ships[ship_name], orientation):
        return emit("error", {"message": f"Không thể đặt {ship_name} ở vị trí này"}, to=request.sid)

    board = logic.place_ship(board, x, y, logic.ships[ship_name], orientation, ship_name, owner)
    logic.save_board(owner, board)

    emit("ship_placed_self", {
        "ship_name": ship_name, 
        "x": x, 
        "y": y, 
        "orientation": orientation, 
        "positions": logic.ship_positions[owner][ship_name]}, 
        to=request.sid)
    emit("opponent_progress", {"message": f"Đối thủ đã đặt {ship_name}"}, to=str(game.id), include_self=False)

@socketio.on("auto_place_ship")
def handle_auto_place_ship(data):
    from app.game_logic.base_logic import GameLogic

    game_id = data["game_id"]
    player = data["player"]
    strategy = data["strategy"]
    game = db.session.get(Game, game_id)

    logic = ShipPlacementStrategy(game)
    board = logic.auto_place_ships_strategy(player, strategy)
    board = json.dumps(board)

    socketio.emit("auto_ship_placed_self", {"board": board}, to=request.sid)
    print(f"[DEBUG] auto_place_ship -> emitted board for {player}")

@socketio.on("player_ready")
def handle_ready(data):
    """Khi người chơi ấn nút sẵn sàng"""
    game_id = data["game_id"]
    player = data["player"]

    game = db.session.get(Game, game_id)
    if not game:
        return

    # Gắn cờ đã sẵn sàng
    if game.player and game.player.playername == player:
        game.player_ready = True
    elif game.opponent and game.opponent.playername == player:
        game.opponent_ready = True

    db.session.commit()

    # Kiểm tra nếu cả 2 đã sẵn sàng
    if (game.player_ready and (game.opponent_ready or game.ai_ready)):
        game.status = "battle"
        
        #dính lỗi này cay quá!!
        if not game.current_turn:
            try:
                game.current_turn = game.player.playername
            except Exception:
                # fallback: nếu thiếu dữ liệu, lấy opponent
                game.current_turn = game.opponent.playername if game.opponent else None
        db.session.commit()
        socketio.emit("both_ready", {"game_id": game.id}, to=str(game.id))
        socketio.emit("turn_change", {
            "current_turn": game.current_turn,
            "is_ai_turn": (game.ai and game.current_turn == game.ai.name)
        }, to=str(game.id))


#Người bắn  
@socketio.on("player_fire")
def handle_fire(data):
    from app.game_logic.base_logic import GameLogic
    from app.socket_helpers import process_shot_result

    game_id = data["game_id"]
    player_name = data["player"]
    x, y = int(data["x"]), int(data["y"])

    game = db.session.get(Game, game_id)
    if not game:
        return emit("error", {"message": "Game không tồn tại"}, to=request.sid)

    # Kiểm tra lượt
    if game.current_turn != player_name:
        return emit("error", {"message": "Chưa đến lượt bạn!"}, to=request.sid)


    # Xác định đối thủ
    if game.opponent and game.player.playername == player_name:
        opponent_name = game.opponent.playername 
    elif game.opponent and game.opponent.playername == player_name:
        opponent_name = game.player.playername
    elif game.ai:
        opponent_name = game.ai.name
    else:
        return emit("error", {"message": "Không xác định được đối thủ"}, to=request.sid)
    
    print(f"[DEBUG] Đối thủ sẽ bắn là {opponent_name}")

    # Xử lý bắn
    logic = GameLogic(game)
    result_data = logic.shoot(attacker_name=player_name, target_name=opponent_name, x=x, y=y)
    db.session.commit()

    game_over = process_shot_result(game, result_data, player_name, opponent_name, x, y)
    if game_over:
        return

#AI bắn
@socketio.on("ai_make_shot")
def handle_ai_make_shot(data):
    from app.models import Game
    from app.ai.factory import get_ai_instance
    from app.socket_helpers import process_shot_result
    from app import db, socketio

    sleep(0.25)
    game_id = data.get("game_id")
    game = db.session.get(Game, game_id)
    if not game or not game.ai:
        return emit("error", {"message": "Không tìm thấy AI!"}, to=request.sid)

    ai = get_ai_instance(game)
    print(f"[DEBUG] AI {ai.name} bắt đầu bắn...")

    # Gọi logic AI bắn

    result_data = ai.make_shot(
        attacker_name=game.ai.name,
        target_name=game.player.playername
    )
    db.session.commit()

    process_shot_result(game, result_data, game.ai.name, game.player.playername)
