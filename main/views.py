from flask import Blueprint
from flask import Flask
main_blueprint = Blueprint('main', __name__)
app = Flask(__name__)

@main_blueprint.route('/')
def home():
    app.logger.debug('Debug level log')
    app.logger.info('Info level log')
    app.logger.warning('Warning level log')
    app.logger.error('Error level log')
    app.logger.critical('Crirical level log')
    return 'Hello, World'

    return '메인 페이지입니다.'

