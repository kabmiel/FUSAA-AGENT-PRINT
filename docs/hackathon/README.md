# FUSAA Agent — kit Hackathon

Ce dossier contient les visuels réels de démonstration de l’application.

## Parcours de la vidéo

1. Vue d’ensemble : atelier, production et accès Facturation.
2. Tableau de bord Facturation avec les cartes liquid glass et les compteurs.
3. Documents : types de document, prévisualisation et suivi des factures.
4. Concurrence : choix d’un autre entête, marge +5 / +10 / +15 % ou personnalisée et estimation instantanée.
5. Génération animée, puis ouverture du brouillon devis pour vérification avant impression ou paiement.

La vidéo enregistrée est `media/fusaa-hackathon-demo.webm`. Les captures `01` à `06` suivent exactement ce parcours.
Le conducteur de la présentation de trois minutes se trouve dans
[`VIDEO_3_MINUTES.md`](VIDEO_3_MINUTES.md).

## Livrables attendus

- `media/01-vue-ensemble.png` — vue générale de l’atelier.
- `media/02-facturation-tableau-de-bord.png` — badges et compteurs Facturation.
- `media/03-documents-facturation.png` — choix du type de document et liste des documents.
- `media/04-concurrence-parametres.png` — nouvel entête et marge concurrence.
- `media/05-generation-animee.png` — animation de traitement pendant la génération.
- `media/06-brouillon-concurrence.png` — devis brouillon ouvert pour contrôle.
- `media/fusaa-hackathon-demo.webm` — vidéo réelle du parcours ci-dessus.

## Produire les visuels en local

Les commandes utilisent une base de démonstration séparée et ne touchent pas à `backend/fusaa.db`.

```powershell
$project = (Get-Location).Path.Replace('\\', '/')
$env:DATABASE_URL = "sqlite:///$project/runtime/hackathon-demo.db"
$env:STORAGE_DIR = "$project/runtime/hackathon-storage"
Push-Location backend
python -m alembic upgrade head
Pop-Location
python scripts/seed_hackathon_demo.py
Push-Location backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Dans un second terminal :

```powershell
python scripts/capture_hackathon_demo.py
```

La capture ouvre automatiquement `http://127.0.0.1:8765/admin` : la boutique
publique à la racine n’est pas utilisée pour la vidéo d’administration.

Compte local de démonstration : `demo@fusaa-agent.com` / `FusaaDemo2026!`.

Lancez la capture seulement après le message Uvicorn indiquant que le serveur
est prêt. Les fichiers sont enregistrés dans `docs/hackathon/media/`. Le
script ne publie rien sur Render et ne modifie pas la base principale.

## Vérification avant dépôt

1. Vérifier que les six PNG et la vidéo WebM existent dans `media/`.
2. Ouvrir la vidéo : elle doit montrer la marge de concurrence à +10 % et le brouillon généré.
3. Ne jamais déposer `runtime/hackathon-demo.db` ou les jetons de connexion : ce sont uniquement des données locales de démonstration.

## Texte de présentation (environ 60 secondes)

> FUSAA Agent relie la boutique, l’atelier d’impression et la facturation dans une même application. L’équipe pilote les commandes, les produits, les paiements et les documents depuis une interface adaptée au mobile comme au desktop. La facturation utilise les entêtes et les styles importés de l’ancienne application Boulangerie. Une facture peut être transformée en devis concurrence : on sélectionne une autre entreprise, on choisit la marge et FUSAA recalcule chaque ligne tout en conservant le client, les produits et la trace du document original. Les actions importantes affichent une animation de traitement et chaque document reste prévisualisable avant impression.
