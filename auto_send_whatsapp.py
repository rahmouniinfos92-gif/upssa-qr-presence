#!/usr/bin/env python3
"""
UPSSA ONBOARD 2026 — Envoi Automatique WhatsApp Web
Automatise l'envoi des 205 confirmations officielles restantes via la session WhatsApp Web connectée dans Google Chrome.
Numéro émetteur : 0606196089 (+212606196089)
"""

import sys
import os
import time
import json
import urllib.parse
import urllib.request
import subprocess
import argparse

FLY_URL = "https://upssa-qr-presence.fly.dev"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Import des modules locaux si présents
try:
    import database
    import whatsapp_manager
except ImportError:
    database = None
    whatsapp_manager = None

def run_applescript(script):
    """Exécute un script AppleScript et retourne le résultat stdout."""
    p = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()

def check_chrome_and_whatsapp():
    """Vérifie que Google Chrome est ouvert et trouve l'onglet WhatsApp Web."""
    script = '''
    tell application "Google Chrome"
        set out to "NOT_FOUND"
        set windowList to every window
        repeat with w in windowList
            set i to 1
            repeat with t in tabs of w
                if URL of t contains "web.whatsapp.com" then
                    return (id of w as string) & ":" & (i as string) & ":" & (URL of t)
                end if
                set i to i + 1
            end repeat
        end repeat
        return out
    end tell
    '''
    code, stdout, stderr = run_applescript(script)
    if code != 0 or stdout == "NOT_FOUND":
        return None
    parts = stdout.split(":", 2)
    return {
        "window_id": parts[0],
        "tab_index": int(parts[1]),
        "url": parts[2]
    }

def test_js_enabled(tab_info):
    """Vérifie si 'Autoriser JavaScript dans les événements AppleScript' est activé dans Chrome."""
    w_id = tab_info["window_id"]
    t_idx = tab_info["tab_index"]
    script = f'''
    tell application "Google Chrome"
        repeat with w in every window
            if (id of w as string) is "{w_id}" then
                set t to tab {t_idx} of w
                try
                    set res to (execute t javascript "document.title")
                    return "OK:" & res
                on error errMsg
                    return "ERR:" & errMsg
                end try
            end if
        end repeat
    end tell
    '''
    code, stdout, stderr = run_applescript(script)
    if stdout.startswith("OK:"):
        return True, stdout[3:]
    return False, stdout[4:] if stdout.startswith("ERR:") else stdout

def execute_js_in_tab(tab_info, js_code):
    """Exécute du code JavaScript dans l'onglet WhatsApp Web."""
    w_id = tab_info["window_id"]
    t_idx = tab_info["tab_index"]
    # Échappement des guillemets pour AppleScript
    escaped_js = js_code.replace('\\', '\\\\').replace('"', '\\"')
    script = f'''
    tell application "Google Chrome"
        repeat with w in every window
            if (id of w as string) is "{w_id}" then
                set t to tab {t_idx} of w
                try
                    set res to (execute t javascript "{escaped_js}")
                    return res as string
                on error errMsg
                    return "ERROR:" & errMsg
                end try
            end if
        end repeat
    end tell
    '''
    code, stdout, stderr = run_applescript(script)
    return stdout

def navigate_whatsapp_tab(tab_info, target_url):
    """Change l'URL de l'onglet WhatsApp Web pour ouvrir la conversation."""
    w_id = tab_info["window_id"]
    t_idx = tab_info["tab_index"]
    script = f'''
    tell application "Google Chrome"
        repeat with w in every window
            if (id of w as string) is "{w_id}" then
                set URL of tab {t_idx} of w to "{target_url}"
                return "OK"
            end if
        end repeat
    end tell
    '''
    run_applescript(script)

def fetch_pending_students(fly_url=FLY_URL):
    """Récupère la liste des étudiants en attente directement depuis l'API Fly.io."""
    try:
        url = f"{fly_url}/api/students?whatsapp_status=pending"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data
    except Exception as e:
        print(f"⚠️ Impossible de contacter Fly.io ({e}), utilisation de la base locale...")
        if database:
            return database.get_all_students(filter_wa='pending')
        return []

def mark_student_sent(student_id, fly_url=FLY_URL):
    """Marque l'étudiant comme envoyé à la fois sur Fly.io et en local."""
    # 1. Fly.io
    try:
        url = f"{fly_url}/api/whatsapp-status"
        payload = json.dumps({"id": student_id, "status": "sent"}).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            pass
    except Exception as e:
        print(f"  ⚠️ Sync Fly.io warning : {e}")

    # 2. Local SQLite
    if database:
        try:
            database.mark_whatsapp_sent(student_id, status='sent')
        except Exception:
            pass

def format_official_message(student, fly_url=FLY_URL):
    """Génère le texte officiel exact du message WhatsApp."""
    name = student.get('name', 'étudiant(e)')
    st_id = student.get('id', '')
    transport = student.get('transport')
    
    if transport:
        trans_txt = "Rendez-vous à 11h30 au campus pour un départ à 12h précises (Transport réservé ✅)."
    else:
        trans_txt = "Non réservé (accès direct par vos propres moyens au Hyatt Place Taghazout)."

    ticket_url = f"{fly_url}/ticket?id={st_id}"

    msg = f"""🎉 *UPSSA ONBOARD | CONFIRMATION OFFICIELLE*

Cher(e) {name},

Nous avons le plaisir de vous confirmer votre inscription à la journée *UPSSA ONBOARD – Team Building & Soirée*, qui se tiendra *mercredi 18 novembre 2026, au Hyatt Place Taghazout !* 🎉

✨ Une journée exceptionnelle vous attend, entre challenges, esprit d'équipe, rencontres et ambiance festive !

🎟️ *Votre QR Code personnel est joint à ce message.* Il devra obligatoirement être présenté et scanné à votre arrivée pour accéder à l'événement.
*(Code d'accès personnel : {st_id})*

⚠️ *Important :* Votre inscription est valable pour l'ensemble du programme (Team Building + Soirée). L'accès uniquement à la soirée ne sera pas autorisé.

🚌 *Transport UPSSA :* {trans_txt}

🔗 *Lien direct vers votre e-Billet & QR Code :*
{ticket_url}

Nous comptons sur votre présence et votre ponctualité pour faire de cette journée un moment inoubliable !

See you 🚀

*UPSSA Student Life*"""
    return msg

def send_to_student(tab_info, student, fly_url=FLY_URL, max_wait_sec=18):
    """
    Envoie le message WhatsApp à un étudiant via WhatsApp Web.
    Retourne True si le message a été envoyé avec succès, False sinon.
    """
    phone = student.get('phone_wa') or student.get('phone', '')
    phone = ''.join(c for c in phone if c.isdigit())
    if not phone:
        print(f"  ❌ Numéro de téléphone manquant pour {student.get('name')}")
        return False

    message = format_official_message(student, fly_url=fly_url)
    encoded_text = urllib.parse.quote(message)
    target_url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_text}"

    # Navigation vers la conversation
    navigate_whatsapp_tab(tab_info, target_url)

    # Polling : attente du chargement du bouton d'envoi ou détection d'erreur
    start_time = time.time()
    
    js_check_send = """
    (function() {
        // 1. Détection d'une popup d'erreur (numéro invalide)
        const modals = document.querySelectorAll('div[role="dialog"], div[data-animate-modal-body="true"]');
        for (const m of modals) {
            const txt = m.innerText || '';
            if (txt.includes('invalide') || txt.includes('non valide') || txt.includes('invalid') || txt.includes('partagé via')) {
                // Cliquer sur le bouton OK pour fermer
                const btn = m.querySelector('button');
                if (btn) btn.click();
                return "INVALID_PHONE";
            }
        }

        // 2. Recherche du bouton Envoyer (icône d'avion en papier)
        const sendBtn = document.querySelector('button[aria-label="Envoyer"]')
                     || document.querySelector('button[aria-label="Send"]')
                     || document.querySelector('span[data-icon="send"]')?.closest('button')
                     || document.querySelector('span[data-icon="send-light"]')?.closest('button')
                     || document.querySelector('button[data-testid="compose-btn-send"]')
                     || document.querySelector('button[data-tab="11"]');

        if (sendBtn) {
            // Vérifier que le bouton n'est pas désactivé
            if (!sendBtn.disabled) {
                sendBtn.click();
                return "SENT";
            }
        }

        // 3. Fallback : simuler la touche Entrée sur le champ éditable
        const composer = document.querySelector('div[contenteditable="true"][data-tab="10"]')
                      || document.querySelector('footer div[contenteditable="true"]');
        if (composer && composer.innerText.trim().length > 10) {
            // Le texte est bien présent
            return "READY_WAITING_BUTTON";
        }

        return "LOADING";
    })()
    """

    time.sleep(3) # Attendre que WhatsApp commence le chargement

    sent = False
    while time.time() - start_time < max_wait_sec:
        res = execute_js_in_tab(tab_info, js_check_send)
        
        if res == "SENT":
            sent = True
            break
        elif res == "INVALID_PHONE":
            print(f"  ⚠️ Numéro invalide ou non WhatsApp sur +{phone}")
            return False
        
        time.sleep(0.7)

    if not sent:
        # Tentative de secours : appuyer sur Entrée via JS
        fallback_js = """
        (function() {
            const sendBtn = document.querySelector('button[aria-label="Envoyer"]') 
                         || document.querySelector('span[data-icon="send"]')?.closest('button');
            if (sendBtn) {
                sendBtn.click();
                return "CLICKED_RETRY";
            }
            return "FAILED";
        })()
        """
        fb_res = execute_js_in_tab(tab_info, fallback_js)
        if fb_res == "CLICKED_RETRY":
            sent = True

    if sent:
        # Attendre 1.5s que l'envoi réseau soit complété par WhatsApp
        time.sleep(1.5)
        mark_student_sent(student['id'], fly_url=fly_url)
        return True
    else:
        print(f"  ⏳ Délai dépassé pour +{phone} (bouton non cliqué)")
        return False

def main():
    parser = argparse.ArgumentParser(description="Automatisation d'envoi WhatsApp UPSSA ONBOARD")
    parser.add_argument('--limit', type=int, default=0, help="Nombre max d'étudiants à envoyer (0 = tous les restants)")
    parser.add_argument('--delay', type=float, default=3.5, help="Pause de sécurité en secondes entre chaque envoi (défaut : 3.5s)")
    parser.add_argument('--dry-run', action='store_true', help="Affiche les messages sans les envoyer")
    args = parser.parse_args()

    print("=" * 65)
    print("📲 UPSSA ONBOARD 2026 — DISPATCH AUTOMATIQUE WHATSAPP")
    print(f"👤 Compte émetteur connecté : 0606196089 (+212606196089)")
    print(f"🌐 Plateforme Cloud         : {FLY_URL}")
    print("=" * 65)

    # 1. Vérification de l'onglet Chrome
    tab_info = check_chrome_and_whatsapp()
    if not tab_info:
        print("❌ Erreur : Onglet WhatsApp Web non trouvé dans Google Chrome !")
        print("👉 Assurez-vous que Google Chrome est ouvert avec l'onglet https://web.whatsapp.com/ actif.")
        sys.exit(1)

    print(f"✅ Onglet WhatsApp Web détecté dans Chrome (Fenêtre #{tab_info['window_id']}, Onglet #{tab_info['tab_index']}).")

    # 2. Vérification de l'autorisation JavaScript
    js_ok, js_msg = test_js_enabled(tab_info)
    if not js_ok:
        print("\n" + "⚠️ " * 20)
        print("🛑 ACTION UNIQUE REQUISE DANS GOOGLE CHROME (prend 2 secondes) :")
        print("Dans la barre de menu tout en haut de votre écran Mac :")
        print("  1. Cliquez sur : Affichage (ou 'View')")
        print("  2. Cliquez sur : Développeur (ou 'Developer')")
        print("  3. Cochez      : Autoriser JavaScript dans les événements AppleScript")
        print("                   (Allow JavaScript from Apple Events)")
        print("⚠️ " * 20 + "\n")
        print("Une fois coché, relancez simplement ce script !")
        sys.exit(2)

    print("✅ Autorisation AppleScript JavaScript validée avec succès !")

    # 3. Récupération des étudiants en attente
    pending = fetch_pending_students(FLY_URL)
    total_pending = len(pending)
    print(f"\n📊 Étudiants restant à notifier : {total_pending}")

    if total_pending == 0:
        print("🎉 Aucun message en attente ! Les 309 étudiants ont tous été notifiés.")
        return

    to_process = pending[:args.limit] if args.limit > 0 else pending
    count_to_process = len(to_process)

    print(f"🚀 Prêt à envoyer à {count_to_process} étudiant(s) avec une pause de {args.delay}s entre chaque envoi.")
    print("👉 Vous pouvez interrompre à tout moment avec Ctrl+C (les progrès seront conservés).\n")

    success_count = 0
    fail_count = 0

    for idx, st in enumerate(to_process, 1):
        st_id = st.get('id', '')
        st_name = st.get('name', 'Étudiant')
        st_phone = st.get('phone_wa') or st.get('phone', '')
        st_pole = st.get('pole', 'Santé')

        print(f"[{idx}/{count_to_process}] Envoi pour {st_name} (ID: {st_id}, 📞 +{st_phone}, Pôle {st_pole})...", end="", flush=True)

        if args.dry_run:
            print(" [SIMULATION - OK]")
            success_count += 1
            continue

        ok = send_to_student(tab_info, st, fly_url=FLY_URL)
        if ok:
            print(" ✅ ENVOYÉ & VALIDÉ")
            success_count += 1
        else:
            print(" ⚠️ ÉCHEC / IGNORÉ")
            fail_count += 1

        # Pause de sécurité anti-spam WhatsApp
        if idx < count_to_process:
            time.sleep(args.delay)

    print("\n" + "=" * 65)
    print(f"🏁 ENVOI TERMINÉ : {success_count} réussis, {fail_count} ignorés/échoués.")
    print(f"📊 Vérification en direct sur : {FLY_URL}")
    print("=" * 65)

if __name__ == '__main__':
    main()
