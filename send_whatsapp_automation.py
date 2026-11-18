#!/usr/bin/env python3
"""
UPSSA WhatsApp Dispatch Automation Tool
Permet d'envoyer les messages de confirmation WhatsApp avec les QR codes pour toute la liste des étudiants UPSSA.
Offre plusieurs modes : Interactif 1-clic, automatisation navigateur, et exports.
"""

import sys
import os
import time
import argparse
import webbrowser
import subprocess
import database
import whatsapp_manager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def show_status():
    """Affiche l'état d'avancement de l'envoi WhatsApp depuis la base SQLite."""
    stats = database.get_stats()['overview']
    total = stats['total']
    sent = stats['wa_sent_count']
    pending = stats['wa_pending_count']
    pct = round((sent / total) * 100, 1) if total > 0 else 0

    print("=" * 60)
    print("📲 ÉTAT DE L'ENVOI WHATSAPP — UPSSA ONBOARD")
    print("=" * 60)
    print(f"👥 Total Inscrits      : {total}")
    print(f"✅ Messages Envoyés    : {sent} ({pct}%)")
    print(f"⏳ Messages en attente : {pending}")
    print("=" * 60)

def open_student_whatsapp(student, base_url="http://localhost:8080"):
    """Ouvre la conversation WhatsApp avec le message pré-rempli pour un étudiant."""
    links = whatsapp_manager.get_whatsapp_links(student, base_url=base_url)
    pass_file = os.path.join(BASE_DIR, 'passes', f"{student['id']}.png")
    qr_file = os.path.join(BASE_DIR, 'qrcodes', f"{student['id']}.png")

    print("\n" + "-" * 60)
    print(f"👤 Destinataire : {student['name']} ({student['pole']} - {student['year']})")
    print(f"📞 WhatsApp     : +{links['phone_wa']}")
    print(f"🎫 Pass Image   : {pass_file}")
    print(f"🔗 Lien Web     : {links['web_wa'][:80]}...")
    print("-" * 60)

    # Ouvrir WhatsApp Web
    webbrowser.open(links['web_wa'])
    return links

def interactive_dispatch_loop(base_url="http://localhost:8080"):
    """
    Parcourt la liste des étudiants en attente un par un.
    Pour chaque étudiant :
      1. Ouvre la conversation WhatsApp Web pré-remplie.
      2. Indique le fichier image du QR code / Pass à glisser-déposer.
      3. Demande confirmation pour marquer comme 'Envoyé' dans SQLite et passer au suivant.
    """
    students = database.get_all_students(filter_wa='pending')
    total_pending = len(students)

    if total_pending == 0:
        print("🎉 Tous les messages WhatsApp ont déjà été envoyés !")
        return

    print(f"\n🚀 Démarrage de la file d'envoi interactive pour {total_pending} étudiants...")
    print("Instructions :")
    print(" 1. Votre navigateur va ouvrir la conversation WhatsApp avec le message pré-rempli.")
    print(" 2. Glissez-déposez le Pass/QR code dans la conversation WhatsApp.")
    print(" 3. Appuyez sur Entrée dans ce terminal pour marquer comme 'Envoyé' et passer à l'étudiant suivant.")
    print(" 4. Tapez 'q' pour quitter à tout moment.\n")

    input("Appuyez sur Entrée pour commencer...")

    for i, s in enumerate(students, 1):
        print(f"\n[{i}/{total_pending}] Envoi pour {s['name']} ({s['phone_wa']})")
        open_student_whatsapp(s, base_url=base_url)

        pass_file = os.path.join(BASE_DIR, 'passes', f"{s['id']}.png")
        print(f"📸 Image Pass prête à joindre : {pass_file}")

        choice = input("👉 Message envoyé ? [Entrée = Oui / 's' = Passer / 'q' = Quitter] : ").strip().lower()

        if choice == 'q':
            print("🛑 Envoi interrompu par l'utilisateur.")
            break
        elif choice == 's':
            print("⏩ Étudiant ignoré pour le moment.")
            continue
        else:
            database.mark_whatsapp_sent(s['id'], status='sent')
            print(f"✅ {s['name']} marqué comme ENVOYÉ dans la base SQL.")

    show_status()

def main():
    parser = argparse.ArgumentParser(description="UPSSA WhatsApp Broadcast & Dispatch Tool")
    parser.add_argument('--status', action='store_true', help="Afficher les statistiques d'envoi")
    parser.add_argument('--export', action='store_true', help="Exporter la liste CSV et le carnet d'adresses VCF")
    parser.add_argument('--interactive', action='store_true', help="Lancer la boucle d'envoi interactive pas à pas")
    parser.add_argument('--send', type=str, help="Ouvrir WhatsApp pour un identifiant étudiant spécifique")
    parser.add_argument('--mark-sent', type=str, help="Marquer manuellement un ID comme envoyé dans SQLite")
    parser.add_argument('--base-url', type=str, default="http://localhost:8080", help="URL de base du serveur")

    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.export:
        csv_file = whatsapp_manager.export_dispatch_csv(base_url=args.base_url)
        vcf_file = whatsapp_manager.export_contacts_vcf()
        print(f"✅ Exports terminés :\n - CSV : {csv_file}\n - VCF : {vcf_file}")
    elif args.send:
        s = database.get_student_by_id(args.send)
        if s:
            open_student_whatsapp(s, base_url=args.base_url)
        else:
            print(f"❌ Étudiant non trouvé avec l'identifiant {args.send}")
    elif args.mark_sent:
        ok = database.mark_whatsapp_sent(args.mark_sent, status='sent')
        if ok:
            print(f"✅ Étudiant {args.mark_sent} marqué comme envoyé.")
        else:
            print(f"❌ Échec : ID {args.mark_sent} non trouvé.")
    elif args.interactive:
        interactive_dispatch_loop(base_url=args.base_url)
    else:
        show_status()
        print("\nCommandes disponibles :")
        print("  python3 send_whatsapp_automation.py --interactive   # File d'envoi pas-à-pas avec WhatsApp Web")
        print("  python3 send_whatsapp_automation.py --status        # Voir l'avancement")
        print("  python3 send_whatsapp_automation.py --export        # Générer CSV et VCF")
        print("  python3 send_whatsapp_automation.py --send <ID>     # Envoyer à un étudiant précis")

if __name__ == '__main__':
    main()

