# 🎓 UPSSA ONBOARD — Système Complet de Scan QR Code, Base de Données SQL & Diffusion WhatsApp

Ce projet est une solution complète, autonome et professionnelle de gestion des présences et d'envoi de confirmations officielles pour l'événement **UPSSA ONBOARD – Team Building & Soirée Gala** (mercredi 18 novembre 2026 au **Hyatt Place Taghazout**).

Il intègre une **base de données SQL (SQLite)**, un **générateur de vrais QR Codes et Pass Digitaux haute définition**, et un **Centre de Diffusion WhatsApp interactif et automatisé** pour l'ensemble des 309 étudiants inscrits.

---

## 🌐 Liens de Déploiement en Ligne

- **Application en Production (Fly.io) :** [https://upssa-qr-presence.fly.dev/](https://upssa-qr-presence.fly.dev/)
- **Exemple de Billet d'accès étudiant :** [https://upssa-qr-presence.fly.dev/ticket?id=1002](https://upssa-qr-presence.fly.dev/ticket?id=1002)
- **Tableau de bord Fly.io :** [https://fly.io/dashboard/kan-kantim](https://fly.io/dashboard/kan-kantim)
- **Dépôt GitHub :** [https://github.com/rahmouniinfos92-gif/upssa-qr-presence](https://github.com/rahmouniinfos92-gif/upssa-qr-presence)

---

## 🚀 Démarrage Rapide

### 1. Lancer l'Application & la Base SQL
Ouvrez un terminal dans le dossier du projet :
```bash
./start.sh
# ou
python3 start_server.py
```

Le serveur local démarre immédiatement et affiche :
- **Sur votre ordinateur** : `http://localhost:8080`
- **Sur smartphone / tablette (Wi-Fi)** : `http://192.168.x.x:8080`
- **Exemple de e-Billet étudiant en ligne** : `http://localhost:8080/ticket?id=1001`

Toutes les modifications et pointages sont enregistrés de façon permanente dans la base **SQLite** `upssa.db`.

---

## 🗄️ Base de Données SQL (`upssa.db`)

Le module `database.py` gère la persistance relationnelle avec schéma SQL strict, clés primaires et index d'optimisation :

1. **Table `students`** :
   - `id` (Clé primaire unique à 4 chiffres : `1001` à `1309`)
   - `name`, `email`, `phone`, `phone_wa` (numéro normalisé international pour WhatsApp)
   - `pole` (Santé, Sciences, Audit), `year` (1ère à 4ème année)
   - `gala` (0/1), `teambuilding` (0/1), `transport` (0/1)
   - `qr_data`, `qr_file`, `pass_file`
   - `whatsapp_status` (`pending` ou `sent`), `whatsapp_sent_at`
   - `attended` (0/1), `scanned_at`, `scanned_time`
2. **Table `scans`** :
   - Historique horodaté de chaque tentative de scan, contrôle anti-doublon et identification de l'appareil.
3. **Table `whatsapp_logs`** :
   - Journal des envois de messages avec aperçu et horodatage.

---

## 🎟️ Génération des QR Codes & Cartes d'Accès Officielles

Le script `qr_generator.py` génère automatiquement :
1. **309 QR Codes PNG bruts** dans le dossier `qrcodes/` (haute résolution, contraste parfait, module ISO/IEC 18004).
2. **309 Pass Digitaux Officiels** dans le dossier `passes/` :
   - Charte graphique UPSSA (Bleu Nuit `#0c2340` et Or festif).
   - En-tête : *UNIVERSITÉ PRIVÉE DE SANTÉ SOUSS ALMASSIRA — UPSSA ONBOARD 2026*.
   - Nom et prénom de l'étudiant, pôle d'études et année.
   - Badges d'accès : Gala, Team Building, Transport UPSSA Bus.
   - Grand QR Code scannable au centre avec code d'accès unique.
   - Consignes d'arrivée et mention obligatoire.

Pour regénérer tous les fichiers à tout moment :
```bash
python3 qr_generator.py
```

---

## 📲 Envoi du Message WhatsApp avec QR Code à Toute la Liste

Le message officiel conforme à vos spécifications :
```
🎉 UPSSA ONBOARD | CONFIRMATION OFFICIELLE

Cher(e) {Nom},

Nous avons le plaisir de vous confirmer votre inscription à la journée UPSSA ONBOARD – Team Building & Soirée, qui se tiendra mercredi 18 novembre 2026, au Hyatt Place Taghazout !** 🎉

✨ Une journée exceptionnelle vous attend, entre challenges, esprit d'équipe, rencontres et ambiance festive !

🎟️ Votre QR Code personnel est joint à ce message. Il devra obligatoirement être présenté et scanné à votre arrivée pour accéder à l'événement.
(Code d'accès : {id})

⚠️ Important : Votre inscription est valable pour l'ensemble du programme (Team Building + Soirée). L'accès uniquement à la soirée ne sera pas autorisé.

🚌 Transport UPSSA : Rendez-vous à 11h30 au campus pour un départ à 12h précises, pour les étudiants ayant réservé le transport.

🔗 Lien direct vers votre e-Billet & QR Code :
http://.../ticket?id={id}

Nous comptons sur votre présence et votre ponctualité pour faire de cette journée un moment inoubliable !

See you 🚀

UPSSA Student Life
```

### Méthode A : Depuis l'Interface Web (Recommandé & 1-Clic)
1. Ouvrez `http://localhost:8080` et cliquez sur l'onglet **📲 Envoi WhatsApp**.
2. **Mode Défilement Express (1 par 1)** :
   - Le bandeau supérieur affiche automatiquement l'étudiant suivant en attente.
   - Cliquez sur **« 📲 Ouvrir WhatsApp & Marquer Envoyé ➔ »** : la conversation s'ouvre dans WhatsApp Web avec le message pré-rempli, et son statut passe instantanément à `✓ Envoyé` dans la base SQL !
   - Glissez l'image du QR Code / Pass affichée sur la vignette directement dans la conversation WhatsApp.
3. **Tableau de bord de diffusion** :
   - Recherche instantanée par nom ou numéro.
   - Filtres : *En attente*, *Déjà envoyés*, *Avec transport*.
   - Bouton de prévisualisation du message formaté (💬).

### Méthode B : Envoi Assisté en Ligne de Commande
Lancez l'outil interactif dans le terminal :
```bash
python3 send_whatsapp_automation.py --interactive
```
Le script ouvre WhatsApp Web pour chaque étudiant de la liste un par un et enregistre la validation dans SQLite.

### Méthode C : Export pour Envoi en Masse
Pour utiliser un outil de diffusion en masse (ex: WhatsApp Business API, broadcast tool) :
```bash
python3 send_whatsapp_automation.py --export
```
Deux fichiers sont générés :
- `whatsapp_dispatch_list.csv` : Tableau complet avec les 309 étudiants, leurs numéros normalisés (+212...), les liens `wa.me` directs, le chemin des fichiers QR code et le message pré-formaté.
- `contacts_upssa_onboard.vcf` : Fichier de carnet d'adresses standard permettant d'importer les 309 contacts en 1 clic sur votre téléphone ou compte Google/Apple Contacts (nommés `UPSSA - [Nom]`).

---

## 📷 Double Mode de Pointage & Contrôle d'Accès en Direct

L'onglet principal de pointage propose **deux méthodes instantanées au choix** :
1. **Saisie Manuelle Ultra-Rapide (Code à 4 chiffres)** :
   - Champ de saisie grand format avec focus automatique permanent.
   - Validation instantanée automatique dès que les 4 chiffres sont tapés (ex: `1001`), ou en appuyant sur <kbd>Entrée</kbd>.
   - Clavier tactile / Pavé numérique intégré pour une utilisation fluide sur smartphone ou tablette.
   - Accepte également la saisie par prénom, nom ou téléphone.
2. **Scanner de Caméra QR Code en Direct** :
   - Reconnaissance instantanée via caméra avant / arrière avec visée laser.
   - Glisser-déposer d'une image ou capture d'écran de QR code reçue sur WhatsApp.
   - Compatible douchette laser code-barres / QR Code USB.
3. **Contrôle Anti-Doublons & Traçabilité** :
   - Si un étudiant est pointé une 2ème fois, alerte sonore et affichage orange avec l'heure exacte du premier passage (`Déjà pointé à 09:14:22`).
   - Synchronisation SQLite multi-postes : Plusieurs organisateurs peuvent pointer simultanément aux portes d'entrée avec leurs téléphones connectés au Wi-Fi.

---

## 📁 Structure du Projet

```
upssa-qr-presence/
├── upssa.db                      # Base de données relationnelle SQLite
├── database.py                   # Moteur SQL, tables, synchronisation & requêtes
├── qr_generator.py               # Générateur de QR Codes & Pass Digitaux PNG
├── whatsapp_manager.py           # Formatage des messages, liens wa.me et exports
├── send_whatsapp_automation.py   # Script CLI d'envoi et de suivi WhatsApp
├── start_server.py               # Serveur HTTP avec API REST connectée à SQLite
├── start.sh                      # Script de lancement en 1 clic
├── ticket.html                   # Page Web mobile du e-Billet étudiant avec QR Code
├── index.html                    # Application principale (Scanner + Liste + WhatsApp + Stats)
├── qrcodes/                      # 309 QR Codes PNG individuels (haute résolution)
├── passes/                       # 309 Pass Digitaux VIP UPSSA PNG avec badges et QR
├── whatsapp_dispatch_list.csv    # Export CSV prêt pour envoi en masse WhatsApp
├── contacts_upssa_onboard.vcf    # Carnet de contacts vCard des 309 étudiants
├── css/style.css                 # Styles de l'interface & de la section WhatsApp
├── js/app.js                     # Logique applicative, API REST & audio
├── js/data.js                    # Données de secours initiales
├── raw_data.csv                  # Données brutes sources
└── students.json                 # Données JSON des 309 inscrits
```
