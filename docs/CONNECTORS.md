# Connecteurs

Tous les connecteurs normalisent leurs entrées en `IncomingDocument`, puis utilisent le même pipeline que l’upload mobile : stockage immuable, inspection, aperçu, `Document`, `PrintJob` en `WAITING_APPROVAL`, audit et événement temps réel.

## API Connector

Créez un connecteur depuis la PWA ou `POST /api/v1/connectors`. La réponse retourne une clé une seule fois ; le serveur conserve uniquement son hash. Envoyez ensuite un fichier :

```text
POST /api/v1/connectors/{connector_id}/incoming?external_id=source-unique-id
X-Connector-Key: <secret>
multipart/form-data: file
```

`external_id` rend la réception idempotente : une nouvelle tentative ne crée jamais deux impressions.

## Email

`EMAIL` utilise la même endpoint, avec `/email/incoming`, afin qu’un fournisseur de messagerie ou un futur lecteur IMAP puisse envoyer chaque pièce jointe normalisée. Il n’y a pas de lecture automatique de boîte aux lettres ni de secret d’e-mail stocké dans cette phase.

## WhatsApp Business officiel

FUSAA ne lit jamais WhatsApp Web dans Brave, les cookies du navigateur, les QR codes ni les conversations personnelles. L’intégration ne concerne que le compte WhatsApp Business que vous contrôlez dans Meta.

Créez un connecteur `WHATSAPP` depuis FUSAA. La clé affichée une seule fois est le **jeton de vérification webhook** à renseigner dans Meta. L’URL de vérification est :

```text
GET/POST /api/v1/connectors/{connector_id}/whatsapp/webhook
```

La réception `POST` accepte uniquement les notifications signées par Meta (`X-Hub-Signature-256`). Son activation nécessite `META_WHATSAPP_APP_SECRET` dans l’environnement du serveur. Il ne s’agit pas d’une clé d’IA et FUSAA n’en crée pas automatiquement.

Sans ce secret, le webhook refuse les messages. Avec le secret, FUSAA enregistre uniquement l’identifiant d’un document ou d’une image reçue, jamais le texte, le numéro ou les contacts. Le téléchargement réel du média depuis Meta reste volontairement désactivé : il exige un jeton Media API dédié et une décision explicite avant toute connexion externe.
