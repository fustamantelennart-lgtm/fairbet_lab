## Intento Fallido 1: Conflicto por persistencia de `manage.py` residual
* **Fecha:** 19/05/2026
* **Contexto:** Re-intento de inicialización de Django tras eliminar el directorio `config`.
* **Error presentado:** `CommandError: /app/manage.py already exists. Overlaying a project into an existing directory won't replace conflicting files.`
* **Causa raíz:** El comando anterior generó exitosamente el archivo `manage.py` en la raíz antes de fallar por el conflicto de directorios. El framework bloqueó la nueva ejecución al detectar el archivo residual.
* **Solución aplicada:** Remover manualmente el archivo `manage.py` residual de la raíz del espacio de trabajo y ejecutar el comando por segunda vez sobre un directorio completamente limpio.