# APK Android FUSAA Service

L'APK FUSAA ouvre l'interface officielle hébergée sur Render dans une application Android, avec son stockage de session isolé. Les travaux, leurs droits et l'impression restent gérés par le serveur FUSAA et l'agent Windows : l'APK ne peut jamais lancer une impression physique sans cet agent.

## Construire l'APK

Sur le PC de développement avec Android Studio, Java 17 et le SDK Android installés, ouvrez PowerShell dans le dossier `mobile` :

```powershell
npm.cmd install
npm.cmd run android:add
npm.cmd run android:sync
npm.cmd run android:apk
```

L'APK de test est alors ici :

```text
mobile\android\app\build\outputs\apk\debug\app-debug.apk
```

Installez ce fichier sur Android en autorisant temporairement les installations depuis votre gestionnaire de fichiers, puis désactivez cette autorisation. Pour une publication Play Store, ouvrez le projet avec `npm.cmd run android:open`, créez une clé de signature dans Android Studio puis générez un APK/AAB **signé**.

## Mise à jour et sécurité

- L'application mobile lit l'interface à `https://fusaa-agent-print.onrender.com` : une mise à jour web est visible sans réinstaller l'APK.
- Ne modifiez pas cette adresse vers un serveur inconnu. Toute modification de `mobile/capacitor.config.ts` demande une nouvelle compilation et une distribution du nouvel APK.
- L'APK exige Internet ; les données d'authentification restent dans le stockage isolé de l'application Android.
- Utilisez toujours HTTPS. Aucun mot de passe, jeton d'enrôlement ou clé Supabase ne doit être ajouté dans le projet mobile.

## Recette mobile

1. Installer l'APK et vérifier l'écran sombre FUSAA au lancement.
2. Se connecter avec un compte existant.
3. Ouvrir un travail, consulter les badges de progression et vérifier la mise en page mobile.
4. Envoyer un petit PDF, choisir l'imprimante synchronisée et confirmer l'impression.
5. Vérifier sur le PC FUSAA que l'agent a reçu puis terminé la commande.
