#!/usr/bin/env python3
"""
UPSSA WhatsApp Broadcast & Dispatch Manager
Gère le formatage des messages officiels WhatsApp, la génération des liens directs wa.me,
l'export CSV/VCF pour envoi en masse, et le suivi d'envoi dans la base SQL.
"""

import os
import sys
import urllib.parse
import csv
import json
from datetime import datetime
import database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Modèle de message officiel UPSSA
DEFAULT_MESSAGE_TEMPLATE = """🎉 *UPSSA ONBOARD | CONFIRMATION OFFICIELLE*

Cher(e) {name},

Nous avons le plaisir de vous confirmer votre inscription à la journée *UPSSA ONBOARD – Team Building & Soirée*, qui se tiendra *mercredi 18 novembre 2026, au Hyatt Place Taghazout !* 🎉

✨ Une journée exceptionnelle vous attend, entre challenges, esprit d'équipe, rencontres et ambiance festive !

🎟️ *Votre QR Code personnel est joint à ce message.* Il devra obligatoirement être présenté et scanné à votre arrivée pour accéder à l'événement.
*(Code d'accès personnel : {id})*

⚠️ *Important :* Votre inscription est valable pour l'ensemble du programme (Team Building + Soirée). L'accès uniquement à la soirée ne sera pas autorisé.

🚌 *Transport UPSSA :* {transport_text}

{ticket_url_text}Nous comptons sur votre présence et votre ponctualité pour faire de cette journée un moment inoubliable !

See you 🚀

*UPSSA Student Life*"""

def get_transport_text(student):
    """Retourne la consigne de transport adaptée au choix de l'étudiant."""
    if student.get('transport'):
        return "Rendez-vous à 11h30 au campus pour un départ à 12h précises (Transport réservé ✅)."
    else:
        return "Non réservé (accès direct par vos propres moyens au Hyatt Place Taghazout)."

def generate_message(student, base_url=None, personalized_name=True):
    """Génère le texte complet du message WhatsApp pour un étudiant."""
    name = student.get('name', 'étudiant(e)') if personalized_name else 'étudiant(e)'
    st_id = student.get('id', '')
    transport_text = get_transport_text(student)

    ticket_url_text = ""
    if base_url:
        ticket_url_text = f"🔗 *Lien direct vers votre e-Billet & QR Code :*\n{base_url}/ticket?id={st_id}\n\n"

    message = DEFAULT_MESSAGE_TEMPLATE.format(
        name=name,
        id=st_id,
        transport_text=transport_text,
        ticket_url_text=ticket_url_text
    )
    return message

def get_whatsapp_links(student, base_url=None):
    """Génère les liens WhatsApp Web et wa.me pour un étudiant."""
    phone_wa = student.get('phone_wa', '')
    if not phone_wa:
        phone_wa = database.format_whatsapp_phone(student.get('phone', ''))

    message = generate_message(student, base_url=base_url)
    encoded_message = urllib.parse.quote(message)

    wa_me_url = f"https://wa.me/{phone_wa}?text={encoded_message}"
    web_wa_url = f"https://web.whatsapp.com/send?phone={phone_wa}&text={encoded_message}"
    app_wa_url = f"whatsapp://send?phone={phone_wa}&text={encoded_message}"

    return {
        'phone_wa': phone_wa,
        'message': message,
        'wa_me': wa_me_url,
        'web_wa': web_wa_url,
        'app_wa': app_wa_url
    }

def export_dispatch_csv(output_path=None, base_url="http://localhost:8080"):
    """Exporte la liste complète des 309 étudiants prête pour l'envoi WhatsApp en CSV."""
    if output_path is None:
        output_path = os.path.join(BASE_DIR, 'whatsapp_dispatch_list.csv')

    students = database.get_all_students()

    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Identifiant',
            'Nom',
            'Pôle',
            'Année',
            'Téléphone Original',
            'Téléphone WhatsApp',
            'Statut Envoi WhatsApp',
            'Date Envoi',
            'Transport',
            'Gala',
            'Teambuilding',
            'Lien WhatsApp Web',
            'Lien wa.me Direct',
            'Fichier QR Code',
            'Fichier Pass Digital',
            'Message Complet'
        ])

        for s in students:
            links = get_whatsapp_links(s, base_url=base_url)
            qr_abs = os.path.join(BASE_DIR, 'qrcodes', f"{s['id']}.png")
            pass_abs = os.path.join(BASE_DIR, 'passes', f"{s['id']}.png")

            writer.writerow([
                s['id'],
                s['name'],
                s['pole'],
                s['year'],
                s['phone'],
                links['phone_wa'],
                s.get('whatsapp_status', 'pending'),
                s.get('whatsapp_sent_at', ''),
                'Oui' if s['transport'] else 'Non',
                'Oui' if s['gala'] else 'Non',
                'Oui' if s['teambuilding'] else 'Non',
                links['web_wa'],
                links['wa_me'],
                qr_abs,
                pass_abs,
                links['message']
            ])

    print(f"✅ Export CSV WhatsApp créé avec succès : {output_path}")
    return output_path

def export_contacts_vcf(output_path=None):
    """
    Exporte tous les contacts au format standard vCard (.vcf).
    Permet à l'organisateur d'importer les 309 contacts en 1 clic dans son carnet d'adresses
    pour que WhatsApp reconnaisse immédiatement tous les étudiants avec leurs noms et prénoms.
    """
    if output_path is None:
        output_path = os.path.join(BASE_DIR, 'contacts_upssa_onboard.vcf')

    students = database.get_all_students()

    with open(output_path, 'w', encoding='utf-8') as f:
        for s in students:
            phone_wa = s.get('phone_wa', '')
            name = s.get('name', 'Étudiant')
            pole = s.get('pole', 'UPSSA')
            f.write("BEGIN:VCARD\n")
            f.write("VERSION:3.0\n")
            f.write(f"FN:UPSSA - {name} ({pole})\n")
            f.write(f"N:{name};UPSSA;;;\n")
            f.write(f"TEL;TYPE=CELL:+{phone_wa}\n")
            if s.get('email'):
                f.write(f"EMAIL:{s['email']}\n")
            f.write(f"NOTE:ID: {s['id']} | Pole: {pole} | Annee: {s.get('year', '')}\n")
            f.write("END:VCARD\n")

    print(f"✅ Fichier contacts vCard créé avec succès : {output_path}")
    return output_path

if __name__ == '__main__':
    print("Test du module WhatsApp Manager...")
    sample = database.get_student_by_id('f14um11i7q')
    if sample:
        links = get_whatsapp_links(sample, base_url="http://localhost:8080")
        print("\n--- APERÇU DU MESSAGE FORMATÉ ---")
        print(links['message'])
        print("\n--- LIEN WHATSAPP ---")
        print("wa.me :", links['wa_me'][:100], "...")
        print("Téléphone WhatsApp :", links['phone_wa'])

    export_dispatch_csv()
    export_contacts_vcf()

