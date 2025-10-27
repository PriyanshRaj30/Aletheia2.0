from flask import Flask, request, redirect, session, jsonify, render_template_string
from supabase import create_client, Client
import os
from functools import wraps
from datetime import datetime
import logging
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# Configuration - USE ENVIRONMENT VARIABLES IN PRODUCTION
app.config.update(
    SECRET_KEY=os.getenv('SECRET_KEY'),
    SESSION_COOKIE_SECURE=True,  # HTTPS only
    SESSION_COOKIE_HTTPONLY=True,  # Prevent XSS
    SESSION_COOKIE_SAMESITE='Lax',  # CSRF protection
    PERMANENT_SESSION_LIFETIME=3600  # 1 hour
)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://asfitcnldphtulfpaarp.supabase.co/')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'your-anon-key-here')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==================== DECORATORS ====================
def login_required(f):
    """Decorator to protect routes requiring authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'access_token' not in session:
            return redirect('/login')
        
        # Verify token is still valid
        try:
            supabase.auth.get_user(session['access_token'])
        except:
            session.clear()
            return redirect('/login')
            
        return f(*args, **kwargs)
    return decorated_function

# ==================== DATABASE OPERATIONS ====================
def get_or_create_user(auth_user):
    """
    Get user from database or create if doesn't exist
    Returns: user record from 'users' table
    """
    try:
        # Check if user exists
        response = supabase.table('users').select('*').eq('id', auth_user.id).execute()
        
        if response.data and len(response.data) > 0:
            # Update last login
            supabase.table('users').update({
                'last_login': datetime.utcnow().isoformat(),
                'email': auth_user.email  # Update email in case it changed
            }).eq('id', auth_user.id).execute()
            
            logger.info(f"User logged in: {auth_user.email}")
            return response.data[0]
        else:
            # Create new user
            user_data = {
                'id': auth_user.id,
                'email': auth_user.email,
                'full_name': auth_user.user_metadata.get('full_name', ''),
                'avatar_url': auth_user.user_metadata.get('avatar_url', ''),
                'provider': auth_user.app_metadata.get('provider', 'unknown'),
                'created_at': datetime.utcnow().isoformat(),
                'last_login': datetime.utcnow().isoformat()
            }
            
            response = supabase.table('users').insert(user_data).execute()
            logger.info(f"New user created: {auth_user.email}")
            return response.data[0]
            
    except Exception as e:
        logger.error(f"Error in get_or_create_user: {str(e)}")
        raise

def update_user_profile(user_id, profile_data):
    """Update user profile information"""
    try:
        allowed_fields = ['full_name', 'avatar_url', 'bio', 'phone']
        update_data = {k: v for k, v in profile_data.items() if k in allowed_fields}
        update_data['updated_at'] = datetime.utcnow().isoformat()
        
        response = supabase.table('users').update(update_data).eq('id', user_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}")
        raise

# ==================== ROUTES ====================
@app.route('/')
def index():
    if 'access_token' in session:
        return redirect('/dashboard')
    return redirect('/login')

@app.route('/login')
def login():
    LOGIN_TEMPLATE = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .container {
                background: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                max-width: 400px;
                width: 90%;
            }
            h1 { margin-bottom: 30px; color: #333; text-align: center; }
            .google-btn {
                width: 100%;
                padding: 12px 20px;
                background: #4285f4;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 16px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 10px;
                transition: background 0.3s;
            }
            .google-btn:hover { background: #357ae8; }
            .google-btn:active { transform: scale(0.98); }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Welcome Back</h1>
            <button class="google-btn" onclick="loginWithGoogle()">
                <svg width="20" height="20" viewBox="0 0 20 20">
                    <path fill="white" d="M19.6 10.23c0-.82-.1-1.42-.25-2.05H10v3.72h5.5c-.15.96-.74 2.31-2.04 3.22v2.45h3.16c1.89-1.73 2.98-4.3 2.98-7.34z"/>
                    <path fill="white" d="M13.46 15.13c-.83.59-1.96 1-3.46 1-2.64 0-4.88-1.74-5.68-4.15H1.07v2.52C2.72 17.75 6.09 20 10 20c2.7 0 4.96-.89 6.62-2.42l-3.16-2.45z"/>
                    <path fill="white" d="M3.99 10c0-.69.12-1.35.32-1.97V5.51H1.07A9.973 9.973 0 000 10c0 1.61.39 3.14 1.07 4.49l3.24-2.52c-.2-.62-.32-1.28-.32-1.97z"/>
                    <path fill="white" d="M10 3.88c1.88 0 3.13.81 3.85 1.48l2.84-2.76C14.96.99 12.7 0 10 0 6.09 0 2.72 2.25 1.07 5.51l3.24 2.52C5.12 5.62 7.36 3.88 10 3.88z"/>
                </svg>
                Sign in with Google
            </button>
        </div>
        
        <script>
            function loginWithGoogle() {
                window.location.href = '/auth/google';
            }
        </script>
    </body>
    </html>
    '''
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/auth/google')
def auth_google():
    """Initiate Google OAuth flow"""
    try:
        redirect_url = request.host_url.rstrip('/') + '/auth/callback'
        
        response = supabase.auth.sign_in_with_oauth({
            'provider': 'google',
            'options': {
                'redirect_to': redirect_url,
                'scopes': 'email profile'
            }
        })
        
        return redirect(response.url)
    except Exception as e:
        logger.error(f"OAuth initiation error: {str(e)}")
        return f"Authentication error: {str(e)}", 500

@app.route('/auth/callback')
def auth_callback():
    """Handle OAuth callback"""
    code = request.args.get('code')
    
    if not code:
        return "No authorization code provided", 400
    
    try:
        # Exchange code for session
        response = supabase.auth.exchange_code_for_session({'auth_code': code})
        
        # Store session data
        session['access_token'] = response.session.access_token
        session['refresh_token'] = response.session.refresh_token
        session['user_id'] = response.user.id
        session.permanent = True
        
        # Get or create user in database
        get_or_create_user(response.user)
        
        return redirect('/dashboard')
        
    except Exception as e:
        logger.error(f"Authentication callback error: {str(e)}")
        return f"Authentication error: {str(e)}", 400

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    try:
        # Get auth user
        auth_response = supabase.auth.get_user(session['access_token'])
        
        # Get user from database
        db_user = supabase.table('users').select('*').eq('id', auth_response.user.id).execute()
        user_data = db_user.data[0] if db_user.data else {}
        
        DASHBOARD_TEMPLATE = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Dashboard</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: #f5f5f5;
                    padding: 20px;
                }
                .container { max-width: 800px; margin: 0 auto; }
                .header {
                    background: white;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    margin-bottom: 20px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                .user-card {
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                .avatar {
                    width: 80px;
                    height: 80px;
                    border-radius: 50%;
                    margin-bottom: 20px;
                }
                .info-row {
                    padding: 15px 0;
                    border-bottom: 1px solid #eee;
                    display: flex;
                    justify-content: space-between;
                }
                .info-row:last-child { border-bottom: none; }
                .label { font-weight: 600; color: #666; }
                .value { color: #333; }
                .btn {
                    padding: 10px 20px;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 14px;
                    transition: all 0.3s;
                }
                .btn-logout { background: #dc3545; color: white; }
                .btn-logout:hover { background: #c82333; }
                .btn-profile { background: #28a745; color: white; margin-right: 10px; }
                .btn-profile:hover { background: #218838; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Dashboard</h1>
                    <div>
                        <button class="btn btn-profile" onclick="location.href='/profile'">Edit Profile</button>
                        <button class="btn btn-logout" onclick="logout()">Logout</button>
                    </div>
                </div>
                
                <div class="user-card">
                    {% if user.avatar_url %}
                    <img src="{{ user.avatar_url }}" alt="Avatar" class="avatar">
                    {% endif %}
                    
                    <div class="info-row">
                        <span class="label">Full Name:</span>
                        <span class="value">{{ user.full_name or 'Not set' }}</span>
                    </div>
                    
                    <div class="info-row">
                        <span class="label">Email:</span>
                        <span class="value">{{ user.email }}</span>
                    </div>
                    
                    <div class="info-row">
                        <span class="label">User ID:</span>
                        <span class="value">{{ user.id }}</span>
                    </div>
                    
                    <div class="info-row">
                        <span class="label">Provider:</span>
                        <span class="value">{{ user.provider }}</span>
                    </div>
                    
                    <div class="info-row">
                        <span class="label">Member Since:</span>
                        <span class="value">{{ user.created_at[:10] }}</span>
                    </div>
                    
                    <div class="info-row">
                        <span class="label">Last Login:</span>
                        <span class="value">{{ user.last_login[:10] }}</span>
                    </div>
                </div>
            </div>
            
            <script>
                function logout() {
                    if (confirm('Are you sure you want to logout?')) {
                        window.location.href = '/logout';
                    }
                }
            </script>
        </body>
        </html>
        '''
        
        return render_template_string(DASHBOARD_TEMPLATE, user=user_data)
        
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        session.clear()
        return redirect('/login')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile page"""
    if request.method == 'POST':
        try:
            profile_data = {
                'full_name': request.form.get('full_name'),
                'bio': request.form.get('bio'),
                'phone': request.form.get('phone')
            }
            
            update_user_profile(session['user_id'], profile_data)
            return redirect('/dashboard')
            
        except Exception as e:
            return f"Error updating profile: {str(e)}", 400
    
    # GET request - show profile form
    try:
        user_data = supabase.table('users').select('*').eq('id', session['user_id']).execute()
        user = user_data.data[0] if user_data.data else {}
        
        PROFILE_TEMPLATE = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Edit Profile</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: #f5f5f5;
                    padding: 20px;
                }
                .container { max-width: 600px; margin: 0 auto; }
                .card {
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                h1 { margin-bottom: 30px; }
                .form-group {
                    margin-bottom: 20px;
                }
                label {
                    display: block;
                    margin-bottom: 5px;
                    font-weight: 600;
                    color: #333;
                }
                input, textarea {
                    width: 100%;
                    padding: 10px;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    font-size: 14px;
                }
                textarea { resize: vertical; min-height: 100px; }
                .btn {
                    padding: 12px 24px;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 16px;
                    margin-right: 10px;
                }
                .btn-primary { background: #007bff; color: white; }
                .btn-primary:hover { background: #0056b3; }
                .btn-secondary { background: #6c757d; color: white; }
                .btn-secondary:hover { background: #545b62; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="card">
                    <h1>Edit Profile</h1>
                    <form method="POST">
                        <div class="form-group">
                            <label>Full Name</label>
                            <input type="text" name="full_name" value="{{ user.full_name or '' }}">
                        </div>
                        
                        <div class="form-group">
                            <label>Bio</label>
                            <textarea name="bio">{{ user.bio or '' }}</textarea>
                        </div>
                        
                        <div class="form-group">
                            <label>Phone</label>
                            <input type="tel" name="phone" value="{{ user.phone or '' }}">
                        </div>
                        
                        <button type="submit" class="btn btn-primary">Save Changes</button>
                        <button type="button" class="btn btn-secondary" onclick="location.href='/dashboard'">Cancel</button>
                    </form>
                </div>
            </div>
        </body>
        </html>
        '''
        
        return render_template_string(PROFILE_TEMPLATE, user=user)
        
    except Exception as e:
        logger.error(f"Profile page error: {str(e)}")
        return f"Error loading profile: {str(e)}", 400

@app.route('/logout')
def logout():
    """Logout user"""
    try:
        if 'access_token' in session:
            supabase.auth.sign_out()
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
    
    session.clear()
    return redirect('/login')

# ==================== API ENDPOINTS ====================
@app.route('/api/user')
@login_required
def api_user():
    """Get current user data"""
    try:
        user_data = supabase.table('users').select('*').eq('id', session['user_id']).execute()
        
        if user_data.data:
            return jsonify(user_data.data[0])
        else:
            return jsonify({'error': 'User not found'}), 404
            
    except Exception as e:
        logger.error(f"API user error: {str(e)}")
        return jsonify({'error': str(e)}), 401

@app.route('/api/user/update', methods=['PUT'])
@login_required
def api_update_user():
    """Update user profile via API"""
    try:
        data = request.get_json()
        updated_user = update_user_profile(session['user_id'], data)
        
        return jsonify(updated_user)
        
    except Exception as e:
        logger.error(f"API update error: {str(e)}")
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    # NEVER use debug=True in production
    app.run(
        debug=os.getenv('FLASK_ENV') == 'development',
        host='0.0.0.0',
        port=int(os.getenv('PORT'))
    )

