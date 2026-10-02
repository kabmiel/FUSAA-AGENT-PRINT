# Comptes clients à crédit

Dans **Facturation > Comptes crédit**, enregistrer un nouvel achat avec le même catalogue Boutique + Facturation et les mêmes entêtes que les factures ordinaires. Sélectionner un client réel (ou le créer avec le popup Client). L'acompte est facultatif.

Un nouvel achat s'ajoute au même compte. « Rembourser » répartit le montant sur les achats les plus anciens ; « Tout solder » remplit le montant du solde. Les comptes soldés quittent la liste Débiteurs et apparaissent dans Archives / soldés. Un nouvel achat les réactive, sans effacer l'historique ni la fiche client.

L'état PDF reprend l'entête choisi, la date à côté de chaque désignation, les produits dans leur ordre, les remboursements et le solde en chiffres et en lettres. Il contient tout l'historique, même quand la vue écran est paginée.

## Sécurité et limites

- Écriture réservée aux administrateurs de l'organisation ; lecture réservée à ses membres.
- Achats et remboursements sont enregistrés ensemble avec les soldes et paiements dans une transaction.
- Identifiant de demande unique contre les doubles enregistrements ; une demande réutilisée avec un contenu différent est refusée.
- Remboursements supérieurs au solde refusés. Les achats crédit enregistrés ne sont pas modifiables depuis l'éditeur ordinaire ; les corrections comptables nécessiteront des écritures d'annulation dédiées, pas une suppression d'historique.
- Les anciennes factures ordinaires impayées ne sont pas converties automatiquement en crédits : leur solde ne constitue pas une autorisation de vente à crédit.
- Liste paginée, produits déjà chargés par le compositeur existant, requêtes groupées pour l'historique. Aucun appel IA pour les calculs.

## Démarrage local et migration

Depuis PowerShell à la racine du projet :

```powershell
.\scripts\start-local.ps1
```

Le script applique les migrations sur la base SQLite locale avant de démarrer. La migration `0024_customer_credit_accounts` crée deux tables, sans modifier les clients ni les anciennes factures. Sauvegarder la base avant une migration réelle. Aucun déploiement Render n'est effectué par cette modification.

Contrôles ciblés, sur base en mémoire uniquement :

```powershell
py -3.11 -m pytest tests/test_credit_accounts.py -q
```
