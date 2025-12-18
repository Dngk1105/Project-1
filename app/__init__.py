from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from datetime import datetime, timedelta
import sqlalchemy as sa
from flask_socketio import SocketIO 

app = Flask(__name__)
app.config.from_object(Config)
socketio = SocketIO(app, cors_allowed_origins="*")
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login = LoginManager(app)
login.login_view = 'entername'
login.login_message = "Nhập tên trước khi vào bạn nhé!"

from app import routes, models, socket_events
