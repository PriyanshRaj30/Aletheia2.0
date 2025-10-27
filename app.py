from flask import Flask, jsonify
from flask_cors import CORS
from config import config
from models import db
from auth import auth_bp, login_manager
import os
import logging

def create_app(config_name='development'):
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    app.logger.setLevel(logging.INFO)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    
    # CORS configuration
    CORS(app, 
         resources={r"/*": {"origins": app.config['FRONTEND_URL']}},
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization"],
         expose_headers=["Content-Type"],
         methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    
    # Register authentication blueprint
    app.register_blueprint(auth_bp)
    
    # Create database tables
    with app.app_context():
        db.create_all()
        app.logger.info("✓ Database tables created")
    
    # Root route
    @app.route('/')
    def index():
        return jsonify({
            'message': 'Bookshelf AR API',
            'version': '1.0',
            'status': 'running',
            'endpoints': {
                'auth_login': '/auth/login',
                'auth_status': '/auth/status',
                'health': '/health'
            }
        }), 200
    
    # Health check
    @app.route('/health')
    def health():
        try:
            # Test database connection
            db.session.execute('SELECT 1')
            db_status = 'connected'
        except Exception as e:
            app.logger.error(f"Database health check failed: {e}")
            db_status = 'disconnected'
        
        return jsonify({
            'status': 'healthy',
            'database': db_status
        }), 200
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({
            'error': 'not_found',
            'message': 'The requested resource was not found'
        }), 404
    
    @app.errorhandler(500)
    def internal_error(e):
        app.logger.error(f"Internal error: {e}")
        return jsonify({
            'error': 'internal_error',
            'message': 'An internal server error occurred'
        }), 500
    
    return app


if __name__ == '__main__':
    # Allow HTTP for local development (REMOVE IN PRODUCTION)
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    
    app = create_app('development')
    
    print("\n" + "="*50)
    print("🚀 Bookshelf AR API Server Starting")
    print("="*50)
    print(f"📍 Running on: http://localhost:5000")
    print(f"🔐 Login URL: http://localhost:5000/auth/login")
    print(f"❤️  Health Check: http://localhost:5000/health")
    print("="*50 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)