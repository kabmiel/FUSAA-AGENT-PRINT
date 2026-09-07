# Mise en service FUSAA INFORMATIQUE

Cette recette couvre le serveur Render, l'agent sur le PC FUSAA et l'interface web/mobile. Elle évite de démarrer deux agents ou d'imprimer deux fois un même travail.

## 1. Serveur Render

Dans le service Web Render, utilisez la racine `backend`, la commande de build `pip install -r requirements.txt` et la commande de démarrage :

```text
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Le contrôle de santé est `/readyz`. Renseignez les variables de `render.env` dans Render, sans jamais envoyer ce fichier dans Git. Une réponse HTTP 200 sur `https://fusaa-agent-print.onrender.com/readyz` confirme que l'API est prête.

## 2. PC FUSAA : agent d'impression

Installez Python 3.11 puis, dans PowerShell, placez-vous **dans** le dossier `local-agent` du projet :

```powershell
cd "C:\FUSAA-AGENT-PRINT-main\FUSAA-AGENT-PRINT-main\local-agent"
py -3.11 -m pip install -e ".[windows]"
py -3.11 -m fusaa_agent.main
```

Le premier lancement demande un jeton d'enrôlement. Créez-le depuis FUSAA dans l'atelier `FUSAA INFORMATIQUE`, puis collez sa valeur exacte dans le fichier `.env` unique à la racine du projet, par exemple :

```text
BACKEND_URL=https://fusaa-agent-print.onrender.com
ENROLLMENT_TOKEN=le_jeton_juste_genere
```

Après le premier enrôlement réussi, l'état de l'agent est conservé dans `agent-state.json`. Retirez alors `ENROLLMENT_TOKEN` du `.env`. Si le message « Another FUSAA agent already uses this state file » apparaît, l'agent fonctionne déjà : ne relancez pas une seconde copie.

Pour le démarrage automatique à chaque connexion Windows, à la racine du projet :

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Install-Autostart.ps1
```

Le lendemain, aucune commande manuelle n'est requise si l'utilisateur Windows ouvre sa session. Pour vérifier :

```powershell
py -3.11 .\scripts\windows_runtime.py health
```

## 3. Recette métier finale

1. Ouvrir FUSAA, se connecter et vérifier que l'atelier affiché est `FUSAA INFORMATIQUE`.
2. Vérifier que l'agent et l'imprimante voulue sont `ONLINE`.
3. Envoyer un PDF d'une page, puis vérifier progression, aperçu et réglages dans la popup glass.
4. Préparer puis confirmer l'impression. Le travail doit passer par les badges `Fichier`, `Inspection`, `Préparation`, `Impression`, `Terminé`.
5. Vérifier la feuille imprimée. Ensuite seulement, cliquer sur `Confirmer la fin du travail` : le travail quitte la liste active mais reste dans l'historique.
6. Faire un test d'un format non directement imprimable : il doit être accepté et clairement indiqué comme à préparer/conversion, sans échec silencieux.
7. Tester une commande publique : devis, validation manuelle du paiement, production, reçu, archivage et export CSV.
8. Lancer `py -3.11 .\scripts\windows_runtime.py backup`, puis vérifier le dernier état dans `État du système`.

## 4. En cas de problème

- `401 Unauthorized` pendant l'enrôlement : le jeton est erroné, expiré ou contient le texte d'exemple. Générez-en un nouveau.
- `500` sur les commandes : consulter les logs Render, puis l'état agent. Ne confirmez pas à nouveau tant que l'état du travail n'est pas clair.
- Pilote qui refuse les réglages : sélectionner le format/couleur proposés par l'imprimante et relancer depuis le badge. Une erreur ambiguë ne déclenche jamais une réimpression automatique.
- Agent déjà lancé : ne supprimez pas `agent-state.json` et ne forcez pas un second lancement. Vérifiez le processus ou reconnectez la session Windows.

Pour revenir à une version antérieure du serveur, utilisez le déploiement précédent dans Render. Les sauvegardes locales se restaurent uniquement vers un nouveau dossier ; voir `WINDOWS_AUTONOMY.md`.
