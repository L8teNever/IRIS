import os
from flask import Flask
from models import db, Tag, Setting

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'iris-private-secret-2024'
    # Create instance folder and ensure it's writable
    instance_path = os.path.join(BASE_DIR, 'instance')
    os.makedirs(instance_path, exist_ok=True)
    
    db_path = os.path.join(instance_path, 'iris.db')
    
    # SELF-HEALING: If Docker created a directory named 'iris.db', delete it
    if os.path.exists(db_path) and os.path.isdir(db_path):
        import shutil
        shutil.rmtree(db_path)
        
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.abspath(db_path)}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    db.init_app(app)

    from routes import register_routes
    register_routes(app)

    with app.app_context():
        db.create_all()
        _seed_defaults()

    return app


def _seed_defaults():
    # Seed default settings
    defaults = {
        'theme': 'dark',
        'app_name': 'IRIS',
        'default_category': 'persoenlich',
    }
    for key, value in defaults.items():
        if not Setting.query.get(key):
            db.session.add(Setting(key=key, value=value))

    # Seed preset tags
    preset_tags = [
        ('Wichtig',     '#B3261E'),
        ('Privat',      '#6750A4'),
        ('Arbeit',      '#1565C0'),
        ('Schule',      '#2E7D32'),
        ('Gesundheit',  '#E91E63'),
        ('Finanzen',    '#F9A825'),
        ('Familie',     '#FF5722'),
        ('Freunde',     '#009688'),
        ('Hobby',       '#8BC34A'),
        ('Reise',       '#00BCD4'),
    ]
    for name, color in preset_tags:
        if not Tag.query.filter_by(name=name).first():
            db.session.add(Tag(name=name, color=color))

    db.session.commit()


if __name__ == '__main__':
    app = create_app()
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=debug, host='0.0.0.0', port=5000)
