#!/usr/bin/env python3
"""
UPSSA QR Code & Event Pass Generator
Générateur de vrais QR Codes haute résolution et de Cartes d'Accès Digitales Officielles.
Utilise qrcodegen (pur python) et Pillow (PIL).
"""

import os
import sys
import qrcodegen
from PIL import Image, ImageDraw, ImageFont
import database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QR_DIR = os.path.join(BASE_DIR, 'qrcodes')
PASS_DIR = os.path.join(BASE_DIR, 'passes')

os.makedirs(QR_DIR, exist_ok=True)
os.makedirs(PASS_DIR, exist_ok=True)

def generate_qr_matrix(text, ecc=qrcodegen.QrCode.Ecc.MEDIUM):
    """Génère la matrice booléenne du QR Code."""
    return qrcodegen.QrCode.encode_text(text, ecc)

def create_qr_image(text, output_path, scale=12, border=4, fill_color=(12, 35, 64), bg_color=(255, 255, 255)):
    """
    Génère un fichier PNG de QR code propre et haute résolution.
    fill_color par défaut : Bleu Nuit UPSSA (#0c2340).
    """
    qr = generate_qr_matrix(text)
    size = qr.get_size()
    dim = (size + border * 2) * scale

    img = Image.new('RGB', (dim, dim), bg_color)
    draw = ImageDraw.Draw(img)

    for y in range(size):
        for x in range(size):
            if qr.get_module(x, y):
                rx = (x + border) * scale
                ry = (y + border) * scale
                draw.rectangle([rx, ry, rx + scale - 1, ry + scale - 1], fill=fill_color)

    img.save(output_path, 'PNG', optimize=True)
    return output_path

def get_font(size=16, bold=False):
    """Retourne une police système Mac/Linux ou la police par défaut."""
    font_paths = [
        "/System/Library/Fonts/SFPro-Bold.ttf" if bold else "/System/Library/Fonts/SFPro-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()

def create_digital_pass(student, output_path):
    """
    Génère un Pass Digital VIP UPSSA Onboard officiel sous forme d'image PNG haute qualité (600 x 920 px).
    Parfait pour l'envoi WhatsApp !
    """
    width = 640
    height = 960
    
    # Couleurs de la charte UPSSA
    c_navy = (12, 35, 64)       # #0c2340 Bleu nuit UPSSA
    c_gold = (212, 160, 23)     # #d4a017 Or festif
    c_bg = (248, 249, 252)      # Fond carte
    c_white = (255, 255, 255)
    c_card_bg = (255, 255, 255)
    c_gray_dark = (51, 65, 85)  # Texte principal
    c_gray_light = (100, 116, 139)
    c_green = (16, 185, 129)
    c_red = (239, 68, 68)

    img = Image.new('RGB', (width, height), (235, 240, 245))
    draw = ImageDraw.Draw(img)

    # Carte principale avec coins arrondis
    card_margin = 20
    draw.rounded_rectangle(
        [card_margin, card_margin, width - card_margin, height - card_margin],
        radius=24,
        fill=c_card_bg,
        outline=(226, 232, 240),
        width=2
    )

    # Header de la carte (Bandeau Bleu Nuit)
    header_height = 200
    draw.rounded_rectangle(
        [card_margin, card_margin, width - card_margin, card_margin + header_height],
        radius=24,
        fill=c_navy
    )
    # Rectangle pour aplanir le bas du header
    draw.rectangle(
        [card_margin, card_margin + header_height - 24, width - card_margin, card_margin + header_height],
        fill=c_navy
    )

    # Polices
    f_subhead = get_font(14, bold=True)
    f_title = get_font(26, bold=True)
    f_date = get_font(14, bold=False)
    f_name = get_font(28, bold=True)
    f_detail = get_font(15, bold=False)
    f_badge = get_font(12, bold=True)
    f_id = get_font(15, bold=True)
    f_warn = get_font(12, bold=False)
    f_footer = get_font(12, bold=True)

    # Textes du Header
    draw.text((width // 2, 45), "UNIVERSITÉ PRIVÉE DE SANTÉ SOUSS ALMASSIRA", fill=(180, 200, 225), font=f_subhead, anchor="mm")
    draw.text((width // 2, 85), "🎉 UPSSA ONBOARD 2026", fill=c_gold, font=f_title, anchor="mm")
    draw.text((width // 2, 120), "Team Building & Soirée de Gala", fill=c_white, font=get_font(17, bold=True), anchor="mm")
    draw.text((width // 2, 155), "Mercredi 18 Novembre 2026  •  Hyatt Place Taghazout", fill=(210, 225, 245), font=f_date, anchor="mm")

    # Nom de l'étudiant
    draw.text((width // 2, 255), student.get('name', 'Étudiant(e)'), fill=c_navy, font=f_name, anchor="mm")
    
    # Pôle & Année
    pole = student.get('pole', 'Études')
    year = student.get('year', 'Année')
    draw.text((width // 2, 290), f"Pôle {pole}  •  {year}", fill=c_gray_light, font=f_detail, anchor="mm")

    # Badges de prestations (Gala, Teambuilding, Transport)
    badges_y = 330
    badges = [
        ("GALA", "OUI" if student.get('gala') else "NON", c_green if student.get('gala') else c_gray_light),
        ("TEAMBUILDING", "OUI" if student.get('teambuilding') else "NON", c_green if student.get('teambuilding') else c_gray_light),
        ("TRANSPORT BUS", "OUI (11h30)" if student.get('transport') else "NON", c_navy if student.get('transport') else c_gray_light)
    ]
    
    badge_w = 175
    badge_h = 44
    start_x = (width - (3 * badge_w + 2 * 15)) // 2

    for i, (label, val, col) in enumerate(badges):
        bx = start_x + i * (badge_w + 15)
        # fond du badge
        draw.rounded_rectangle([bx, badges_y, bx + badge_w, badges_y + badge_h], radius=8, fill=(241, 245, 249))
        draw.text((bx + badge_w // 2, badges_y + 12), label, fill=c_gray_light, font=f_badge, anchor="mm")
        draw.text((bx + badge_w // 2, badges_y + 30), val, fill=col, font=get_font(13, bold=True), anchor="mm")

    # Génération du QR Code dans une sous-image temporaire
    st_id = student.get('id', '')
    qr_data = f"UPSSA:{st_id}"
    qr_matrix = generate_qr_matrix(qr_data, qrcodegen.QrCode.Ecc.MEDIUM)
    q_size = qr_matrix.get_size()
    q_scale = 8
    q_dim = q_size * q_scale

    qr_img = Image.new('RGB', (q_dim, q_dim), c_white)
    qr_draw = ImageDraw.Draw(qr_img)
    for y in range(q_size):
        for x in range(q_size):
            if qr_matrix.get_module(x, y):
                qr_draw.rectangle([x * q_scale, y * q_scale, (x + 1) * q_scale - 1, (y + 1) * q_scale - 1], fill=c_navy)

    # Cadre du QR Code
    qr_box_y = 405
    qr_box_dim = q_dim + 40
    qr_box_x = (width - qr_box_dim) // 2
    draw.rounded_rectangle(
        [qr_box_x, qr_box_y, qr_box_x + qr_box_dim, qr_box_y + qr_box_dim],
        radius=16,
        fill=c_white,
        outline=(203, 213, 225),
        width=2
    )
    img.paste(qr_img, (qr_box_x + 20, qr_box_y + 20))

    # Identifiant sous le QR Code
    id_y = qr_box_y + qr_box_dim + 25
    draw.text((width // 2, id_y), f"CODE D'ACCÈS : {st_id}", fill=c_navy, font=f_id, anchor="mm")

    # Ligne pointillée décorative
    sep_y = id_y + 30
    for sx in range(card_margin + 30, width - card_margin - 30, 12):
        draw.line([(sx, sep_y), (sx + 6, sep_y)], fill=(203, 213, 225), width=2)

    # Avertissement & Instructions
    instr_y = sep_y + 35
    draw.text((width // 2, instr_y), "🎟️ Présentez ce QR Code à l'accueil pour valider votre entrée", fill=c_navy, font=get_font(13, bold=True), anchor="mm")
    draw.text((width // 2, instr_y + 24), "⚠️ Billet nominatif et non transférable. Valable pour toute la journée.", fill=(185, 28, 28), font=f_warn, anchor="mm")

    # Pied de page
    foot_y = height - card_margin - 35
    draw.text((width // 2, foot_y), "UPSSA STUDENT LIFE  •  BIENVENUE !", fill=c_gray_light, font=f_footer, anchor="mm")

    img.save(output_path, 'PNG', optimize=True)
    return output_path

def generate_all_assets():
    """Génère les QR Codes et les Cartes d'Accès pour TOUS les étudiants de la base SQLite."""
    students = database.get_all_students()
    total = len(students)
    print(f"🚀 Début de la génération pour {total} étudiants...")

    qr_count = 0
    pass_count = 0

    for i, s in enumerate(students, 1):
        st_id = s['id']
        qr_file = os.path.join(QR_DIR, f"{st_id}.png")
        pass_file = os.path.join(PASS_DIR, f"{st_id}.png")

        # 1. QR Code brut
        create_qr_image(f"UPSSA:{st_id}", qr_file, scale=10, border=4)
        qr_count += 1

        # 2. Pass Digital officiel avec design
        create_digital_pass(s, pass_file)
        pass_count += 1

        if i % 50 == 0 or i == total:
            print(f"  ⚡ {i}/{total} passes & QR codes générés ({round(i/total*100)}%)...")

    print(f"✅ Terminé avec succès : {qr_count} QR Codes et {pass_count} Passes générés !")
    return qr_count, pass_count

if __name__ == '__main__':
    print("Test du générateur UPSSA QR Code...")
    st_test = database.get_all_students()
    if st_test:
        sample = st_test[0]
        q_path = os.path.join(QR_DIR, f"{sample['id']}.png")
        p_path = os.path.join(PASS_DIR, f"{sample['id']}.png")
        create_qr_image(f"UPSSA:{sample['id']}", q_path)
        create_digital_pass(sample, p_path)
        print(f"Sample QR créé : {q_path}")
        print(f"Sample Pass créé : {p_path}")
        print("Lancement de la génération complète...")
        generate_all_assets()

