import sqlite3
from datetime import datetime

DATABASE = "sara.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # USERS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama TEXT,
        username TEXT UNIQUE,
        password TEXT,
        email TEXT,
        nip TEXT UNIQUE,
        role TEXT
    )
    """)

    # ANNOUNCEMENTS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS announcements(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        judul TEXT NOT NULL,
        isi TEXT NOT NULL,
        tipe TEXT DEFAULT 'info',
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # SUBMISSIONS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS submissions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        nama TEXT,
        nip TEXT,
        jenis TEXT,
        tanggal_mulai DATE,
        tanggal_selesai DATE,
        alasan TEXT,
        lampiran TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            message TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

    # RATINGS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ratings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        nama TEXT,
        rating INTEGER,
        saran TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # CHAT LOGS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        user_message TEXT,
        bot_response TEXT,
        source TEXT DEFAULT 'kb',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # HR CHATS - IMPROVED VERSION
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hr_chats(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama TEXT NOT NULL,
        nip TEXT,
        message TEXT NOT NULL,
        reply TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        replied_at TIMESTAMP
    )
    """)

    # CEK ADMIN
    cursor.execute(
        "SELECT * FROM users WHERE username=?",
        ("admin",)
    )

    admin = cursor.fetchone()

    if not admin:
        cursor.execute("""
    INSERT INTO users
    (nama, username, password, email, nip, role)
    VALUES (?, ?, ?, ?, ?, ?)
    """,
    (
        "Administrator HRD",
        "admin",
        "admin123",
        "hr@samaratu.com",
        "HR001",
        "admin"
    ))

    conn.commit()
    conn.close()
    

def create_user(nama, username, password, email="", nip="", role="user"):
    conn = get_db_connection()
    try:
        conn.execute("""
        INSERT INTO users (nama, username, password, email, nip, role)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (nama, username, password, email, nip, role))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        raise Exception("Username atau NIP sudah terdaftar!")

def create_notification(user_id, title, message):
    conn = get_db_connection()

    conn.execute("""
    INSERT INTO notifications
    (user_id, title, message)
    VALUES (?, ?, ?)
    """, (user_id, title, message))

    conn.commit()
    conn.close()

def get_notifications(user_id):
    conn = get_db_connection()

    data = conn.execute("""
    SELECT *
    FROM notifications
    WHERE user_id=?
    ORDER BY created_at DESC
    """, (user_id,)).fetchall()

    conn.close()

    return [dict(row) for row in data]

def get_user_by_username(username):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None

def get_submission_by_id(submission_id):
    conn = get_db_connection()

    data = conn.execute(
        "SELECT * FROM submissions WHERE id = ?",
        (submission_id,)
    ).fetchone()

    conn.close()

    return dict(data) if data else None

def update_user_password(user_id, new_password):
    """Update user password"""
    conn = get_db_connection()
    try:
        conn.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, user_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        raise Exception(f"Gagal mengubah password: {str(e)}")

def update_user_username(user_id, new_username):
    """Update user username"""
    conn = get_db_connection()
    try:
        # Check if username already exists
        existing = conn.execute("SELECT id FROM users WHERE username = ? AND id != ?", (new_username, user_id)).fetchone()
        if existing:
            raise Exception("Username sudah digunakan!")
        
        conn.execute("UPDATE users SET username = ? WHERE id = ?", (new_username, user_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        raise Exception(str(e))

def update_user_credentials(user_id, username=None, password=None):
    """Update both username and password"""
    conn = get_db_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise Exception("User tidak ditemukan!")
        
        # Update username if provided
        if username and username != user['username']:
            existing = conn.execute("SELECT id FROM users WHERE username = ? AND id != ?", (username, user_id)).fetchone()
            if existing:
                raise Exception("Username sudah digunakan!")
            conn.execute("UPDATE users SET username = ? WHERE id = ?", (username, user_id))
        
        # Update password if provided
        if password:
            conn.execute("UPDATE users SET password = ? WHERE id = ?", (password, user_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        raise Exception(str(e))

def create_announcement(judul, isi, tipe, admin_id):
    conn = get_db_connection()
    conn.execute("""
    INSERT INTO announcements (judul, isi, tipe, created_by)
    VALUES (?, ?, ?, ?)
    """, (judul, isi, tipe, admin_id))
    conn.commit()
    conn.close()

def get_announcements():
    conn = get_db_connection()
    data = conn.execute("SELECT * FROM announcements ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in data]

def create_submission(user_id, nama, nip, jenis, tanggal_mulai, tanggal_selesai, alasan, lampiran=None):
    conn = get_db_connection()
    conn.execute("""
    INSERT INTO submissions (user_id, nama, nip, jenis, tanggal_mulai, tanggal_selesai, alasan, lampiran)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, nama, nip, jenis, tanggal_mulai, tanggal_selesai, alasan, lampiran))
    conn.commit()
    conn.close()

def get_submissions(user_id=None):
    conn = get_db_connection()
    if user_id:
        data = conn.execute("SELECT * FROM submissions WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    else:
        data = conn.execute("SELECT * FROM submissions ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in data]

def get_submission_by_nip(nip):
    conn = get_db_connection()

    data = conn.execute("""
    SELECT *
    FROM submissions
    WHERE nip = ?
    ORDER BY created_at DESC
    """, (nip,)).fetchall()

    conn.close()

    return [dict(row) for row in data]

def update_submission_status(submission_id, status):
    conn = get_db_connection()

    conn.execute(
        "UPDATE submissions SET status = ? WHERE id = ?",
        (status, submission_id)
    )

    conn.commit()
    conn.close()

def create_rating(user_id, nama, rating, saran):
    conn = get_db_connection()
    conn.execute("INSERT INTO ratings (user_id, nama, rating, saran) VALUES (?, ?, ?, ?)", (user_id, nama, rating, saran))
    conn.commit()
    conn.close()

def get_ratings():
    conn = get_db_connection()
    data = conn.execute("SELECT * FROM ratings ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in data]

def save_chat(user_id, user_message, bot_response, source='kb'):
    conn = get_db_connection()
    conn.execute("INSERT INTO chat_logs (user_id, user_message, bot_response, source) VALUES (?, ?, ?, ?)", 
                 (user_id, user_message, bot_response, source))
    conn.commit()
    conn.close()

def get_chat_logs(limit=100):
    conn = get_db_connection()
    data = conn.execute("SELECT * FROM chat_logs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in data]

# ============ HR CHAT FUNCTIONS ============
def create_hr_chat(nama, message, nip=None):
    """Simpan pesan dari user ke HR"""
    conn = get_db_connection()
    try:
        conn.execute("""
        INSERT INTO hr_chats (nama, nip, message, status)
        VALUES (?, ?, ?, 'pending')
        """, (nama, nip, message))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        raise Exception(f"Gagal menyimpan pesan HR: {str(e)}")

def get_hr_chats(status=None):
    """Get all HR chat messages"""
    conn = get_db_connection()
    if status:
        data = conn.execute("""
        SELECT * FROM hr_chats
        WHERE status = ?
        ORDER BY created_at DESC
        """, (status,)).fetchall()
    else:
        data = conn.execute("""
        SELECT * FROM hr_chats
        ORDER BY created_at DESC
        """).fetchall()
    conn.close()
    return [dict(row) for row in data]

def get_hr_chat_by_id(chat_id):
    """Get specific HR chat by ID"""
    conn = get_db_connection()
    data = conn.execute("""
    SELECT * FROM hr_chats WHERE id = ?
    """, (chat_id,)).fetchone()
    conn.close()
    return dict(data) if data else None

def update_hr_chat_reply(chat_id, reply):
    """Update HR chat with reply"""
    conn = get_db_connection()
    try:
        conn.execute("""
        UPDATE hr_chats
        SET reply = ?, status = 'replied', replied_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (reply, chat_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        raise Exception(f"Gagal menyimpan balasan: {str(e)}")

def get_hr_replies_by_nip(nip):
    """Get HR replies for a specific NIP"""
    conn = get_db_connection()
    data = conn.execute("""
    SELECT * FROM hr_chats
    WHERE nip = ? AND reply IS NOT NULL
    ORDER BY replied_at DESC
    """, (nip,)).fetchall()
    conn.close()
    return [dict(row) for row in data]

def get_hr_replies_by_nama(nama):
    """Get HR replies for a specific nama"""
    conn = get_db_connection()
    data = conn.execute("""
    SELECT * FROM hr_chats
    WHERE nama = ? AND reply IS NOT NULL
    ORDER BY replied_at DESC
    """, (nama,)).fetchall()
    conn.close()
    return [dict(row) for row in data]

def get_dashboard_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM chat_logs WHERE date(created_at) = date('now')")
    chat_today = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM chat_logs")
    chat_total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM submissions")
    total_cuti = cursor.fetchone()[0]
    cursor.execute("SELECT AVG(rating) FROM ratings")
    avg_rating = cursor.fetchone()[0] or 0
    pengumuman = get_announcements()[:5]
    conn.close()
    return {
        "chat_today": chat_today,
        "chat_total": chat_total,
        "total_cuti": total_cuti,
        "avg_rating": round(avg_rating, 1),
        "pengumuman": pengumuman
    }
