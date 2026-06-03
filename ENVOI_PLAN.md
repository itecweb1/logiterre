# 📋 Plan d'envoi LOGITERRE 2026 — Optimisé Hostinger

## ⚠️ Avant tout : Réactiver votre compte Hostinger

1. Ouvrez l'email Hostinger qui dit "Email sending suspended"
2. Cliquez sur le bouton de réactivation
3. Changez votre mot de passe Hostinger si demandé
4. **IMPORTANT** : Si vous changez le mot de passe, mettez-le à jour dans `send_emails.py` ligne 38

## 🛡️ Configuration anti-spam

Le script utilise maintenant :
- ⏱️ **90 à 180 secondes** aléatoires entre chaque email (comportement humain)
- 🔄 **Reconnexion SMTP** entre chaque envoi (pas de longue session suspecte)
- 📧 **En-têtes pro** : Message-ID, Date, Reply-To, X-Mailer
- 🔁 **Retry automatique** en cas d'erreur transitoire
- 🛑 **Arrêt immédiat** si Hostinger bloque (préserve votre compte)

## 📅 Plan d'envoi étalé sur 3 jours

Hostinger surveille les comportements. Pour ne pas se faire bloquer, étalez :

### Jour 1 — Test puis 25 emails
```bash
cd /Users/ayb/Desktop/logiterre-expo

# 1) Test (envoie 1 email à VOUS-MÊME)
python3 send_emails.py --test

# 2) Vérifiez votre boîte mail
# Si tout est OK :

# 3) Premier batch de 25 (≈ 60-90 minutes)
python3 send_emails.py --batch 25 --yes
```

### Jour 2 — 25 emails suivants
```bash
python3 send_emails.py --batch 25 --yes
```

### Jour 3 — Les 21 derniers
```bash
python3 send_emails.py --resume --yes
```

## 🔍 Suivi des envois

- **Log JSON** : `/Users/ayb/Desktop/logiterre-expo/email_log.json`
- **Reprise** : `--resume` continue uniquement les non-envoyés
- **Vérifier le statut** :
```bash
python3 -c "import json; d=json.load(open('email_log.json')); print(f'Envoyés: {sum(1 for v in d.values() if v[\"status\"]==\"sent\")} / Échecs: {sum(1 for v in d.values() if v[\"status\"]==\"failed\")}')"
```

## 🆘 Si le compte se rebloque

1. Réactivez immédiatement via hPanel
2. Attendez **24h minimum** avant de relancer
3. Réduisez à 10-15 emails/jour
4. Vérifiez que SPF/DKIM/DMARC sont configurés pour `logiterre-expo.com`
5. Considérez Brevo (gratuit 300/jour) si problème persiste

## 📊 État des envois

Pour voir qui a été envoyé :
```bash
python3 -c "
import json
d = json.load(open('email_log.json'))
sent = [k for k,v in d.items() if v['status']=='sent']
failed = [k for k,v in d.items() if v['status']=='failed']
print(f'✓ Envoyés ({len(sent)}): {sent}')
print(f'✗ Échecs ({len(failed)}): {failed}')
"
```
