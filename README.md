# Battle-Ship

### linux configuration(this is mine)
0. python -m venv venv
1. source venv/bin/activate
2. pip install flask flask_sqlalchemy flask_migrate flask_login flask_socketio eventlet Flask-WTF numpy
3. python run_game.py
4. stop running: ps aux | grep run_game.py
kill <PID> or ctrl + C

5. pip freeze > requirements.txt


### everyone have to do after clone repo 
1. python -m venv venv
2. source venv/bin/activate 
3. pip install -r requirements.txt
4.  flask db init        # Khởi tạo thư mục migrations/
    flask db migrate -m "Initial migration"
    flask db upgrade     # Tạo file app.db cục bộ

5. python run_game.py

> note: lets convert these commands to windows command if you use windows os
