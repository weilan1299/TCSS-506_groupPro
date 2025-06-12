import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_dance.contrib.github import make_github_blueprint, github
from dotenv import load_dotenv

load_dotenv()

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
app = Flask(__name__)
app.config['SECRET_KEY']="cfa2f205ad8f7196954a5050e98cc199"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'


#GitHub OAuth
github_bp = make_github_blueprint(client_id=os.getenv("GIT_CLIENT_ID"),
                                   client_secret=os.getenv("GIT_CLIENT_SECRET"),
                                  redirect_to="github_login")

app.register_blueprint(github_bp, url_prefix='/login')

db = SQLAlchemy(app)
migrate = Migrate(app, db)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

app.config['MAIL_SERVER'] = 'smtp.googlemail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("EMAIL_ADDRESS")
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASSWORD')
mail= Mail(app)

from main import routes
