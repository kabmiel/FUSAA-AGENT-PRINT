# Extension Brave — alertes WhatsApp FUSAA

Cette extension relie uniquement WhatsApp Web ouvert dans Brave au serveur FUSAA qui tourne sur le même PC. Elle produit des alertes anonymes dans **Arrivées** lorsqu’un marqueur de message non lu ou une nouvelle bulle entrante est détecté.

Elle ne lit ni ne transmet le texte des messages, les contacts, numéros, fichiers, médias, cookies ou la session WhatsApp. Les données envoyées à `127.0.0.1:8000` sont uniquement :

- un identifiant d’événement aléatoire ;
- `MESSAGE` ou `UNREAD` ;
- un compteur sans contenu.

## Installer dans Brave

1. Ouvrez `brave://extensions`.
2. Activez le **Mode développeur** en haut à droite.
3. Cliquez sur **Charger l’extension non empaquetée**.
4. Sélectionnez le dossier `browser-extension` de ce projet.
5. Épinglez l’icône **FUSAA – alertes WhatsApp** dans la barre Brave.

## Associer l’extension

1. Démarrez FUSAA Service et connectez-vous sur `http://127.0.0.1:8000`.
2. Dans la vue **Arrivées**, créez un code de liaison pour l’atelier concerné. Un code dure dix minutes et ne peut être utilisé qu’une fois.
3. Cliquez sur l’icône FUSAA dans Brave, collez ce code et choisissez **Associer ce navigateur**.
4. Ouvrez `https://web.whatsapp.com/` dans Brave et gardez la page ouverte.

L’état de l’extension affiche si la page WhatsApp est détectée. Lorsqu’une nouvelle arrivée est signalée, ouvrez WhatsApp vous-même pour consulter le message ou télécharger son document, puis choisissez ce fichier dans FUSAA.

## Limites connues

WhatsApp modifie parfois son interface. L’extension utilise plusieurs marqueurs DOM sans lire leur contenu, mais une mise à jour de WhatsApp peut nécessiter l’ajout d’un marqueur. Les alertes sont indicatives : elles ne téléchargent pas automatiquement des pièces jointes et ne déclenchent jamais une impression.

## Retirer la liaison

Dans le popup de l’extension, cliquez sur **Dissocier**. Le code local est supprimé. Vous pouvez aussi révoquer la liaison depuis FUSAA.
