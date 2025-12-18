# place_ships_strat.py
import random
from app import db
from app.game_logic.base_logic import GameLogic   

class ShipPlacementStrategy(GameLogic):

    def strategy_random(self, board, ship_name, length, owner):
        """Random"""
        placed = False
        while not placed:
            orientation = random.choice(["H", "V"])
            x = random.randint(0, 9)
            y = random.randint(0, 9)
            if self.can_place(board, x, y, length, orientation):
                board = self.place_ship(board, x, y, length, orientation, ship_name, owner)
                placed = True
        return board

    #----------------------------------------------------------------------------------------------
    
    def strategy_avoid_mid_corner(self, board, ship_name, length, owner):
        """Tránh đặt tàu ở giữa và 2 bên rìa"""
        invalid = {0, 4 ,5 , 9}
        placed = False
        attempts = 0
        max_attempts = 100
        while not placed and attempts < max_attempts:  
            attempts += 1
            if random.random() < 0.9:
                orientation = "V"
            else:
                orientation = "H"
            
            x = random.randint(0, 9)
            y = random.randint(0, 9)
            
            if self.can_place_avoid_mid_corner(board, x, y, length, orientation):
                placed = True
                board = self.place_ship(board, x, y, length, orientation, ship_name, owner)
        if not placed:
            board = self.strategy_random(board, ship_name, length, owner)
        return board
            
    #----------------------------------------------------------------------------------------------
    
    def strategy_avoid_adjacent(self, board, ship_name, length, owner):
        """Tránh xếp sát nhau"""
        placed = False
        attempts = 0
        max_attempts = 100
        while not placed and attempts < max_attempts:
            attempts += 1
            orientation = random.choice(["H", "V"])
            x = random.randint(0, 9)
            y = random.randint(0, 9)
            if self.can_place_avoid_adjacent(board, x, y, length, orientation):
                board = self.place_ship(board, x, y, length, orientation, ship_name, owner)
                placed = True
                
        if not placed:
            board = self.strategy_random(board, ship_name, length, owner)
        return board
    
    #----------------------------------------------------------------------------------------------
   
    # def strategy_cluster(self, board, ship_name, length, owner):
    #     """Xếp tàu theo từng cụm"""
    #     placed = False
    #     attempts =0
    #     max_attempts = 100
        
   
   #================================================================================================
    def auto_place_ships_strategy(self, owner_name, strategy="random"):
        board = self.init_board(owner_name)

        strat_map = {
            "random": self.strategy_random,
            "avoid mid and corner": self.strategy_avoid_mid_corner,
            "avoid adjacent": self.strategy_avoid_adjacent
        }

        strat_func = strat_map.get(strategy, self.strategy_random)

        for ship_name, length in self.ships.items():
            board = strat_func(board, ship_name, length, owner_name)

        self.save_board(owner_name, board)
        return board

    def can_place_avoid_mid_corner(self, board, x, y, length, orientation):
        """Kiểm tra vị trí có thể đặt tàu tránh giữa và rìa"""
        invalid = {0, 4, 5, 9}
        size = len(board)


        if orientation == "V":
            for row in range(x, x + length):
                if y in invalid:
                    return False
        else:  # "H"
            for col in range(y, y + length):
                if x in invalid:
                    return False

        # Kiểm tra chồng tàu khác
        if not self.can_place(board, x, y, length, orientation):
            return False

        return True


    def can_place_avoid_adjacent(self, board, x, y, length, orientation):
        """Check có thể đặt tàu mà không sát tàu khác"""
        for i in range(length):
            nx = x + (i if orientation == "V" else 0)
            ny = y + (i if orientation == "H" else 0)
            
            if not self.in_bounds(nx, ny):
                return False
            
            if board[nx][ny] != 0:
                return False
            
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                adjx, adjy = nx + dx, ny + dy
                if not (0 <= adjx < len(board) and 0 <= adjy < len(board[0])):
                    continue
                if board[adjx][adjy] == 1:
                    return False
                
        return True