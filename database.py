#!/usr/bin/env python3
"""
UPSSA Attendance & Event Management System
Module de gestion de la base de données SQLite.
"""

import sqlite3
import os
import json
import re
from datetime import datetime

DB_PATH = os.environ.get('DB_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'upssa.db'))

def get_connection():
    """Crée et retourne une connexion SQLite avec row_factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def format_whatsapp_phone(raw):
    """
    Normalise un numéro de téléphone pour WhatsApp (format international E.164 sans +).
    Exemple:
      '0645737215' -> '212645737215'
      '0724836763' -> '212724836763'
      '+212 6 45 73 72 15' -> '212645737215'
      '33766050529' -> '33766050529'
    """
    if not raw:
        return ''
    s = re.sub(r'[^\d+]', '', str(raw).strip())
    if s.startswith('+'):
        s = s[1:]
    if s.startswith('00'):
        s = s[2:]
    # Numéros marocains commençant par 0 (06... ou 07... ou 05...)
    if s.startswith('0') and len(s) == 10:
        return '212' + s[1:]
    if len(s) == 9 and (s.startswith('6') or s.startswith('7') or s.startswith('5')):
        return '212' + s
    return s

def init_db():
    """Initialise le schéma de la base de données SQL."""
    conn = get_connection()
    cursor = conn.cursor()

    # Table des étudiants
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id TEXT PRIMARY KEY,
        old_id TEXT,
        name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        phone_wa TEXT,
        pole TEXT,
        year TEXT,
        file_status TEXT,
        gala INTEGER DEFAULT 0,
        teambuilding INTEGER DEFAULT 0,
        confirmed INTEGER DEFAULT 0,
        transport INTEGER DEFAULT 0,
        qr_data TEXT,
        qr_file TEXT,
        pass_file TEXT,
        whatsapp_status TEXT DEFAULT 'pending',
        whatsapp_sent_at TEXT,
        attended INTEGER DEFAULT 0,
        scanned_at TEXT,
        scanned_time TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Table d'historique de scan (anti-doublon et traçabilité)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        student_name TEXT,
        timestamp TEXT NOT NULL,
        status TEXT NOT NULL,
        device TEXT,
        notes TEXT,
        FOREIGN KEY (student_id) REFERENCES students(id)
    )
    """)

    # Table des journaux d'envoi WhatsApp
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS whatsapp_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        phone TEXT NOT NULL,
        status TEXT NOT NULL,
        message TEXT,
        timestamp TEXT NOT NULL,
        notes TEXT,
        FOREIGN KEY (student_id) REFERENCES students(id)
    )
    """)

    # Index pour des recherches instantanées
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_phone_wa ON students(phone_wa)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_attended ON students(attended)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_whatsapp ON students(whatsapp_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scans_student ON scans(student_id)")

    conn.commit()
    conn.close()
    print("✅ Base de données SQLite initialisée avec succès.")

def seed_students_if_empty(json_path=None):
    """Importe les étudiants depuis students.json si la table est vide ou complète les informations."""
    if json_path is None:
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'students.json')
    
    if not os.path.exists(json_path):
        print(f"⚠️ Fichier source {json_path} non trouvé.")
        return 0

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    conn = get_connection()
    cursor = conn.cursor()

    count = 0
    now = datetime.now().isoformat()

    for item in data:
        st_id = item.get('id', '').strip()
        old_id = item.get('old_id', '').strip()
        if not st_id:
            continue

        name = item.get('name', '').strip()
        email = item.get('email', '').strip()
        phone = item.get('phone', '').strip()
        phone_wa = format_whatsapp_phone(phone)
        pole = item.get('pole', '').strip()
        year = item.get('year', '').strip()
        file_status = item.get('file_status', '').strip()
        gala = 1 if item.get('gala') else 0
        teambuilding = 1 if item.get('teambuilding') else 0
        confirmed = 1 if item.get('confirmed') else 0
        transport = 1 if item.get('transport') else 0
        qr_data = f"UPSSA:{st_id}"
        qr_file = f"qrcodes/{st_id}.png"
        pass_file = f"passes/{st_id}.png"

        cursor.execute("""
        INSERT INTO students (
            id, old_id, name, email, phone, phone_wa, pole, year, file_status,
            gala, teambuilding, confirmed, transport, qr_data, qr_file, pass_file
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            old_id = excluded.old_id,
            name = excluded.name,
            email = excluded.email,
            phone = excluded.phone,
            phone_wa = excluded.phone_wa,
            pole = excluded.pole,
            year = excluded.year,
            file_status = excluded.file_status,
            gala = excluded.gala,
            teambuilding = excluded.teambuilding,
            confirmed = excluded.confirmed,
            transport = excluded.transport,
            qr_data = excluded.qr_data,
            qr_file = excluded.qr_file,
            pass_file = excluded.pass_file
        """, (
            st_id, old_id, name, email, phone, phone_wa, pole, year, file_status,
            gala, teambuilding, confirmed, transport, qr_data, qr_file, pass_file
        ))
        count += 1

    conn.commit()
    conn.close()
    print(f"✅ {count} étudiants synchronisés dans la base SQLite.")
    return count

def get_all_students(filter_attended=None, filter_wa=None, pole=None, search=None):
    """Récupère tous les étudiants avec filtres optionnels."""
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM students WHERE 1=1"
    params = []

    if filter_attended is not None:
        query += " AND attended = ?"
        params.append(1 if filter_attended else 0)

    if filter_wa is not None:
        query += " AND whatsapp_status = ?"
        params.append(filter_wa)

    if pole:
        query += " AND pole = ?"
        params.append(pole)

    if search:
        search_pattern = f"%{search.strip()}%"
        query += " AND (name LIKE ? OR email LIKE ? OR phone LIKE ? OR id LIKE ?)"
        params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

    query += " ORDER BY name ASC"
    cursor.execute(query, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_student_by_id(st_id):
    """Recherche un étudiant par son ID à 4 chiffres, ancien ID, code QR, email ou téléphone."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM students 
        WHERE id = ? OR old_id = ? OR qr_data = ? OR phone_wa = ? OR email = ?
    """, (st_id, st_id, st_id, st_id, st_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def record_scan(st_id, device='web'):
    """
    Enregistre un pointage de scan ou saisie manuelle dans la base SQL.
    Gère la détection de doublons (déjà présent) et l'historique complet.
    Accepte : ID à 4 chiffres, QR data (UPSSA:1001), ancien ID, téléphone ou nom.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Nettoyage de l'identifiant (ex: UPSSA:1001 -> 1001)
    clean_id = str(st_id).strip()
    if clean_id.upper().startswith('UPSSA:'):
        clean_id = clean_id[6:].strip()

    # Extraction automatique si URL complète de billet ou QR scanné
    if '?' in clean_id and ('id=' in clean_id or 'code=' in clean_id or 'http' in clean_id):
        try:
            import urllib.parse
            parsed_u = urllib.parse.urlparse(clean_id)
            qs = urllib.parse.parse_qs(parsed_u.query)
            extracted = qs.get('id', qs.get('code', qs.get('student', [clean_id])))[0].strip()
            if extracted:
                clean_id = extracted
                if clean_id.upper().startswith('UPSSA:'):
                    clean_id = clean_id[6:].strip()
        except Exception:
            pass

    # Recherche multi-critères : ID 4 chiffres, ancien ID, email, téléphone, ou nom exact
    cursor.execute("""
        SELECT * FROM students 
        WHERE id = ? OR old_id = ? OR qr_data = ? OR email = ? OR phone_wa = ? OR phone = ? OR LOWER(name) = LOWER(?)
    """, (clean_id, clean_id, f"UPSSA:{clean_id}", clean_id, clean_id, clean_id, clean_id))
    student = cursor.fetchone()

    if not student:
        # Enregistre la tentative inconnue
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO scans (student_id, student_name, timestamp, status, device, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (clean_id, 'Inconnu', now, 'error', device, 'Identifiant non répertorié')
        )
        conn.commit()
        conn.close()
        return {'success': False, 'status': 'not_found', 'message': f"Code {clean_id} non trouvé dans la liste des inscrits."}

    student_data = dict(student)
    now_dt = datetime.now()
    now_iso = now_dt.isoformat()
    now_time = now_dt.strftime('%H:%M:%S')

    if student_data['attended']:
        # Doublon !
        cursor.execute(
            "INSERT INTO scans (student_id, student_name, timestamp, status, device, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (student_data['id'], student_data['name'], now_iso, 'duplicate', device, f"Déjà pointé à {student_data['scanned_time']}")
        )
        conn.commit()
        conn.close()
        return {
            'success': False,
            'status': 'duplicate',
            'message': f"Attention : {student_data['name']} a déjà été scanné à {student_data['scanned_time']}.",
            'student': student_data
        }

    # Premier scan validé !
    cursor.execute("""
    UPDATE students
    SET attended = 1, scanned_at = ?, scanned_time = ?, updated_at = ?
    WHERE id = ?
    """, (now_iso, now_time, now_iso, student_data['id']))

    cursor.execute(
        "INSERT INTO scans (student_id, student_name, timestamp, status, device, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (student_data['id'], student_data['name'], now_iso, 'success', device, 'Entrée validée')
    )

    conn.commit()
    conn.close()

    student_data['attended'] = 1
    student_data['scanned_at'] = now_iso
    student_data['scanned_time'] = now_time

    return {
        'success': True,
        'status': 'success',
        'message': f"Pointage validé avec succès pour {student_data['name']} !",
        'student': student_data
    }

def toggle_student_attendance(st_id, status=None):
    """Bascule ou force le statut de présence d'un étudiant manuellement."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT attended, name FROM students WHERE id = ?", (st_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    current_status = row['attended']
    new_status = 1 if (not current_status if status is None else status) else 0

    now_iso = datetime.now().isoformat()
    now_time = datetime.now().strftime('%H:%M:%S') if new_status else None

    cursor.execute("""
    UPDATE students
    SET attended = ?, scanned_at = ?, scanned_time = ?, updated_at = ?
    WHERE id = ?
    """, (new_status, now_iso if new_status else None, now_time, now_iso, st_id))

    cursor.execute(
        "INSERT INTO scans (student_id, student_name, timestamp, status, device, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (st_id, row['name'], now_iso, 'manual_checkin' if new_status else 'manual_checkout', 'manual', 'Modification manuelle')
    )

    conn.commit()
    conn.close()
    return {'id': st_id, 'attended': new_status, 'scanned_time': now_time}

def mark_whatsapp_sent(st_id, status='sent', message_preview=None):
    """Marque le message WhatsApp comme envoyé pour un étudiant."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, phone_wa FROM students WHERE id = ?", (st_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    now_iso = datetime.now().isoformat()

    cursor.execute("""
    UPDATE students
    SET whatsapp_status = ?, whatsapp_sent_at = ?, updated_at = ?
    WHERE id = ?
    """, (status, now_iso if status == 'sent' else None, now_iso, st_id))

    cursor.execute("""
    INSERT INTO whatsapp_logs (student_id, phone, status, message, timestamp)
    VALUES (?, ?, ?, ?, ?)
    """, (st_id, row['phone_wa'], status, message_preview or 'WhatsApp confirmation message', now_iso))

    conn.commit()
    conn.close()
    return True

def get_stats():
    """Calcule toutes les métriques en temps réel directement via des requêtes SQL."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN attended = 1 THEN 1 ELSE 0 END) as attended_count,
        SUM(CASE WHEN gala = 1 THEN 1 ELSE 0 END) as gala_total,
        SUM(CASE WHEN gala = 1 AND attended = 1 THEN 1 ELSE 0 END) as gala_attended,
        SUM(CASE WHEN teambuilding = 1 THEN 1 ELSE 0 END) as tb_total,
        SUM(CASE WHEN teambuilding = 1 AND attended = 1 THEN 1 ELSE 0 END) as tb_attended,
        SUM(CASE WHEN transport = 1 THEN 1 ELSE 0 END) as transport_total,
        SUM(CASE WHEN transport = 1 AND attended = 1 THEN 1 ELSE 0 END) as transport_attended,
        SUM(CASE WHEN whatsapp_status = 'sent' THEN 1 ELSE 0 END) as wa_sent_count,
        SUM(CASE WHEN whatsapp_status != 'sent' OR whatsapp_status IS NULL THEN 1 ELSE 0 END) as wa_pending_count
    FROM students
    """)
    overview = dict(cursor.fetchone())

    # Stats par pôle
    cursor.execute("""
    SELECT
        pole,
        COUNT(*) as total,
        SUM(CASE WHEN attended = 1 THEN 1 ELSE 0 END) as attended
    FROM students
    GROUP BY pole
    """)
    by_pole = [dict(r) for r in cursor.fetchall()]

    # Derniers scans
    cursor.execute("""
    SELECT * FROM scans
    ORDER BY id DESC
    LIMIT 50
    """)
    recent_scans = [dict(r) for r in cursor.fetchall()]

    conn.close()

    total = overview['total'] or 1
    attended = overview['attended_count'] or 0
    overview['percentage'] = round((attended / total) * 100, 1)

    return {
        'overview': overview,
        'by_pole': by_pole,
        'recent_scans': recent_scans
    }

if __name__ == '__main__':
    print("Initialisation de la base SQLite...")
    init_db()
    seed_students_if_empty()
    stats = get_stats()
    print("Statistiques actuelles :", json.dumps(stats['overview'], indent=2))

