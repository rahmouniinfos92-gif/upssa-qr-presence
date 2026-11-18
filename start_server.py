#!/usr/bin/env python3
"""
UPSSA QR Code Attendance & WhatsApp Dispatch Server
Serveur web local HTTP avec API REST connectée à la base de données SQLite.
Permet le scan temps réel multi-appareils (PC, tablette, smartphones Wi-Fi)
et la gestion des envois WhatsApp avec QR codes.
"""

import http.server
import socket
import socketserver
import os
import sys
import json
import urllib.parse
import csv
from datetime import datetime

import database
import qr_generator
import whatsapp_manager

PORT = int(os.environ.get('PORT', 8080))
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

def get_local_ip():
    """Détecte l'adresse IP locale sur le réseau Wi-Fi."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

class UPSSAHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        # En-têtes pour désactiver le cache et autoriser CORS
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def send_json(self, data, status_code=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Route d'accès au billet étudiant : /ticket ou /ticket?id=...
        if path == '/ticket' or path == '/ticket/':
            self.path = '/ticket.html'
            return super().do_GET()

        # --- API REST ROUTES ---

        # 1. Liste des étudiants depuis SQLite
        if path == '/api/students':
            search = query.get('search', [None])[0]
            pole = query.get('pole', [None])[0]
            filter_wa = query.get('whatsapp_status', [None])[0]
            att_param = query.get('attended', [None])[0]
            filter_att = None
            if att_param == '1' or att_param == 'true':
                filter_att = True
            elif att_param == '0' or att_param == 'false':
                filter_att = False

            students = database.get_all_students(
                filter_attended=filter_att,
                filter_wa=filter_wa,
                pole=pole,
                search=search
            )
            # Ajout des URLs dynamiques
            local_ip = get_local_ip()
            base_url = f"http://{local_ip}:{PORT}"
            for s in students:
                links = whatsapp_manager.get_whatsapp_links(s, base_url=base_url)
                s['phone_wa'] = links['phone_wa']
                s['wa_url'] = links['web_wa']
                s['wa_me_url'] = links['wa_me']
                s['ticket_url'] = f"{base_url}/ticket?id={s['id']}"

            return self.send_json(students)

        # 2. Détail d'un étudiant par son ID
        if path == '/api/student':
            st_id = query.get('id', [None])[0]
            if not st_id:
                return self.send_json({'error': 'Paramètre id manquant'}, 400)
            student = database.get_student_by_id(st_id)
            if not student:
                return self.send_json({'error': 'Étudiant non trouvé'}, 404)
            local_ip = get_local_ip()
            base_url = f"http://{local_ip}:{PORT}"
            links = whatsapp_manager.get_whatsapp_links(student, base_url=base_url)
            student['phone_wa'] = links['phone_wa']
            student['wa_url'] = links['web_wa']
            student['wa_me_url'] = links['wa_me']
            student['ticket_url'] = f"{base_url}/ticket?id={student['id']}"
            return self.send_json(student)

        # 3. Statistiques temps réel
        if path == '/api/stats':
            stats = database.get_stats()
            return self.send_json(stats)

        # 4. Export CSV de Présence en Direct
        if path == '/api/export-attendance':
            students = database.get_all_students()
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8-sig')
            self.send_header('Content-Disposition', 'attachment; filename="presence_upssa_onboard.csv"')
            self.end_headers()

            # UTF-8 BOM pour Excel
            self.wfile.write(b'\xef\xbb\xbf')
            
            output = []
            writer = csv.writer(sys.stdout)
            lines = [
                ['Identifiant', 'Nom', 'Pôle', 'Année', 'Téléphone', 'Statut Présence', 'Heure de Pointage', 'Gala', 'Teambuilding', 'Transport UPSSA', 'WhatsApp Envoyé']
            ]
            for s in students:
                lines.append([
                    s['id'],
                    s['name'],
                    s['pole'],
                    s['year'],
                    s['phone'],
                    'Présent' if s['attended'] else 'Absent',
                    s.get('scanned_time') or '',
                    'Oui' if s['gala'] else 'Non',
                    'Oui' if s['teambuilding'] else 'Non',
                    'Oui' if s['transport'] else 'Non',
                    'Oui' if s.get('whatsapp_status') == 'sent' else 'Non'
                ])
            csv_str = '\r\n'.join([','.join([f'"{val}"' for val in row]) for row in lines])
            self.wfile.write(csv_str.encode('utf-8'))
            return

        # 5. Export VCF Contacts
        if path == '/api/export-vcf':
            vcf_path = os.path.join(DIRECTORY, 'contacts_upssa_onboard.vcf')
            if not os.path.exists(vcf_path):
                whatsapp_manager.export_contacts_vcf(vcf_path)
            with open(vcf_path, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/vcard; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename="contacts_upssa_onboard.vcf"')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        # Fichiers statiques par défaut
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get('Content-Length', 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b'{}'
        try:
            body = json.loads(body_bytes.decode('utf-8'))
        except Exception:
            body = {}

        # 1. Enregistrement d'un Scan QR Code
        if path == '/api/scan':
            code = body.get('code', '')
            device = body.get('device', 'web')
            if not code:
                return self.send_json({'success': False, 'message': 'Code QR vide'}, 400)
            
            res = database.record_scan(code, device=device)
            return self.send_json(res)

        # 2. Pointage Manuel
        if path == '/api/toggle-presence':
            st_id = body.get('id', '')
            status = body.get('status', None)
            if not st_id:
                return self.send_json({'error': 'ID manquant'}, 400)
            res = database.toggle_student_attendance(st_id, status=status)
            if not res:
                return self.send_json({'error': 'Étudiant non trouvé'}, 404)
            return self.send_json({'success': True, 'data': res})

        # 3. Mise à jour statut WhatsApp
        if path == '/api/whatsapp-status':
            st_id = body.get('id', '')
            status = body.get('status', 'sent')
            if not st_id:
                return self.send_json({'error': 'ID manquant'}, 400)
            ok = database.mark_whatsapp_sent(st_id, status=status)
            return self.send_json({'success': ok})

        return self.send_json({'error': 'Endpoint non trouvé'}, 404)

def run():
    os.chdir(DIRECTORY)
    
    # 1. Initialiser la base SQLite et synchroniser les données
    print("Initialisation du système SQL UPSSA...")
    database.init_db()
    database.seed_students_if_empty()

    # 2. Vérifier que les QR codes et Passes existent
    qr_dir = os.path.join(DIRECTORY, 'qrcodes')
    pass_dir = os.path.join(DIRECTORY, 'passes')
    if not os.path.exists(qr_dir) or len(os.listdir(qr_dir)) < 309:
        print("Génération des QR Codes et Passes officiels manquants...")
        qr_generator.generate_all_assets()

    # 3. Générer les exports initiaux CSV et VCF
    whatsapp_manager.export_dispatch_csv()
    whatsapp_manager.export_contacts_vcf()

    port = PORT
    for p in range(PORT, PORT + 20):
        try:
            with socketserver.TCPServer(("", p), UPSSAHandler) as httpd:
                local_ip = get_local_ip()
                print("=" * 65)
                print("🎓 UPSSA ONBOARD — SYSTÈME COMPLET DE PRÉSENCE & WHATSAPP")
                print("=" * 65)
                print(f"✅ Serveur & Base SQL connectés avec succès !")
                print(f"👉 Sur cet ordinateur          : http://localhost:{p}")
                print(f"📱 Sur smartphone / tablette    : http://{local_ip}:{p}")
                print(f"🎟️ Aperçu billet étudiant       : http://{local_ip}:{p}/ticket?id=1001")
                print(f"📲 Base de données SQLite       : {database.DB_PATH}")
                print(f"📁 QR Codes (309 fichiers PNG)  : {qr_dir}")
                print(f"📁 Passes Digitaux (309 PNG)    : {pass_dir}")
                print("-" * 65)
                print("Appuyez sur Ctrl+C pour arrêter le serveur.")
                print("=" * 65)
                try:
                    httpd.serve_forever()
                except KeyboardInterrupt:
                    print("\n🛑 Arrêt du serveur.")
                return
        except OSError:
            continue

if __name__ == '__main__':
    run()
