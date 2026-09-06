# AI boundary

FUSAA utilise Ollama localement par défaut. Aucune clé API, aucun compte cloud et aucune transmission de messages vers un service externe ne sont nécessaires. Le modèle par défaut est `qwen2.5:0.5b`, servi par `http://127.0.0.1:11434` sur le même PC.

La configuration locale est :

```text
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:0.5b
```

Si Ollama est arrêté, indisponible ou produit une réponse invalide, FUSAA bascule automatiquement vers le routeur déterministe intégré. Il n'y a ni erreur bloquante ni appel réseau externe.

Le modèle ne pilote jamais l'ordinateur : il ne peut proposer que des outils autorisés. L'API vérifie chaque outil et demande une confirmation explicite avant toute préparation, annulation ou impression.

Tools are divided into `SAFE`, `CONFIRMATION_REQUIRED` and `CRITICAL`. Reading jobs, documents and printers is safe. Preparing a file requires confirmation. Printing and cancellation are critical and require a second explicit call with `confirmed: true`. Every understanding request and execution is recorded in `AuditLog`.

Allowed capabilities include `list_print_jobs`, document search/inspection, printer status, deterministic printer recommendation, agent/workshop status, preparation, print request, cancellation and ignore. Recommendation consults only synchronized printer capabilities; it never invents machine capabilities.

The AI layer cannot import or call `cmd.exe`, PowerShell, `subprocess`, `os.system`, dynamically generated Python, or the Windows print API. Physical actions remain an API command routed through the Local Agent.
