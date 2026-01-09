import numpy as np  
import json
import random
from app import db
from app.models import Player, ShipPlacement
from app.ai.ai_interface import BaseAI

class ProbAI(BaseAI):
    """
    AI dùng phổ mật độ xác xuất để quyết định phát bắn
    Phổ dựa trên số lượng cấu hình có thể đặt được ở một ô
    """
    
    def __init__(self, game, name = None):
        super().__init__(game, name)

            
    def place_ships(self):
        """ Ưu tiên đặt ở góc (Tránh các ô ở giữa) """
        board = self.auto_place_ships_strategy(self.name, strategy="avoid center")
        return board
    
    def make_shot(self, attacker_name, target_name):
        board = self.get_board(target_name)
        if not board:
            self.log_action(f"Không tìm thấy bảng của {target_name}")
            return {"result": "invalid", "x": -1, "y": -1}
        
        ships_alive = self.get_ships_alive(target_name)
        self.log_action(f"Tàu còn sống: {ships_alive}")
        
        prob_matrix = np.zeros((10, 10), dtype= int)
        
        hits = [] #lưu vị trí có hit
        for x in range(0, 9):
            for y in range(0, 9):
                if board[x][y] == 2:
                    hits.append((x,y))
        if hits:
            self.log_action(f"Tìm thấy phát bắn trúng -> Target Mode")
        else:
            self.log_action(f"Không tìm thấy phát bắn trúng -> Hunt Mode")
        
        # Tính toán hàm mật độ
        for ship_name, lenght in ships_alive:
            self.log_action(f"Tính toán phổ mật độ cho tàu {ship_name}({lenght})")
            prob_matrix += self.cacl_prob_matrix(board, lenght, hits)
            self.log_action(f"Đã xong, cập nhật phổ", prob_matrix = prob_matrix.tolist())
        
        self.log_action(f"Xem xét phổ để lựa chọn phát bắn")
        possible_move = []
        best_val = -1e9
        for x in range(10):
            for y in range(10):
                if prob_matrix[x][y] > best_val:
                    best_val = prob_matrix[x][y]
                    possible_move.clear()
                    possible_move.append((x, y))
                elif prob_matrix[x][y] == best_val:
                    possible_move.append((x, y))
        self.log_action(f"Danh sách ô có thể bắn: {possible_move}", possible_moves=possible_move)


        choice = random.choice(possible_move)
        x, y = choice
        self.log_action(f"Quyết định bắn tại ({x}, {y})", selected_move=[x, y])

        
        result_data = self.shoot(attacker_name, target_name, x, y)
        result_data.update({"x": x, "y": y})
        db.session.commit()
        self.log_action(f"Kết quả tại ({x}, {y}): {result_data['result']}", shot_result={"x": x, "y": y, "result": result_data['result']})
        return result_data

    
#-------------------------------------------------------------------------------------------------------
    
    def cacl_prob_matrix(self, board, lenght, hits = []):
        """
        Tính toán phổ mật độ xác xuất
        """
        prob_matrix = np.zeros((10, 10), dtype= int)
       
        target_mode = True if hits else False
        for x in range(10):
            for y in range(10):
                for orientation in ["H", "V"]:
                    valid = True
                    cells = []
                    hit_overlap = False
                    
                    for i in range(lenght):
                        nx = x + (i if orientation == "V" else 0)
                        ny = y + (i if orientation == "H" else 0)
                        if not self.in_bounds(nx, ny):
                            valid = False
                            break
                        if board[nx][ny] in [3, 4]:
                            valid = False
                            break
                        if board[nx][ny] == 2:
                            hit_overlap = True
                        cells.append((nx, ny))
                    
                    if valid:
                        if target_mode and not hit_overlap:
                            continue
                        for (nx, ny) in cells:
                            if board[nx][ny] == 2:
                                prob_matrix[nx][ny] = -1
                            else: 
                                prob_matrix[nx][ny] += 1
        return prob_matrix
              

    def get_ships_alive(self, owner_name):
        """
        Lấy danh sách các tàu còn sống, chiều dài giảm dần
        """
        placement = db.session.scalar(
            db.select(ShipPlacement)
            .where(ShipPlacement.game_id == self.game.id)
            .where(ShipPlacement.owner == owner_name)
        )
        
        data = json.loads(placement.ship_data)
        ships_alive = []
        for ship_name, lenght in self.ships.items():
            if not data[ship_name]["sunked"]:
                ships_alive.append((ship_name, lenght))
        
        return ships_alive
            

    
        