# PWA et notifications

La PWA met en cache uniquement son interface. Les réponses API authentifiées, les documents et les aperçus ne sont jamais mis en cache par le service worker.

Un upload lancé sans réseau est conservé dans IndexedDB sur le smartphone puis synchronisé automatiquement dès que le réseau revient. Les confirmations physiques d’impression ne sont volontairement jamais mises en attente hors ligne : l’utilisateur doit être connecté pour les confirmer.

Web Push exige HTTPS (ou `localhost`) et une paire VAPID. Générez-la avant la production puis renseignez ces variables hors Git :

```powershell
python -m py_vapid --application-server-key
```

Configurez `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` et `VAPID_CLAIM_EMAIL` dans l’environnement du backend. L’utilisateur peut ensuite choisir « Activer les notifications » dans la PWA.
