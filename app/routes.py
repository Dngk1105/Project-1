from app import app, db, socketio
from flask_socketio import emit, join_room, leave_room
from app.forms import EnterNameForm, NewGameForm, StartGameForm, CancelGameForm, JoinGame
from flask import render_template, flash, redirect, url_for, request
from urllib.parse import urlsplit
from app.models import Player, Game, ShipPlacement, AI
import sqlalchemy as sa
from flask_login import current_user, login_user, logout_user, login_required
import json
from app.game_logic.base_logic import GameLogic
from app.ai.factory import get_ai_instance



@app.route('/')
@app.route('/index')
@login_required
def index() : 
    from app.game_logic.queries import overall, overall_probability_matrix
    overall_data = overall()
    prob_matrix = overall_probability_matrix()
    return render_template('index.html', title = 'Trang chủ', overall_data = overall_data, prob_matrix = prob_matrix)

@app.route('/entername', methods = ['GET', 'POST'])
def entername():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = EnterNameForm()
    if form.validate_on_submit():
        player = db.session.scalar(
            sa.select(Player).where(Player.playername == form.playername.data)
        )
        
        if player is None:
            player = Player(playername = form.playername.data)
            db.session.add(player)
            db.session.commit()
            flash('Tạo người chơi mới tên {} thành công!'.format(form.playername.data))
        
        login_user(player, remember=form.remember.data)
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('index')
        
        return redirect(next_page)

    return render_template('entername.html', title='Nhập tên', form=form)

@app.route('/changename')
def changename():
    logout_user()
    return redirect(url_for('index'))

@app.route('/player/<playername>')
@login_required
def player(playername):
    player = db.first_or_404(
        sa.select(Player).where(Player.playername == playername)
    )
    
    return render_template('player.html', player = player)
    
@app.route('/statistic/player/<playername>')
@login_required
def player_statistic(playername):
    player = db.first_or_404(sa.select(Player).where(Player.playername == playername))
    return render_template('statistic/player_statistic.html', player=player)

@app.route('/game_detail/<game_id>')
def game_detail(game_id):
    game = db.first_or_404(sa.select(Game).where(Game.id == game_id))
    
    
    # Lấy ma trận
    placements = db.session.scalars(
        sa.select(ShipPlacement)
        .where(ShipPlacement.game_id == game.id)
    ).all()
    
    player_grid = None
    opponent_grid = None
    guest_name = None
    host_name = None
    player_ships = {}
    opponent_ships = {}
    
    
    for p in placements:
        grid = json.loads(p.grid_data)
        ship_data = json.loads(p.ship_data or "{}")
        
        if p.owner == game.player.playername:
            player_grid = grid
            player_ships = ship_data
            host_name = game.player.playername
        elif game.opponent and p.owner == game.opponent.playername:
            opponent_grid = grid
            opponent_ships = ship_data
            guest_name = game.opponent.playername
        elif game.ai and p.owner == game.ai.name:
            opponent_grid = grid
            opponent_ships = ship_data
            guest_name = game.ai.name
            
    # Tạo danh sách tàu đã chìm / còn sống
    def summarize_ships(ships):
        sunked = [name for name, info in ships.items() if info.get("sunked")]
        alive = [name for name, info in ships.items() if not info.get("sunked")]
        return sunked, alive

    player_sunked, player_alive = summarize_ships(player_ships)
    opponent_sunked, opponent_alive = summarize_ships(opponent_ships)
    
    return render_template(
        "game_detail.html",
        game=game,
        player_grid=player_grid,
        opponent_grid=opponent_grid,
        host_name = host_name,
        guest_name = guest_name,
        player_sunked=player_sunked,
        opponent_sunked=opponent_sunked,
        player_alive=player_alive,
        opponent_alive=opponent_alive
    )
    
@app.route('/new_game', methods = ['GET', 'POST'])
@login_required
def new_game():
    form = NewGameForm()
    form.ai_type.choices = [(ai.name, ai.name) for ai in db.session.scalars(sa.select(AI)).all()]

    if form.validate_on_submit():
        # Nếu chọn đấu với AI
        if form.mode.data == "ai":
            ai_name = form.ai_type.data

            ai = db.session.scalar(sa.select(AI).where(AI.name == ai_name))
            
            new_game = Game(
                player=current_user,
                ai=ai,
                winner="",
                player_shots = 0,
                opponent_shots = 0,
                summary="",
                status="active"
            )
            db.session.add(new_game)
            db.session.commit()

            flash(f"Đã tạo trận đấu với AI: {ai_name}", "success")
            return redirect(url_for("game_hall", game_id=new_game.id))
        
        #Đấu với người
        elif form.mode.data == "human":
            # Tạo game, dùng id làm mã mời
            new_game = Game(
                player=current_user,
                winner="",
                player_shots=0,
                opponent_shots=0,
                summary="Trận người-người đang chờ đối thủ.",
                status="pending"
            )
            db.session.add(new_game)
            db.session.commit()

            return redirect(url_for("game_hall", game_id=new_game.id))
    
    return render_template("new_game.html", form=form)

@app.route('/join', methods=['GET', 'POST'])
@login_required
def join_hall():
    form = JoinGame()
    if form.validate_on_submit():
        return redirect(url_for("join", game_id=form.game_id.data))
    return render_template("join_game.html", form=form)


@app.route('/join/<game_id>')
@login_required
def join(game_id):
    game = db.session.scalar(
        sa.select(Game)
        .where(Game.id == game_id )
        )
    if not game:
        flash("Không tìm game nào cả!")
        return redirect(url_for("index"))
    
    if (game.opponent_id is not None) or (game.ai):
        flash("Có người rồi")
        return redirect(url_for("index"))
    
    game.opponent_id = current_user.id 
    game.status = 'active'
    db.session.commit()
    socketio.emit(
        "player_joined",
        {
            "game_id": game.id,
            "opponent_name": current_user.playername
        },
        to=str(game.id)  # gửi đến "room" cùng tên với id game
    )
        
    flash(f"Đã tham gia sảnh #{game.id}!")
    return redirect(url_for("game_hall", game_id=game.id))



@app.route('/game_hall/<int:game_id>', methods = ['GET', 'POST'])
@login_required
def game_hall(game_id):
    game = db.first_or_404(sa.select(Game).where(Game.id == game_id))
    
    if not game:
        flash("Không tìm thấy trận đấu!", "danger")
        return redirect(url_for("index"))
    
    start_form = StartGameForm()
    cancel_form = CancelGameForm()
    
    if request.method == "POST":
        action = request.form.get("action")

        if action == "start" and start_form.validate():
            db.session.refresh(game)  # cập nhật trạng thái mới nhất từ DB
            if game.status != "active":
                flash("Trận chưa sẵn sàng để bắt đầu!", "warning")
            else:
                game.status = "in_progress"
                db.session.commit()
                flash("Trận đấu đã bắt đầu!", "success")
                
                
                if game.ai_id :
                    flash("Bắt đầu trận đấu với AI!", "success")
                    return redirect(url_for("game_setup", game_id=game.id))
                else :
                    socketio.emit(
                        "game_started",
                        {"game_id": game.id, "redirect_url": url_for("game_setup", game_id=game.id)},
                        to=str(game.id)
                    )
                
                flash("Trận đấu bắt đầu chuyển sang giai đoạn đặt tàu!", "success")
                return redirect(url_for("game_setup", game_id=game.id))

        elif action == "cancel" and cancel_form.validate():
            
            if current_user.id == game.player_id:
                game.status = "canceled"
                db.session.commit()
                socketio.emit("game_canceled", {"game_id": game.id}, to=str(game.id))
                return redirect(url_for("index"))
            
            
            elif current_user.id == game.opponent_id:
                game.opponent_id = None
                game.status = "pending"
                db.session.commit()
                socketio.emit("opponent_left", {"game_id": game.id}, to=str(game.id))
                return redirect(url_for("index"))
    
    invite_link = None
    if game.status == "pending":
        invite_link = url_for("join", game_id=game.id, _external=True)

    return render_template(
        "game_hall.html",
        game=game,
        invite_link=invite_link,
        start_form=start_form,
        cancel_form=cancel_form
    )
    
    
@app.route('/game_setup/<int:game_id>')
@login_required
def game_setup(game_id):
    """
    Trang đặt tàu cho người chơi.
    """
    game = db.first_or_404(sa.select(Game).where(Game.id == game_id))

    # Nếu game chưa ở trạng thái 'in_progress' thì không được vào
    if game.status not in ["in_progress", "setup"]:
        flash("Trận đấu chưa sẵn sàng!", "warning")
        return redirect(url_for("game_hall", game_id=game.id))

    logic = GameLogic(game)

    # Tạo bảng trống nếu chưa có
    player_name = current_user.playername
    board = logic.get_board(player_name)
    if not board:
        logic.init_board(player_name)

    # Nếu là AI đối thủ → tự động sẵn sàng
    if game.ai and not logic.get_board(game.ai.name):
        game.ai_ready = True
        db.session.commit()

    return render_template(
        "game_setup.html",
        game=game,
        player_name=player_name,
        ships=list(logic.ships.keys())
    )


@app.route("/game_battle/<int:game_id>")
@login_required
def game_battle(game_id):
    game = db.get_or_404(Game, game_id)
    player_name = current_user.playername
    is_host = (game.player.playername == player_name)
    game.current_turn = game.player.playername
    db.session.commit()

    # xác định đối thủ
    if game.ai:
        opponent_name = game.ai.name
        ai = get_ai_instance(game)
        ai.place_ships()
    elif is_host and game.opponent:
        opponent_name = game.opponent.playername
    elif not is_host:
        opponent_name = game.player.playername

    # lấy bảng
    player_placement = db.session.scalar(
        db.select(ShipPlacement)
        .where(ShipPlacement.game_id == game_id)
        .where(ShipPlacement.owner == player_name)
    )
    opponent_placement = db.session.scalar(
        db.select(ShipPlacement)
        .where(ShipPlacement.game_id == game_id)
        .where(ShipPlacement.owner == opponent_name)
    )

    player_board = json.loads(player_placement.grid_data) if player_placement else None
    opponent_board = json.loads(opponent_placement.grid_data) if opponent_placement else None

    return render_template(
        "game_battle.html",
        game=game,
        player_name=player_name,
        opponent_name=opponent_name,
        player_board=json.dumps(player_board),
        opponent_board=json.dumps(opponent_board),
        is_host=is_host
    )
    
    
@app.route("/render_matrix", methods=["POST"])
def render_matrix():
    data = request.get_json()
    matrix = data.get("matrix")
    heatmap = data.get("heatmap", False)
    return render_template("statistic/_stat_table.html", matrix=matrix, heatmap=heatmap)