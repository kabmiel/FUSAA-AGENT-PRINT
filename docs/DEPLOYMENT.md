# Deployment checklist

1. Install Docker Engine on the server and terminate TLS at a reverse proxy (Caddy, Nginx or Traefik).
2. Renseignez le fichier `.env` unique à la racine pour le développement local. Ne le versionnez jamais. En production Render, renseignez ces variables dans le tableau de bord Render, jamais dans Git.

## Images Boutique FUSAA (Cloudinary)

Pour permettre l’import direct des images produits depuis l’administration FUSAA, ajoutez ces trois variables dans `.env` local et dans les variables Render :

```env
CLOUDINARY_CLOUD_NAME=votre_cloud_name
CLOUDINARY_API_KEY=votre_api_key
CLOUDINARY_API_SECRET=votre_api_secret
```

Ne mettez jamais ces valeurs dans Git. Sans elles, la boutique fonctionne toujours avec des URL d’images saisies manuellement ; seul le bouton d’import Cloudinary reste désactivé côté serveur avec un message explicite.

## Import initial de l’ancien catalogue Shopinverse

Après avoir créé l’organisation FUSAA et appliqué les migrations, utilisez l’outil inclus pour copier les catégories, produits, prix FCFA et stocks depuis l’ancien projet Django :

```powershell
py -3.11 scripts/import_shopinverse.py --source "C:\Users\LENOVO\Desktop\PROJET EN COURS\shopinverse_django\db.sqlite3" --organization-id "VOTRE_ID_ORGANISATION"
```

Les anciens comptes et anciennes commandes ne sont volontairement pas importés : ils appartiennent au modèle d’authentification Django et ne doivent pas être transférés sans consentement. Les nouvelles commandes passent par Boutique FUSAA et sont gérées dans le même admin que l’impression.
3. Use PostgreSQL; SQLite is rejected in production mode.
4. Start with `docker compose up --build -d`. The API waits for PostgreSQL and runs Alembic migrations before serving traffic.
5. Check `GET /healthz` and `GET /readyz` through the reverse proxy.
6. Back up the PostgreSQL volume and document storage daily. Test restoration before relying on backups.
7. Configure VAPID keys and HTTPS before enabling Web Push.
8. Enroll each Windows agent only after confirming the API certificate and its workshop.

## Render gratuit

- Root Directory : `backend`
- Build Command : `pip install .`
- Start Command : `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health Check Path : `/readyz`
- Utilisez PostgreSQL/Supabase pour `DATABASE_URL`.
- Le disque local gratuit est éphémère : `STORAGE_DIR=/tmp/fusaa-storage` convient aux essais, mais les documents doivent être sauvegardés ailleurs avant une mise en veille ou un redéploiement.
- Définissez des valeurs explicites pour `CORS_ORIGINS`, `TRUSTED_HOSTS`, `JWT_SECRET`, `SINGLE_WORKSHOP_ID` et `SINGLE_WORKSHOP_NAME`.

The production backend disables interactive API documentation by default. Keep `.env`, agent state files, VAPID/private keys and database backups outside Git.
