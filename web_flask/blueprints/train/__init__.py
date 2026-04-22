from flask import Blueprint

train_bp = Blueprint('train', __name__, template_folder='../templates')

from . import views