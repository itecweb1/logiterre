╔══════════════════════════════════════════════════════════════════════════╗
║          LOGITERRE 2026 — Système d'envoi d'invitations                  ║
║                    Guide d'utilisation complet                           ║
╚══════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STRUCTURE DU PROJET
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  logiterre-expo/
  ├── envoyer.py            ← ⭐ SCRIPT PRINCIPAL — à utiliser au quotidien
  ├── send_emails.py        ← Moteur SMTP Hostinger (ne pas modifier)
  ├── send_prudent.py       ← Envoi par lots avec suivi (avancé)
  ├── send_umf.py           ← Envoi liste UMF Marseille (avancé)
  ├── academies_clean.py    ← Base de données des institutions
  ├── email_log.json        ← Journal de tous les envois (auto-généré)
  ├── PDF_ACADEMIES/        ← Dossier des PDFs générés
  ├── DOCX_TEMP_ACAD/       ← Modèles DOCX temporaires
  └── README.txt            ← Ce fichier

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  UTILISATION RAPIDE — envoyer.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ÉTAPE 1 — Ouvre le fichier envoyer.py dans un éditeur de texte

  ÉTAPE 2 — Modifie la liste MY_LIST en haut du fichier :

      MY_LIST = [
          ("Nom complet de l'institution",   "email@domaine.com"),
          ("Deuxième institution",           "contact@exemple.org"),
          ("Troisième institution",          "info@autre.net"),
          # ... autant de lignes que tu veux
      ]

  ÉTAPE 3 — Lance le script dans le terminal :

      python3 envoyer.py

  ÉTAPE 4 — Confirme en tapant "oui" quand demandé

  C'est tout ! Le script :
    ✓ Génère automatiquement le PDF personnalisé pour chaque institution
    ✓ Envoie l'email avec le PDF en pièce jointe
    ✓ Attend 2 minutes entre chaque envoi (protection anti-spam)
    ✓ Affiche un résumé à la fin

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CONFIGURATION SMTP (send_emails.py)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Serveur SMTP  : smtp.hostinger.com (port 465, SSL)
  Expéditeur    : a.zahraoui@logiterre-expo.com
  Reply-To      : sg@logiterre-expo.com
  CC automatique: contact@uaotlafrica.com, sg@logiterre-expo.com

  ⚠️  Si Hostinger bloque : aller sur hPanel → Email → Réactiver le compte

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CONSEILS ANTI-SPAM (IMPORTANT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ✅ Maximum 25-30 emails par jour
  ✅ Délai minimum 2 minutes entre chaque email
  ✅ Attendre 12 heures entre deux sessions
  ❌ Ne jamais envoyer plus de 50 emails en une session
  ❌ Ne jamais réduire le délai en dessous de 120 secondes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SUIVI DE CAMPAGNE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Voir le statut des envois :
      python3 send_prudent.py --status
      python3 send_umf.py --status

  Voir le plan complet :
      python3 send_prudent.py --plan
      python3 send_umf.py --plan

  Le fichier email_log.json garde la trace de TOUS les envois.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  RÉSULTATS DE LA CAMPAGNE 2026
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📧 395 emails envoyés (21-31 mai 2026)
  🌍 ~40 pays couverts
  🏛️  ~382 organisations contactées sur 5 continents

  Répartition :
    - Batch 1 : 68  institutions académiques originales
    - Batch 2 : 39  institutions prestige (Harvard, Oxford, IMO...)
    - Batch 3 : 35  USA / Europe / Australie
    - Batch 4 : 29  Nouvelles institutions mondiales
    - Batch 5 : 71  Fédérations & Associations mondiales
    - UMF     : 150 Entreprises maritime Marseille-Fos

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PRÉREQUIS TECHNIQUES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  - Python 3.10+ (testé avec Python 3.13)
  - LibreOffice (pour conversion DOCX → PDF)
  - Connexion internet
  - Compte Hostinger SMTP actif

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SUPPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Contact : sg@logiterre-expo.com
  WhatsApp : +212 673 642 4246

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
