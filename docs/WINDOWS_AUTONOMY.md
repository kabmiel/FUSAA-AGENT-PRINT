# Phase 14 — fonctionnement local Windows

Le superviseur démarre à l'ouverture de session de l'utilisateur Windows. Ce n'est pas un service démarré avant connexion : l'agent utilise les imprimantes et pilotes de cet utilisateur.

Installation : lancer `scripts/Install-Autostart.ps1`. Le raccourci « FUSAA Service » dans le dossier Démarrage lance `pythonw.exe scripts/windows_runtime.py supervise`. Un verrou empêche les superviseurs multiples ; un second verrou protège l'agent. Les processus arrêtés sont relancés. Un processus bloqué mais encore vivant est signalé par le contrôle de santé, sans tuer une impression en cours.

L'API écoute uniquement sur 127.0.0.1:8000. Ollama est démarré localement si nécessaire. Aucune clé d'IA ou de Meta n'est requise pour cette installation. WhatsApp automatique reste désactivé.

## Contrôle et sauvegarde

```powershell
python scripts/windows_runtime.py health
python scripts/windows_runtime.py backup
python scripts/windows_runtime.py verify --snapshot "C:\chemin\vers\backups\instantane"
python scripts/windows_runtime.py restore --snapshot "C:\chemin\vers\backups\instantane" --destination "C:\chemin\nouveau-dossier-recuperation"
```

Chaque démarrage du superviseur et chaque nouveau jour déclenchent une sauvegarde locale. Elle contient une copie cohérente SQLite, les documents et aperçus, les configurations et l'état de l'agent. L'intégrité SQLite, les références de documents et les empreintes SHA-256 sont vérifiées. Les fichiers originaux sont immuables ; la copie du stockage peut inclure des fichiers plus récents que l'instantané de base, sans référence manquante.

La restauration écrit uniquement dans un nouveau dossier ; elle ne remplace jamais l'installation active. Avant un retour en service depuis une ancienne sauvegarde, les commandes d'impression encore en attente doivent être examinées manuellement : restaurer un ancien état de queue ne prouve pas qu'une impression n'a pas déjà eu lieu.

Les sauvegardes ne sont pas supprimées automatiquement. Surveillez l'espace disque et copiez-les régulièrement sur un autre support. Elles contiennent des secrets locaux : leur dossier doit être accessible uniquement à l'utilisateur et à SYSTEM. Le journal de supervision est borné ; les journaux des processus tournent à leur relancement.

L'écran « État du système » affiche le dernier contrôle. Le fichier `runtime/health.json` donne aussi les processus gérés. Pour désactiver le prochain démarrage, retirez uniquement le raccourci « FUSAA Service » du dossier Démarrage Windows ; cela ne stoppe pas les processus déjà actifs.

## Impression

Les PDF/images sont rendus vers GDI avec PyMuPDF/Pillow. Les pages et copies sont rendues explicitement ; format, orientation, couleur et recto-verso passent au pilote via DEVMODE. Un paramètre non supporté provoque un refus explicite. Le mode « format automatique » conserve le format du pilote. Les imprimantes à boîte de dialogue de fichier sont refusées.

L'intention d'envoi est enregistrée sur disque avant toute action. Une interruption ambiguë produit une erreur à vérifier, jamais une réimpression automatique. Les commandes acquittées restent mémorisées. La disparition d'un travail du spouleur n'est plus interprétée comme une preuve de réussite.

Le test physique sur votre imprimante reste nécessaire pour valider le pilote, le papier et le résultat réel.

Références du rendu Windows : [CreateDC](https://mhammond.github.io/pywin32/win32gui__CreateDC_meth.html), [StartDoc](https://mhammond.github.io/pywin32/win32print__StartDoc_meth.html), [Pillow ImageWin](https://pillow.readthedocs.io/en/stable/reference/ImageWin.html).
