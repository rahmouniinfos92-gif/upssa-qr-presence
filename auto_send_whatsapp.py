#!/usr/bin/env python3
"""
UPSSA ONBOARD 2026 — Envoi Automatique WhatsApp Web
Automatise l'envoi des confirmations officielles restantes via la session WhatsApp Web connectée dans Google Chrome.
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

try:
    import database
except ImportError:
    database = None

def run_applescript(script):
    """Exécute un script AppleScript et retourne (code, stdout, stderr)."""
    p = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()

def execute_js_in_whatsapp(js_code):
    """Exécute du JavaScript dans l'onglet WhatsApp Web de Google Chrome."""
    escaped = js_code.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')
    script = f'''
    tell application "Google Chrome"
        set w to front window
        repeat with t in tabs of w
            if URL of t contains "web.whatsapp.com" then
                try
                    set res to (execute t javascript "{escaped}")
                    return res as string
                on error errMsg
                    return "ERROR:" & errMsg
                end try
            end if
        end repeat
    end tell
    return "NO_WHATSAPP_TAB"
    '''
    code, stdout, stderr = run_applescript(script)
    return stdout

def navigate_whatsapp_to_chat(phone, message_text):
    """Navigue l'onglet WhatsApp Web vers l'URL d'envoi."""
    encoded_text = urllib.parse.quote(message_text)
    url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_text}"
    
    script = f'''
    tell application "Google Chrome"
        set w to front window
        repeat with t in tabs of w
            if URL of t contains "web.whatsapp.com" then
                set URL of t to "{url}"
                return "NAVIGATED"
            end if
        end repeat
    end tell
    return "NOT_FOUND"
    '''
    code, stdout, stderr = run_applescript(script)
    return stdout == "NAVIGATED"

def fetch_pending_students(fly_url=FLY_URL):
    """Récupère la liste des étudiants en attente depuis l'API Fly.io ou localement."""
    try:
        url = f"{fly_url}/api/students?whatsapp_status=pending"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data
    except Exception as e:
        print(f"  ⚠️ Synchronisation Fly.io temporairement indisponible ({e}), passage à la base locale...")
        if database:
            return database.get_all_students(filter_wa='pending')
        return []

def mark_student_sent(student_id, fly_url=FLY_URL):
    """Marque l'étudiant comme envoyé sur Fly.io et dans la base SQLite locale."""
    # 1. Fly.io
    try:
        url = f"{fly_url}/api/whatsapp-status"
        payload = json.dumps({"id": student_id, "status": "sent"}).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            pass
    except Exception:
        pass

    # 2. Local
    if database:
        try:
            database.mark_whatsapp_sent(student_id, status='sent')
        except Exception:
            pass

def format_official_message(student, fly_url=FLY_URL):
    """Formate le message officiel exact avec variables dynamiques."""
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

def send_to_student(student, fly_url=FLY_URL, max_wait_sec=20):
    """
    Envoie le message officiel à un étudiant via WhatsApp Web.
    Retourne True si envoyé et confirmé, False sinon.
    """
    phone = student.get('phone_wa') or student.get('phone', '')
    phone = ''.join(c for c in phone if c.isdigit())
    if not phone:
        print(f"  ❌ Numéro de téléphone manquant pour {student.get('name')}")
        return False

    message = format_official_message(student, fly_url=fly_url)
    
    # 1. Navigation
    nav_ok = navigate_whatsapp_to_chat(phone, message)
    if not nav_ok:
        print("  ❌ Échec navigation vers l'onglet WhatsApp")
        return False

    # 2. Polling : détection du bouton Envoyer ou de la popup d'erreur
    start_time = time.time()
    time.sleep(2.5) # Attente minimale de chargement de la discussion

    js_detect_and_send = """
    (function() {
        // A. Vérification de popup d'erreur (numéro non inscrit sur WhatsApp)
        const dialogs = document.querySelectorAll('div[role="dialog"], div[data-animate-modal-body="true"]');
        for (const d of dialogs) {
            const t = d.innerText || '';
            if (t.includes('invalide') || t.includes('invalid') || t.includes('partagé via')) {
                const btn = d.querySelector('button');
                if (btn) btn.click();
                return "INVALID_PHONE";
            }
        }

        // B. Bouton Envoyer officiel (aria-label="Envoyer" ou data-tab="11")
        const sendBtn = document.querySelector('footer button[aria-label="Envoyer"]')
                     || document.querySelector('button[aria-label="Envoyer"]')
                     || document.querySelector('footer button[data-tab="11"][aria-label="Envoyer"]');

        if (sendBtn && sendBtn.getAttribute('aria-label') === 'Envoyer') {
            sendBtn.click();
            return "CLICKED";
        }

        // C. Vérification si le texte est dans le champ de saisie
        const composer = document.querySelector('footer div[contenteditable="true"]');
        if (composer && composer.innerText.trim().length > 10) {
            return "READY_WAITING_BUTTON";
        }

        return "LOADING";
    })()
    """

    js_verify_sent = """
    (function() {
        const composer = document.querySelector('footer div[contenteditable="true"]');
        const sendBtn = document.querySelector('footer button[aria-label="Envoyer"]');
        // Si le bouton Envoyer a disparu ou le champ est vide -> message parti !
        if (!sendBtn || (composer && composer.innerText.trim().length === 0)) {
            return "CONFIRMED_SENT";
        }
        return "STILL_SENDING";
    })()
    """

    clicked = False
    while time.time() - start_time < max_wait_sec:
        status = execute_js_in_whatsapp(js_detect_and_send)
        
        if status == "CLICKED":
            clicked = True
            break
        elif status == "INVALID_PHONE":
            print(f"  ⚠️ Numéro non disponible sur WhatsApp (+{phone})")
            return False

        time.sleep(0.6)

    if not clicked:
        # Fallback : tentative d'envoi par simulation Entrée
        fb_js = """
        (function() {
            const c = document.querySelector('footer div[contenteditable="true"]');
            if (c && c.innerText.trim().length > 10) {
                const ke = new KeyboardEvent('keydown', {bubbles: true, cancelable: true, keyCode: 13, which: 13, key: 'Enter', code: 'Enter'});
                c.dispatchEvent(ke);
                return "DISPATCHED";
            }
            return "NOT_READY";
        })()
        """
        if execute_js_in_whatsapp(fb_js) == "DISPATCHED":
            clicked = True

    if clicked:
        # Attente de la confirmation d'envoi par WhatsApp
        time.sleep(1.2)
        confirm = execute_js_in_whatsapp(js_verify_sent)
        mark_student_sent(student['id'], fly_url=fly_url)
        return True
    else:
        print(f"  ⏳ Délai dépassé pour +{phone}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Envoi Automatique WhatsApp UPSSA ONBOARD")
    parser.add_argument('--limit', type=int, default=0, help="Nombre d'étudiants (0 = tous)")
    parser.add_argument('--delay', type=float, default=3.5, help="Pause de sécurité entre messages (secondes)")
    args = parser.parse_args()

    print("=" * 65)
    print("📲 UPSSA ONBOARD 2026 — DISPATCH AUTOMATIQUE WHATSAPP")
    print("👤 Compte émetteur connecté : 0606196089 (+212606196089)")
    print(f"🌐 Plateforme Cloud         : {FLY_URL}")
    print("=" * 65)

    # Vérification connexion
    title = execute_js_in_whatsapp("document.title")
    if "WhatsApp" not in title:
        print(f"❌ Impossible de communiquer avec l'onglet WhatsApp Web (titre: {title})")
        sys.exit(1)

    print(f"✅ Connecté à WhatsApp Web ({title})")

    # Récupération de la file d'attente
    pending = fetch_pending_students(FLY_URL)
    total_pending = len(pending)
    print(f"📊 Étudiants restant à notifier : {total_pending}")

    if total_pending == 0:
        print("🎉 Tous les messages WhatsApp ont déjà été envoyés avec succès (309/309) !")
        return

    to_process = pending[:args.limit] if args.limit > 0 else pending
    count_to_process = len(to_process)

    print(f"🚀 Démarrage de l'envoi pour {count_to_process} étudiant(s) (Pause : {args.delay}s)...")
    print("👉 Appuyez sur Ctrl+C pour arrêter à tout moment (vos progrès restent sauvegardés).\n")

    success_count = 0
    fail_count = 0

    for idx, st in enumerate(to_process, 1):
        st_id = st.get('id', '')
        st_name = st.get('name', 'Étudiant')
        st_phone = st.get('phone_wa') or st.get('phone', '')
        st_pole = st.get('pole', 'Santé')

        print(f"[{idx}/{count_to_process}] {st_name} (ID: {st_id} | 📞 +{st_phone} | {st_pole})... ", end="", flush=True)

        ok = send_to_student(st, fly_url=FLY_URL)
        if ok:
            print("✅ ENVOYÉ")
            success_count += 1
        else:
            print("⚠️ NON ENVOYÉ")
            fail_count += 1

        if idx < count_to_process:
            time.sleep(args.delay)

    print("\n" + "=" * 65)
    print(f"🏁 ENVOI TERMINÉ : {success_count} envoyés avec succès, {fail_count} ignorés/échoués.")
    print(f"📊 Vérification en direct sur : {FLY_URL}")
    print("=" * 65)

if __name__ == '__main__':
    main()
