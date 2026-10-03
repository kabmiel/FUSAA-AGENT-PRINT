# Accès, activation et récupération FUSAA

Les nouveaux mots de passe acceptent 4 à 128 caractères, sans règle de complexité.
Un mot de passe long et unique est néanmoins recommandé. Les mots de passe sont
toujours hachés ; ils ne sont ni affichés ni conservés en clair.

## Démarrage local après cette mise à jour

Arrêtez l'ancien serveur avec Ctrl+C. Depuis PowerShell, dans le dossier FUSAA AGENT :

```powershell
.\scripts\start-local.ps1
```

Ce script applique notamment la migration `0025_auth_recovery_links` sur la base
locale avant de démarrer l'application. Aucun déploiement Render n'est effectué.

## Administrateur déjà connecté

Dans **Settings → Mot de passe de mon compte**, saisissez le mot de passe actuel
et confirmez le nouveau. La session courante est conservée avec un nouveau jeton ;
les anciens jetons ne donnent plus accès aux API ni aux notifications privées.

## Administrateur ayant oublié son mot de passe : récupération locale

L'application doit être lancée. Dans une deuxième fenêtre PowerShell, ouverte
dans le dossier FUSAA AGENT :

```powershell
.\scripts\recover-admin.ps1
```

Saisissez l'e-mail du compte administrateur existant, puis ouvrez le lien privé
affiché. Choisissez et confirmez le nouveau mot de passe. Le lien dure **15 minutes**
et s'utilise **une seule fois**. Ne le partagez pas. Créer un nouveau lien annule le
précédent, mais ne change pas le mot de passe avant sa validation.

La commande utilise explicitement `backend/fusaa.db`, jamais la base distante de
votre `.env`. Elle ne crée pas de compte et refuse un compte inactif ou non administrateur.
Elle ne demande aucun service SMTP. Toute personne ayant accès à cette console et
à la base peut récupérer un compte administrateur : protégez l'accès à votre PC.

## Compte hébergé sur Render

Une base locale ne peut pas récupérer un compte dans une autre base. Depuis la
console **autorisée du serveur**, dans le dossier `backend`, après les migrations :

```sh
python -m app.recover_admin --server --email votre-adresse@example.com --base-url https://votre-application.onrender.com
```

L'option `--server` utilise la base configurée de cet environnement. Ne l'exécutez
pas sur votre PC avec des identifiants de production par inadvertance. Si votre
hébergement n'offre pas de console, une intervention autorisée sur le serveur
sera nécessaire. Rien n'est envoyé automatiquement sur Render.

## Activation et autres comptes

Dans **Équipe**, ajouter un membre produit un lien privé d'activation, valable
72 heures. Le destinataire crée son mot de passe sans perdre son rôle dans l'atelier.
Pour les anciennes invitations ne contenant qu'un e-mail, utilisez **Renvoyer le
lien** : ces anciens liens ne constituent pas une preuve d'identité suffisante.

Le bouton **Réinitialiser** d'un membre actif exige la confirmation du mot de passe
administrateur et crée un lien privé de 15 minutes. Un administrateur ne peut pas
réinitialiser un compte appartenant à une autre organisation ; seul le propriétaire
peut le faire pour un autre administrateur de sa propre organisation.

Les secrets de lien sont stockés hachés en base, transmis dans le fragment `#token`
(pas dans les journaux d'accès HTTP), vérifiés puis consommés atomiquement. Aucun
utilisateur anonyme ne peut récupérer un compte en fournissant seulement son e-mail.
