from dotenv import load_dotenv
load_dotenv()

from database import (
    create_notification, init_db, get_user_by_username, get_user_by_id, create_user,
    create_submission, get_submissions, update_submission_status,
    create_announcement, get_announcements, create_rating, get_ratings,
    save_chat, get_chat_logs, get_dashboard_stats, update_user_credentials,
    get_submission_by_id,
    get_submission_by_nip,
    create_hr_chat, get_hr_chats, get_hr_chat_by_id, update_hr_chat_reply,
    get_hr_replies_by_nip, get_hr_replies_by_nama
)
from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash
import requests, os, sys, json
from datetime import datetime
from functools import wraps
from database import get_db_connection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

try:
    from knowledge import find_answer
except ImportError:
    def find_answer(msg):
        return None

# ==================== INIT ====================
app = Flask(__name__, template_folder=BASE_DIR)
app.secret_key = os.environ.get('SECRET_KEY', 'sara_secret_key_2026_change_in_production')
app.config['SESSION_PERMANENT'] = True
CORS(app)
init_db()

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max

# ==================== CONFIG ====================
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GROQ_ENABLED = os.environ.get('GROQ_ENABLED', 'true').lower() == 'true'
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'llama-3.1-8b-instant')

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434/api/generate')
OLLAMA_ENABLED = os.environ.get('OLLAMA_ENABLED', 'true').lower() == 'true'
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'llama3')

SYSTEM_PROMPT = """Kamu adalah SARA, Asisten Digital untuk PT Samaratu Daya Teknik. 
PRIORITAS: Berikan informasi akurat tentang perusahaan (onboarding, jam kerja, benefit, cuti, dll)
GAYA: Ramah, profesional, gunakan emoji yang sesuai."""

# ==================== MIDDLEWARE ====================
def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized - Please login first'}), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized - Please login first'}), 401
        user = get_user_by_id(session['user_id'])
        if not user or user['role'] != 'admin':
            return jsonify({'error': 'Forbidden - Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# ==================== AUTH ROUTES ====================
@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Admin login route
    GET: Show login form
    POST: Process login credentials
    """
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        # Validate input
        if not username or not password:
            return render_template("login.html", error="Username dan password wajib diisi")
        
        print(f"\n{'='*60}")
        print(f"🔐 Login attempt: {username}")
        
        # Get user from database
        user = get_user_by_username(username)
        
        if user:
            print(f"👤 User found: {user['nama']} (Role: {user['role']})")
            if user['password'] == password:
                if user['role'] == 'admin':
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['role'] = user['role']
                    session.permanent = True
                    
                    print(f"✅ Login successful: {username} (ID: {user['id']})")
                    print(f"{'='*60}\n")
                    return redirect("/admin")
                else:
                    print(f"❌ Non-admin user tried to login as admin: {username}")
                    print(f"{'='*60}\n")
                    return render_template("login.html", error="Hanya admin yang bisa login")
            else:
                print(f"❌ Wrong password for user: {username}")
                print(f"{'='*60}\n")
                return render_template("login.html", error="Username atau Password salah")
        else:
            print(f"❌ User not found: {username}")
            print(f"{'='*60}\n")
            return render_template("login.html", error="Username atau Password salah")
    
    return render_template("login.html")

@app.route('/api/register', methods=['POST'])
def register():
    """User registration endpoint"""
    data = request.json
    try:
        create_user(data['nama'], data['username'], data['password'], 
                   data.get('email', ''), data.get('jabatan', ''), data.get('nip', ''))
        return jsonify({'success': True, 'message': 'Registrasi berhasil'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/logout')
def logout():
    """Logout and clear session"""
    username = session.get('username', 'unknown')
    session.clear()
    print(f"🔓 User logged out: {username}")
    return jsonify({'success': True})

@app.route('/api/user')
@login_required
def get_user():
    """Get current user info"""
    user = get_user_by_id(session['user_id'])
    return jsonify(user)

# ==================== ADMIN SETTINGS ====================
@app.route('/api/admin/change-credentials', methods=['POST'])
@admin_required
def change_admin_credentials():
    """Change admin username and/or password"""
    try:
        data = request.json
        user_id = session['user_id']
        current_password = data.get('current_password', '').strip()
        new_username = data.get('new_username', '').strip()
        new_password = data.get('new_password', '').strip()
        confirm_password = data.get('confirm_password', '').strip()
        
        user = get_user_by_id(user_id)
        if not user:
            return jsonify({'error': 'User tidak ditemukan'}), 404
        
        if user['password'] != current_password:
            print(f"❌ Wrong current password for admin: {user['username']}")
            return jsonify({'error': 'Password saat ini salah'}), 401
        
        if new_password:
            if len(new_password) < 6:
                return jsonify({'error': 'Password baru minimal 6 karakter'}), 400
            
            if new_password != confirm_password:
                return jsonify({'error': 'Konfirmasi password tidak sesuai'}), 400
        
        if new_username and new_username != user['username']:
            if len(new_username) < 3:
                return jsonify({'error': 'Username minimal 3 karakter'}), 400
        
        if not new_username and not new_password:
            return jsonify({'error': 'Pilih username atau password untuk diubah'}), 400
        
        try:
            update_user_credentials(
                user_id,
                username=new_username if new_username and new_username != user['username'] else None,
                password=new_password if new_password else None
            )
        except Exception as e:
            return jsonify({'error': str(e)}), 400
        
        print(f"✅ Admin credentials updated")
        if new_username and new_username != user['username']:
            print(f"   New username: {new_username}")
            session['username'] = new_username
        if new_password:
            print(f"   Password changed")
        
        return jsonify({'success': True, 'message': 'Kredensial berhasil diubah'})
    except Exception as e:
        print(f"❌ Error changing credentials: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ==================== CHAT ENDPOINT ====================
@app.route('/api/chat', methods=['POST'])
def chat():
    """Main chat endpoint"""
    data = request.json
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({'error': 'Message cannot be empty'}), 400
    
    print(f"\n💬 User message: {user_message}")
    
    # 1️⃣ Try Knowledge Base first
    kb_answer = find_answer(user_message)
    if kb_answer:
        print(f"✅ Answer from Knowledge Base")
        save_chat(None, user_message, kb_answer['answer'], 'kb')
        
        # Check if location type
        if kb_answer.get('type') == 'location':
            return jsonify({
                'type': 'location',
                'reply': kb_answer['answer'],
                'address': kb_answer.get('address'),
                'details': kb_answer.get('details'),
                'maps_url': kb_answer.get('maps_url')
            })
        
        return jsonify({'reply': kb_answer['answer'], 'type': 'kb'})
    
    # 2️⃣ Try Groq if KB failed
    if GROQ_ENABLED and GROQ_API_KEY:
        print(f"🤖 Trying Groq...")
        groq_reply = call_groq(user_message)
        if groq_reply:
            print(f"✅ Answer from Groq")
            save_chat(None, user_message, groq_reply, 'groq')
            return jsonify({'reply': groq_reply, 'type': 'groq'})
    
    # 3️⃣ Try Ollama if Groq failed
    if OLLAMA_ENABLED:
        print(f"🤖 Trying Ollama...")
        ollama_reply = call_ollama(user_message)
        if ollama_reply:
            print(f"✅ Answer from Ollama")
            save_chat(None, user_message, ollama_reply, 'ollama')
            return jsonify({'reply': ollama_reply, 'type': 'ollama'})
    
    # 4️⃣ If all failed, suggest contacting HR
    print(f"❌ No answer found - suggesting HR contact")
    fallback_msg = "Maaf, saya tidak menemukan jawaban yang sesuai di database saya. Silakan hubungi HR atau klik tombol 'HR' untuk mendapatkan bantuan langsung dari tim Human Resources kami."
    save_chat(None, user_message, fallback_msg, 'fallback')
    return jsonify({'reply': fallback_msg, 'type': 'fallback', 'error': 'No answer found'})

# ==================== HR CHAT ENDPOINTS (NEW) ================
@app.route('/api/escalate-to-hr', methods=['POST'])
def escalate_to_hr():
    """Save user message to HR queue"""
    try:
        data = request.json
        nama = data.get('nama', '').strip()
        message = data.get('message', '').strip()
        
        if not nama or not message:
            return jsonify({'success': False, 'error': 'Nama dan pesan tidak boleh kosong'}), 400
        
        create_hr_chat(nama=nama, message=message, nip=None)
        print(f"✅ HR escalation saved from {nama}")
        return jsonify({'success': True, 'message': 'Pertanyaan Anda telah diteruskan ke HR'}), 201
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/hr-messages', methods=['GET'])
@admin_required
def get_hr_messages():
    """Get all HR messages for admin"""
    try:
        all_chats = get_hr_chats()
        pending = [chat for chat in all_chats if chat['status'] == 'pending']
        replied = [chat for chat in all_chats if chat['status'] == 'replied']
        
        print(f"📩 HR messages: {len(pending)} pending, {len(replied)} replied")
        return jsonify({'pending': pending, 'replied': replied, 'total': len(all_chats)}), 200
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/hr-messages/<int:msg_id>/reply', methods=['POST'])
@admin_required
def reply_hr_message(msg_id):
    """Admin reply to HR message"""
    try:
        data = request.json
        reply = data.get('reply', '').strip()
        
        if not reply:
            return jsonify({'error': 'Balasan tidak boleh kosong'}), 400
        
        update_hr_chat_reply(msg_id, reply)
        print(f"✅ HR message {msg_id} replied")
        return jsonify({'success': True, 'message': 'Balasan berhasil dikirim'}), 200
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'error': str(e)}), 500    

@app.route('/api/hr-reply/<nama>', methods=['GET'])
def get_hr_reply_by_name(nama):
    """
    Get HR replies for specific person (for user to check)
    Used by cekBalasanHR() function in frontend
    """
    try:
        replies = get_hr_replies_by_nama(nama)
        return jsonify(replies), 200
    except Exception as e:
        print(f"❌ Error getting HR replies: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ==================== SUBMISSIONS ====================
@app.route('/api/submissions', methods=['POST'])
def submit_cuti():
    """Submit leave request"""
    try:
        nama = request.form.get('nama', '').strip()
        nip = request.form.get('nip', '').strip()
        jenis = request.form.get('jenis', '').strip()
        tanggal_mulai = request.form.get('tanggal_mulai', '').strip()
        tanggal_selesai = request.form.get('tanggal_selesai', '').strip()
        alasan = request.form.get('alasan', '').strip()
        
        # Validate required fields
        if not all([nama, nip, jenis, tanggal_mulai, tanggal_selesai]):
            return jsonify({'success': False, 'error': 'Semua field wajib diisi'}), 400
        
        # Validate dates
        from datetime import datetime as dt
        try:
            mulai = dt.strptime(tanggal_mulai, '%Y-%m-%d')
            selesai = dt.strptime(tanggal_selesai, '%Y-%m-%d')
            if mulai > selesai:
                return jsonify({'success': False, 'error': 'Tanggal mulai harus sebelum selesai'}), 400
        except ValueError:
            return jsonify({'success': False, 'error': 'Format tanggal tidak valid'}), 400
        
        # Handle file upload
        lampiran = None
        if 'lampiran' in request.files:
            file = request.files['lampiran']
            if file and file.filename:
                # Check file extension
                ext = file.filename.rsplit('.', 1)[1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    return jsonify({'success': False, 'error': 'Tipe file tidak diizinkan'}), 400
                
                # Save file
                filename = f"{nip}_{datetime.now().timestamp()}.{ext}"
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                lampiran = filename
        
        # Save to database
        create_submission(None, nama, nip, jenis, tanggal_mulai, tanggal_selesai, alasan, lampiran)
        
        print(f"✅ Cuti submitted: {nama} ({nip}) - {jenis}")
        return jsonify({'success': True, 'message': 'Pengajuan cuti berhasil dikirim'}), 201
    
    except Exception as e:
        print(f"❌ Error submitting cuti: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/check-status/<nip>', methods=['GET'])
def check_status(nip):
    """Check cuti status by NIP"""
    try:
        submissions = get_submission_by_nip(nip)
        if not submissions:
            return jsonify({'success': False, 'message': 'Data tidak ditemukan'}), 404
        
        return jsonify({'success': True, 'data': submissions}), 200
    except Exception as e:
        print(f"❌ Error checking status: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/submissions/<int:submission_id>', methods=['GET'])
@admin_required
def get_submission(submission_id):
    """Get specific submission"""
    try:
        sub = get_submission_by_id(submission_id)
        if not sub:
            return jsonify({'error': 'Submission not found'}), 404
        return jsonify(sub), 200
    except Exception as e:
        print(f"❌ Error getting submission: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/submissions/<int:submission_id>/approve', methods=['POST'])
@admin_required
def approve_cuti(submission_id):
    """Approve leave request"""
    try:
        update_submission_status(submission_id, 'approved')
        print(f"✅ Cuti approved: ID {submission_id}")
        return jsonify({'success': True, 'message': 'Cuti telah disetujui'}), 200
    except Exception as e:
        print(f"❌ Error approving cuti: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/submissions/<int:submission_id>/reject', methods=['POST'])
@admin_required
def reject_cuti(submission_id):
    """Reject leave request"""
    try:
        update_submission_status(submission_id, 'rejected')
        print(f"✅ Cuti rejected: ID {submission_id}")
        return jsonify({'success': True, 'message': 'Cuti telah ditolak'}), 200
    except Exception as e:
        print(f"❌ Error rejecting cuti: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ==================== ADMIN DASHBOARD ====================
@app.route('/admin', methods=['GET'])
def admin_dashboard():
    """Admin dashboard page"""
    if 'user_id' not in session:
        return redirect("/login")
    
    return send_from_directory(BASE_DIR, 'admin.html')

@app.route('/api/stats')
@admin_required
def stats():
    """Get dashboard statistics (admin only)"""
    try:
        data = get_dashboard_stats()
        print(f"📊 Stats retrieved for admin: {session.get('username')}")
        return jsonify(data)
    except Exception as e:
        print(f"❌ Error getting stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cuti')
@admin_required
def all_cuti():
    """Get all leave requests (admin only)"""
    try:
        subs = get_submissions()
        print(f"📋 Cuti list retrieved: {len(subs)} items")
        return jsonify(subs)
    except Exception as e:
        print(f"❌ Error getting cuti: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/pengumuman', methods=['POST'])
@admin_required
def buat_pengumuman():
    """Create announcement (admin only)"""
    data = request.json
    try:
        judul = data.get('judul', '').strip()
        isi = data.get('isi', '').strip()
        tipe = data.get('tipe', 'info')
        
        if not judul or not isi:
            return jsonify({'error': 'Judul dan isi wajib diisi'}), 400
        
        create_announcement(judul, isi, tipe, session['user_id'])
        print(f"✅ Announcement created: '{judul}' by {session.get('username')}")
        return jsonify({'success': True, 'message': 'Pengumuman berhasil dibuat'})
    except Exception as e:
        print(f"❌ Error creating announcement: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/pengumuman', methods=['GET'])
def list_pengumuman():
    """Get all announcements (public - no auth needed)"""
    try:
        announcements = get_announcements()
        return jsonify(announcements)
    except Exception as e:
        print(f"❌ Error getting announcements: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route("/notifications")
def notifications():
    """View notifications (requires login)"""
    if "user_id" not in session:
        return redirect("/login")
    
    from database import get_notifications
    data = get_notifications(session["user_id"])
    return render_template("notification.html", notifications=data)

@app.route('/api/survey', methods=['POST'])
def submit_survey():
    """Submit survey response - NO AUTH NEEDED"""
    data = request.json
    try:
        rating = data.get('rating')
        if not rating or rating < 1 or rating > 5:
            return jsonify({'error': 'Rating harus antara 1-5'}), 400
        
        nama = data.get('nama', 'Anonim')
        saran = data.get('saran', '')
        
        user_id = session.get('user_id') if 'user_id' in session else None
        create_rating(user_id, nama, rating, saran)
        print(f"⭐ Survey submitted: {rating} stars by {nama}")
        return jsonify({'message': 'Terima kasih atas feedback Anda!'})
    except Exception as e:
        print(f"❌ Error submitting survey: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/survey', methods=['GET'])
@admin_required
def list_survey():
    """Get all survey responses (admin only)"""
    try:
        ratings = get_ratings()
        print(f"⭐ Survey list retrieved: {len(ratings)} responses")
        return jsonify(ratings)
    except Exception as e:
        print(f"❌ Error getting survey: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat-logs', methods=['GET'])
@admin_required
def get_logs():
    """Get chat logs (admin only)"""
    try:
        logs = get_chat_logs()
        print(f"💬 Chat logs retrieved: {len(logs)} logs")
        return jsonify(logs)
    except Exception as e:
        print(f"❌ Error getting chat logs: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ==================== STATIC ====================
@app.route('/')
def index():
    """Home page"""
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    try:
        return send_from_directory(BASE_DIR, filename)
    except:
        return jsonify({'error': 'File not found'}), 404

@app.route('/api/test', methods=['GET'])
def test():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'SARA Server Running',
        'timestamp': datetime.now().isoformat(),
        'ollama_enabled': OLLAMA_ENABLED,
        'groq_enabled': GROQ_ENABLED and bool(GROQ_API_KEY)
    })

# ==================== ERROR HANDLERS ====================
@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    print(f"❌ Server error: {str(e)}")
    return jsonify({'error': 'Server error'}), 500

# ==================== LLM FUNCTIONS ====================
def call_groq(message):
    """Call Groq API for response"""
    try:
        headers = {
            'Authorization': f'Bearer {GROQ_API_KEY}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': GROQ_MODEL,
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': message}
            ],
            'temperature': 0.7,
            'max_tokens': 1024
        }
        response = requests.post('https://api.groq.com/openai/v1/chat/completions',
                                headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            print(f"❌ Groq error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Groq error: {str(e)}")
    return None

def call_ollama(message):
    """Call Ollama local LLM for response"""
    try:
        response = requests.post(OLLAMA_URL,
            json={
                'model': OLLAMA_MODEL,
                'prompt': f"{SYSTEM_PROMPT}\n\nUser: {message}\nAssistant:",
                'stream': False,
                'temperature': 0.7
            }, timeout=60)
        if response.status_code == 200:
            return response.json().get('response')
        else:
            print(f"❌ Ollama error {response.status_code}")
    except Exception as e:
        print(f"❌ Ollama error: {str(e)}")
    return None

# ==================== MAIN ====================
if __name__ == '__main__':
    print('\n' + '='*60)
    print('🚀 SARA BOT - PT SAMARATU DAYA TEKNIK')
    print('='*60)
    print(f'✅ Mode:     {"Groq + KB" if GROQ_ENABLED and GROQ_API_KEY else "Ollama + KB"}')
    print(f'📡 Ollama:   {"ENABLED" if OLLAMA_ENABLED else "DISABLED"}')
    print(f'🤖 Groq:     {"ENABLED" if GROQ_ENABLED and GROQ_API_KEY else "DISABLED"}')
    print(f'📁 KB:       Loaded')
    print(f'⏰ Started:  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('='*60)
    print('🌐 Server running at http://localhost:5000')
    print('⚙️  Admin at http://localhost:5000/admin')
    print('📝 Default admin - username: admin | password: admin123')
    print('='*60 + '\n')

    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug_mode, port=port, host='0.0.0.0')