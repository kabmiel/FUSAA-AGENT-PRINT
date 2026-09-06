# Correctifs et phase 14 — 5 septembre 2026

## Corrections vérifiées

- Même périmètre atelier dans les listes HTTP et les outils IA. Le rôle VIEWER ne peut ni préparer, confirmer, annuler, router ni transformer un document. Les accès aux fichiers, aperçus, audits et événements temps réel sont filtrés.
- Les requêtes de l'assistant utilisent des jointures explicites ; les dates SQLite sont normalisées en UTC pour la supervision.
- Le routage remet le travail en attente de préparation et retire l'ancienne imprimante.
- Les champs d'impression sont validés côté API. L'agent conserve l'extension du fichier et utilise un rendu GDI. Le pilote est configuré par travail ; les pages et exemplaires sont rendus explicitement.
- L'intention d'envoi est persistée avant la première action physique. Les résultats acquittés restent en mémoire durable. Un résultat ambigu ne déclenche pas de nouvelle impression. Un travail déjà envoyé n'est pas remis en attente par expiration du bail.
- Les noms de fichiers et d'imprimantes sont échappés dans l'interface. La sélection de travail reste stable après actualisation. La file hors ligne utilise de nouvelles transactions IndexedDB, un propriétaire de session et un identifiant de téléchargement pour éviter les répétitions lors des reprises.
- Ollama accepte uniquement une adresse locale et ne suit ni proxy ni redirection. Une réponse conversationnelle en français est produite après consultation des outils autorisés ; les actions gardent une confirmation séparée.

## Validation

28 tests automatisés passent, dont des régressions sur les droits, les notifications, les dates, le rendu simulé, la reprise après interruption, les baux de commandes, la restauration des sauvegardes et le masquage des jetons dans les nouveaux journaux.

Le contrôle des pilotes, sans StartDoc ni sortie papier, accepte A4/portrait/monochrome sur les pilotes KONICA MINOLTA, HP M227, HP M426, EPSON L3250 et Canon iR2625/2630 installés. Ce contrôle ne prouve pas la disponibilité physique de chaque imprimante.

Le test HTTP réel confirme la disponibilité des imprimantes, des travaux, du tableau de bord et de l'état système. Ollama répond à une salutation en français.

Une sauvegarde réelle du projet a été vérifiée puis restaurée dans un nouveau dossier runtime/restore-check-20260905, sans écraser les données actives.

Le superviseur a relancé l'API après un arrêt volontaire de son processus. Le raccourci de démarrage Windows pointe vers le superviseur installé ; un second lancement est arrêté par le verrou d'instance.

## Périmètre restant

WhatsApp automatique reste désactivé conformément au choix sans identifiants externes. Il ne s'agit pas d'une intégration opérationnelle de téléchargement des médias. Utiliser l'import manuel des fichiers.

Une impression physique avec document et imprimante choisis reste nécessaire avant un usage régulier. Les pilotes Windows peuvent signaler imparfaitement la fin d'une impression ; une sortie du spouleur sans confirmation explicite reste à vérifier.

Le démarrage automatique se fait à la connexion de l'utilisateur Windows ; les sauvegardes locales ne protègent pas contre une panne du même disque. Voir WINDOWS_AUTONOMY.md.
