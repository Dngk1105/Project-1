import json
from app import db
from app.models import ShipPlacement, Player, GameMove
import sqlalchemy as sa
import random

class GameLogic:
    """
    Lớp xử lý toàn bộ logic của trò chơi Battleship.
    """

    def __init__(self, game):
        self.game = game

        # Định nghĩa độ dài tàu
        self.ships = {
            "Carrier": 5,
            "Battleship": 4,
            "Cruiser": 3,
            "Submarine": 3,
            "Destroyer": 2,
        }

        # Lưu vị trí từng tàu (cho cả 2 bên)
        # { "player": { "Carrier": [(x1,y1), (x2,y2)...], ... }, "opponent": {...} }
        self.ship_positions = {
            self.game.player.playername: {},
            (self.game.opponent.playername if self.game.opponent else self.game.ai.name): {}
        }

    # --------------------------- Qlí bảng ---------------------------

    def init_board(self, owner_name, size=10):
        """Tạo ma trận trống cho người chơi, nếu chưa có thì khởi tạo."""
        empty_board = [[0 for _ in range(size)] for _ in range(size)]

        # Kiểm tra xem đã có record cho người chơi này trong game chưa
        placement = db.session.scalar(
            db.select(ShipPlacement)
            .where(ShipPlacement.game_id == self.game.id)
            .where(ShipPlacement.owner == owner_name)
        )

        if placement:
            # Nếu đã tồn tại thì chỉ cập nhật lại grid_data (reset bảng)
            placement.grid_data = json.dumps(empty_board)
            if placement.ship_data is None:
                placement.ship_data = json.dumps({})
        else:
            # Nếu chưa có thì tạo mới
            placement = ShipPlacement(
                game_id=self.game.id,
                owner=owner_name,
                grid_data=json.dumps(empty_board),
                ship_data=json.dumps({})  # đảm bảo không bị None
            )
            db.session.add(placement)

        db.session.commit()
        print(f"[DEBUG] init_board() -> Đảm bảo chỉ có 1 ShipPlacement cho {owner_name}")
        return empty_board


    def get_board(self, owner_name):
        """Lấy ma trận từ database"""
        placement = db.session.scalar(
            db.select(ShipPlacement)
            .where(ShipPlacement.game_id == self.game.id)
            .where(ShipPlacement.owner == owner_name)
        )
        if not placement:
            return None
        return json.loads(placement.grid_data)

    def save_board(self, owner_name, board):
        """Cập nhật ma trận của người chơi"""
        placement = db.session.scalar(
            db.select(ShipPlacement)
            .where(ShipPlacement.game_id == self.game.id)
            .where(ShipPlacement.owner == owner_name)
        )

        if placement:
            placement.grid_data = json.dumps(board)
        else:
            placement = ShipPlacement(
                game_id=self.game.id,
                owner=owner_name,
                grid_data=json.dumps(board),
            )
            db.session.add(placement)

        db.session.commit()

    # --------------------------- CORE LOGIC ---------------------------

    def in_bounds(self, x, y, size=10):
        """Kiểm tra toạ độ nằm trong bảng"""
        return 0 <= x < size and 0 <= y < size

    def can_place(self, board, x, y, length, orientation):
        """Kiểm tra xem có thể đặt tàu tại vị trí (x, y) không
            - Không vượt biên
            - Không đè tàu khác
            - Không chạm tàu khác (kể cả chéo)  // tạm thời bỏ 
        """
        for i in range(length):
            nx = x + (i if orientation == "V" else 0)
            ny = y + (i if orientation == "H" else 0)
            
            if not self.in_bounds(nx, ny):
                return False
            
            if board[nx][ny] != 0:
                return False
            
            # for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            #     adjx, adjy = nx + dx, ny + dy
            #     if not (0 <= adjx < len(board) and 0 <= adjy < len(board[0])):
            #         continue
            #     if board[adjx][adjy] == 1:
            #         return False
                
        return True

    def place_ship(self, board, x, y, length, orientation, ship_name, owner):
        """Đặt tàu lên bảng và lưu vị trí"""

        # Kiểm tra nếu tàu này đã được đặt
        if ship_name in self.ship_positions[owner]:
            return None

        # Kiểm tra vị trí có thể đặt được không
        if not self.can_place(board, x, y, length, orientation):
            return None

        # Đặt tàu
        positions = []
        for i in range(length):
            nx = x + (i if orientation == "V" else 0)
            ny = y + (i if orientation == "H" else 0)
            board[nx][ny] = 1
            positions.append((nx, ny))

        self.ship_positions[owner][ship_name] = positions
        # Lưu vào ShipPlacement.ship_data
        placement = db.session.scalar(
            db.select(ShipPlacement)
            .where(ShipPlacement.game_id == self.game.id)
            .where(ShipPlacement.owner == owner)
        )
        if placement:
            data = json.loads(placement.ship_data or "{}")
            data[ship_name] = {
                "positions": positions,
                "sunked": False
            }
            placement.ship_data = json.dumps(data)
            placement.grid_data = json.dumps(board)
        else:
            placement = ShipPlacement(
                game_id=self.game.id,
                owner=owner,
                grid_data=json.dumps(board),
                ship_data=json.dumps({
                    ship_name: {"positions": positions, "sunked": False} 
                }),
            )
            db.session.add(placement)

        db.session.commit()
        print(f"[DEBUG] Cập nhật ship_data cho owner={owner}")
        try:
            current_data = json.loads(placement.ship_data or "{}")
            for name, info in current_data.items():
                pos = info.get("positions", [])
                sunk = info.get("sunked", False)
                print(f"  └─ {name}: {len(pos)} ô, sunked={sunk}, positions={pos}")
        except Exception as e:
            print(f"[DEBUG] Lỗi khi in ship_data của {owner}: {e}")
        return board
    
    def auto_place_ships(self, owner_name): 
        board = self.init_board(owner_name) 
        for ship_name, length in self.ships.items(): 
            placed = False 
            while not placed: 
                orientation = random.choice(["H", "V"]) 
                x = random.randint(0, 9) 
                y = random.randint(0, 9) 
                if self.can_place(board, x, y, length, orientation): 
                    board = self.place_ship(board, x, y, length, orientation, ship_name, owner_name) 				
                    placed = True 
        self.save_board(owner_name, board) 
        print(f"[DEBUG] auto_place_ships() -> Đặt bảng xong rùi đó {owner_name}")
        return board

    # --------------------------- SHOOTING LOGIC ---------------------------

    def shoot(self, attacker_name, target_name, x, y):
        """
        Xử lý phát bắn giữa 2 người (attacker → target)
        Trả về: {"result": "hit/miss/sunk/already_hit/out_of_bounds", "winner": optional_name}
        """
        print(f"[DEBUG] {attacker_name} bắn ({x},{y}) vào {target_name}")

        board = self.get_board(target_name)
        if not board:
            print(f"[DEBUG] Không tìm thấy bảng của {target_name}")
            return {"result": "invalid", "winner": None}

        # Nếu người chơi bắn phát mới, các nước đi đã được undo để chờ redo sẽ bị xóa
        db.session.execute(
            sa.delete(GameMove)
            .where(GameMove.game_id == self.game.id, GameMove.is_reverted == True)
        )

        # Kiểm tra toạ độ hợp lệ
        if not self.in_bounds(x, y):
            print(f"[DEBUG] Toạ độ ({x},{y}) ngoài phạm vi bảng!")
            return {"result": "out_of_bounds", "winner": None}

        cell = board[x][y]
        print(f"[DEBUG] Trạng thái ô ({x},{y}) trước khi bắn: {cell}")
        ship_name = None
        result = None
        prev_cell = cell    #Lưu trạng thái cũ để undo

        # --- Xử lý các trường hợp ---
        if cell == 0:
            board[x][y] = 3
            result = "miss"
            print(f"[DEBUG] Bắn trượt ({x},{y})")

        elif cell == 1:
            board[x][y] = 2
            print(f"[DEBUG] Bắn trúng tàu tại ({x},{y})")
            ship_name, comp = self._get_ship_component(target_name, x, y)
            print(f"[DEBUG] Component tàu {ship_name} gồm {len(comp)} ô: {comp}")
            
            if comp and self._is_component_sunk(comp, board):
                self._mark_component_sunk(comp, board)
                result = "sunk"
                print(f"[DEBUG] Toàn bộ tàu đã chìm! Đánh dấu ô: {comp}")
                
                sunked_ship = ship_name
                if sunked_ship:
                    self._record_ship_sunk(target_name, sunked_ship)

            else:
                result = "hit"
                print(f"[DEBUG] Tàu chưa chìm hoàn toàn.")

        elif cell in (2, 3, 4):
            result = "already_hit"
            print(f"[DEBUG] Ô ({x},{y}) đã bị bắn trước đó.")

        # --- Lưu lại thay đổi ---
        self.save_board(target_name, board)
        print(f"[DEBUG] Đã lưu trạng thái mới của bảng {target_name}")

        # --- Cập nhật thống kê ---
        if attacker_name == getattr(self.game.player, "playername", None):
            self.game.player_shots += 1
            print(f"[DEBUG] +1 lượt bắn cho player {attacker_name}")
        elif attacker_name == getattr(self.game.opponent, "playername", None):
            self.game.opponent_shots += 1
            print(f"[DEBUG] +1 lượt bắn cho opponent {attacker_name}")
        elif attacker_name == getattr(self.game.ai, "name", None):
            self.game.opponent_shots += 1
            print(f"[DEBUG] +1 lượt bắn cho opponent {attacker_name}")

        #Tạo bản ghi undo/redo
        game_move = GameMove(
            game_id=self.game.id,
            attacker_name = attacker_name,
            target_name = target_name,
            x = x,
            y = y,
            result = result,
            game_turn = self.game.current_turn,  
            prev_cell = prev_cell,
            sunk_ship_name = ship_name if result == "sunk" else None,
            is_reverted = False
        )
        
        db.session.add(game_move)
        db.session.commit()

        # --- Kiểm tra thắng cuộc ---
        if self._all_ships_sunk(board):
            print(f"[DEBUG] {target_name} không còn tàu nào → {attacker_name} thắng trận!")
            self.game.status = "finished"
            self.game.winner = attacker_name
            
            player_win = db.session.scalar(
                sa.select(Player).where(Player.playername == attacker_name)
            )
            player_lose = db.session.scalar(
                sa.select(Player).where(Player.playername == target_name)
            )
            
            if player_win:
                player_win.wins = (player_win.wins or 0) + 1
            else:
                print(f"[ERROR] Không tìm thấy người thắng '{attacker_name}' trong bảng Player!")

            if player_lose:
                player_lose.losses = (player_lose.losses or 0) + 1
            else:
                print(f"[ERROR] Không tìm thấy người thua '{attacker_name}' trong bảng Player!")
            db.session.commit()
            print(f"[DEBUG]  Đã commit cập nhật kết quả thắng/thua vào DB.")
            
            return {
                "result": result, 
                "winner": attacker_name, 
                "owner": target_name, 
                "ship_name": ship_name, 
                "comp": comp,
                "x": x,
                "y": y
            }

        print(f"[DEBUG] Kết quả phát bắn: {result}")
        if result == 'sunk':
            return {
                "result": result,
                "winner": None,
                "owner": target_name,
                "ship_name": ship_name,
                "comp": comp,
                "x": x,
                "y": y
            }
        else: 
            return {
                "result": result, 
                "winner": None,
                "x": x,
                "y": y
            }


    # --------------------------- Xử lí undo/redo ---------------------------

    def undo_last_move(self):
        print(f"\n[DEBUG] --- BẮT ĐẦU UNDO (Game ID: {self.game.id}) ---")
        
        # undo nước đi gần nhất
        last_move = db.session.scalar(
            sa.select(GameMove)
            .where(GameMove.game_id == self.game.id,
                GameMove.is_reverted == False)
            .order_by(GameMove.id.desc())
            .limit(1)
        )
        
        if not last_move:
            print("[DEBUG] Không tìm thấy nước đi nào hợp lệ để undo (hoặc đã undo hết).")
            return None

        print(f"[DEBUG] Tìm thấy Last Move: ID={last_move.id}, Attacker={last_move.attacker_name}, Target={last_move.target_name}, Kết quả cũ={last_move.result}")

        board = self.get_board(last_move.target_name)
        
        # --- Xử lí tàu chìm ---
        # Lưu ý: Huynh kiểm tra kỹ tên trường là 'sunk_ship_name' hay 'sunked_ship_name' trong model nhé
        if last_move.result == "sunk" and last_move.sunk_ship_name:
            print(f"[DEBUG] Phát hiện tàu chìm cần khôi phục: {last_move.sunk_ship_name}")
            
            placement = db.session.scalar(
                sa.select(ShipPlacement)
                .where(ShipPlacement.game_id == self.game.id,
                        ShipPlacement.owner == last_move.target_name)
            )
            
            if placement and placement.ship_data:
                ship_data = json.loads(placement.ship_data)
                
                if last_move.sunk_ship_name in ship_data:    
                    print(f"[DEBUG] Đã tìm thấy dữ liệu tàu {last_move.sunk_ship_name} trong ShipPlacement.")
                    
                    # Bỏ đánh dấu sunk
                    ship_data[last_move.sunk_ship_name]["sunked"] = False
                    placement.ship_data = json.dumps(ship_data)
                    
                    # Khôi phục các ô thân tàu từ 4 (chìm) về 2 (trúng)
                    positions = ship_data[last_move.sunk_ship_name]["positions"]
                    count_restored = 0
                    for px, py in positions:
                        if board[px][py] == 4:
                            board[px][py] = 2
                            count_restored += 1
                    print(f"[DEBUG] Đã khôi phục {count_restored} ô thân tàu từ trạng thái 4 về 2.")
                else:
                    print(f"[DEBUG] CẢNH BÁO: Không thấy tàu {last_move.sunk_ship_name} trong ship_data!")
            else:
                print("[DEBUG] CẢNH BÁO: Không tìm thấy placement hoặc ship_data trống.")

        # --- Trả về trạng thái ban đầu của ô bị bắn ---
        current_val = board[last_move.x][last_move.y]
        board[last_move.x][last_move.y] = last_move.prev_cell
        print(f"[DEBUG] Revert ô ({last_move.x}, {last_move.y}): {current_val} -> {last_move.prev_cell}")
        
        # --- Đánh dấu Trạng thái đã quay lui ---
        last_move.is_reverted = True

        # --- Attacker được bắn lại ---
        self.game.current_turn = last_move.attacker_name
        print(f"[DEBUG] Trả lượt chơi lại cho: {self.game.current_turn}")

        # --- Xử lí thống kê ---
        if last_move.attacker_name == getattr(self.game.player, "playername", None):
            self.game.player_shots = max(0, self.game.player_shots - 1)
            print(f"[DEBUG] Giảm shot player còn: {self.game.player_shots}")
        else:
            self.game.opponent_shots = max(0, self.game.opponent_shots - 1)
            print(f"[DEBUG] Giảm shot opponent còn: {self.game.opponent_shots}")
        
        self.save_board(last_move.target_name, board)
        print(f"[DEBUG] Đã lưu board {last_move.target_name}")

        try:
            db.session.commit()
            print("[DEBUG] Commit DB thành công. Undo hoàn tất.\n")
        except Exception as e:
            print(f"[DEBUG] LỖI khi commit: {e}")
            db.session.rollback()

        return {
            "attacker": last_move.attacker_name, 
            "target": last_move.target_name,
            "board": board
        }
    
    def redo_last_move(self):
        #redo nước đi gần nhất
        next_move = db.session.scalar(
            sa.select(GameMove)
            .where(GameMove.game_id == self.game.id,
                   GameMove.is_reverted == True)
            .order_by(GameMove.id.asc())
            .limit(1)
        )
        if not next_move:
            return None

        board = self.get_board(next_move.target_name)
        comp = None
        
        if next_move.result == "miss":
            board[next_move.x][next_move.y] = 3
            self.game.current_turn = next_move.target_name
        elif next_move.result == "hit":
            board[next_move.x][next_move.y] = 2
            self.game.current_turn = next_move.attacker_name
        elif next_move.result == "already_hit":
            self.game.current_turn = next_move.attacker_name
        elif next_move.result == "sunk":
            placement = db.session.scalar(
                sa.select(ShipPlacement)
                .where(ShipPlacement.game_id == self.game.id,
                        ShipPlacement.owner == next_move.target_name)
            )
            if placement and placement.ship_data and next_move.sunk_ship_name:
                ship_data = json.loads(placement.ship_data)
                ship_data[next_move.sunk_ship_name]["sunked"] = True
                placement.ship_data = json.dumps(ship_data)
                
                positions = ship_data[next_move.sunk_ship_name]["positions"]
                comp = positions
                for px, py in positions:
                    board[px][py] = 4            
            self.game.current_turn = next_move.attacker_name
        
        next_move.is_reverted = False
        
        if next_move.attacker_name == getattr(self.game.player, "playername", None):
            self.game.player_shots += 1
        else:
            self.game.opponent_shots += 1 
            
        self.save_board(next_move.target_name, board)
        db.session.commit()

        # return để gọi process_shot_result
        return {
            "result": next_move.result,
            "attacker": next_move.attacker_name,
            "target": next_move.target_name,
            "x": next_move.x,
            "y": next_move.y,
            "winner": self.game.winner if self.game.status == "finished" else None,
            "owner": next_move.target_name,
            "ship_name": next_move.sunk_ship_name,
            "comp": comp
        }

    # --------------------------- Không phải hàm chính ---------------------------
    
    def _get_ship_component(self, target_name, x, y):
        placement = db.session.scalar(
            db.select(ShipPlacement)
            .where(ShipPlacement.game_id == self.game.id)
            .where(ShipPlacement.owner == target_name)
        )
        if not placement:
            print(f"[DEBUG] không tìm thấy bảng placement của {target_name}")
            return None
        if not placement.ship_data:
            print(f"[DEBUG] không tìm thấy bảng ship_data của {target_name}")
            return None
        
        data = json.loads(placement.ship_data)
        for ship_name, info in data.items():
            coords = info.get('positions', {})
            if [x, y] in coords:
                return ship_name, coords
        return None

    def _is_component_sunk(self, component, board):
        """True nếu không có component chưa bị bắn"""
        for (x,y) in component:
            if board[x][y] == 1:
                return False
        return True

    def _is_ship_sunk(self, owner, ship_name, board):
        """Kiểm tra nếu toàn bộ tàu đã bị trúng"""
        for (x, y) in self.ship_positions[owner][ship_name]:
            if board[x][y] not in (2, 4):
                return False
        return True

    def _mark_component_sunk(self, component, board):
        print(f"[DEBUG] Đánh dấu component đã chìm: {component}")
        for (x,y) in component:
            board[x][y] = 4


    def _all_ships_sunk(self, board):
        """Kiểm tra nếu toàn bộ tàu đã bị bắn chìm"""
        for row in board:
            for cell in row:
                if cell == 1:  # vẫn còn phần tàu chưa bị bắn
                    return False
        return True
    
    def _record_ship_sunk(self, owner_name, ship_name):
        placement = db.session.scalar(
            db.select(ShipPlacement)
            .where(ShipPlacement.game_id == self.game.id)
            .where(ShipPlacement.owner == owner_name)
        )
        if not placement or not placement.ship_data:
            return

        data = json.loads(placement.ship_data)
        if ship_name in data:
            data[ship_name]["sunked"] = True
            placement.ship_data = json.dumps(data)
            db.session.commit()

        print(f"[DEBUG] Đánh dấu {ship_name} của {owner_name} là đã chìm")
