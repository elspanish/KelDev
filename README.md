# Plataforma Dev

Aplicación Streamlit para crear proyectos divididos en tareas, asignarlas por
compatibilidad de habilidades y completar las entregas cuando GitHub detecta el
merge de una Pull Request.

## Ejecutar localmente

1. Instala dependencias con `pip install -r requirements.txt`.
2. Copia `pcapp/.env.example` a `pcapp/.env` y configura URL/clave de Supabase y
   la clave de Google AI Studio (`GEMINI_API_KEY`).
3. Ejecuta desde la raíz del repositorio:

   ```sh
   streamlit run pcapp/main.py
   ```

La llamada a Gemini es opcional; sin su clave todavía se pueden crear y editar
las tareas manualmente.

## Preparar Supabase y GitHub

1. Enlaza el CLI de Supabase y ejecuta `supabase db push`. La migración única
   `supabase/migrations/20261013100000_launch_schema.sql` crea las tablas base
   si faltan y completa las tablas preexistentes:
   `project_modules.project_id` conserva el tipo `bigint` y su relación con
   `projects`, mientras que las asignaciones y revisiones reciben los campos y
   estados que usa el flujo de trabajo. Ejecuta el comando antes de iniciar la
   aplicación.
2. Despliega las funciones:
   `supabase functions deploy github-webhook` y
   `supabase functions deploy check-pull-request`.
3. Configura el secreto del webhook en Supabase:
   `supabase secrets set GITHUB_WEBHOOK_SECRET=<secreto-largo-aleatorio>`.
   La función usa además `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` del
   entorno de funciones. La clave service-role no debe ponerse en Streamlit ni
   en el repositorio.
4. Crea una GitHub App (o un webhook de repositorio) suscrita a eventos
   `Pull requests`; registra como URL
   `https://<project-ref>.supabase.co/functions/v1/github-webhook` y usa
   exactamente el mismo secreto del paso anterior. Para una GitHub App, limita
   el acceso a los repositorios que participarán y concede solo los permisos
   requeridos para recibir eventos de Pull Requests.
5. Crea una OAuth App de GitHub para el inicio de sesión y configura su
   `Client ID` y `Client Secret` en el proveedor GitHub de Supabase Auth.
   En GitHub, usa `https://<project-ref>.supabase.co/auth/v1/callback` como
   Authorization callback URL.
   Registra la URL pública de Streamlit como URL de redirección permitida en
   Supabase y configura `APP_URL` con esa misma URL al desplegar la aplicación.
6. Configura las variables `SUPABASE_URL`, `SUPABASE_KEY` y `GEMINI_API_KEY`
   como secretos/variables del entorno donde se ejecuta Streamlit. `GEMINI_API_KEY`
   se crea desde Google AI Studio. Opcionalmente configura `GEMINI_MODEL`.

El webhook verifica la firma HMAC de GitHub. En el flujo directo, la PR se
consulta al registrarla y el webhook detecta los cierres posteriores. En el
flujo por capas se asignan hasta dos revisiones independientes; si no hay
revisores disponibles o vencen sin reemplazo, la entrega se escala al creador
para evitar bloquear el trabajo. Después, el creador registra la PR final al
repositorio destino indicado en la tarea y la fusiona. Solo el merge confirmado
por GitHub completa la tarea y concede la puntuación configurada (por defecto,
5 × 100 puntos, una sola
vez). Los enlaces de PR directa y de PR final deben corresponder al repositorio
destino de la tarea.

## Matching y plazos

Para la primera versión, el matching es deliberadamente sencillo y explicable:
solo se muestran tareas con al menos una habilidad coincidente, se ordenan por
número de habilidades coincidentes y se asignan mediante una RPC transaccional.
Así se evita que dos colaboradores reclamen la misma tarea; si una asignación
vence, ese colaborador queda excluido de futuras asignaciones de esa tarea.
Cada colaborador puede tener una sola tarea o módulo de redacción activo a la
vez; la base de datos bloquea las asignaciones simultáneas de ambos tipos.
Las tareas pendientes son visibles para colaboradores autenticados; una vez
asignadas, solo las ve el colaborador asignado, el creador del proyecto y los
revisores designados.
No se pondera reputación inicialmente: evita sesgo contra usuarios nuevos y
mantiene el resultado fácil de depurar. Los dos revisores se seleccionan al
azar entre perfiles distintos del autor y del creador, priorizando coincidencia
de habilidades.

Al crear cada tarea se configuran límites de 1 a 720 horas para la asignación,
la revisión por pares y la revisión del creador/merge. La migración programa
`public.expire_task_workflows()` cada cinco minutos cuando `pg_cron` está
disponible. Si no se activa en tu proyecto Supabase, habilita la extensión
`pg_cron` y programa esa función cada cinco minutos desde Supabase Cron. Por
ello, una expiración puede procesarse hasta cinco minutos después del límite.
Las PR abiertas no se cierran automáticamente al vencer el plazo: el creador
debe cerrarlas en GitHub si la tarea vuelve a estar disponible.

El flujo indicado al crear el proyecto es el valor predeterminado. Cada tarea
puede usar revisión directa o revisión por capas, también cuando se redacta a
partir de un módulo; las propuestas heredan el flujo del módulo salvo que el
proponente lo cambie en esa tarea.

Gemini recibe solo el título y la descripción del proyecto y devuelve tareas
editables con estimación de hasta 8 horas por persona y dificultad
Baja/Media/Alta. Si incluyes la URL de GitHub en la descripción, se asigna
automáticamente como repositorio destino de cada tarea, separada del modo de
entrega. Al crear un proyecto también se puede publicar solo una lista
de módulos: los colaboradores compatibles reclaman un módulo, proponen tareas
completas y el creador aprueba o devuelve la propuesta antes de publicarlas.
La URL del repositorio destino es obligatoria para nuevas tareas y debe
revisarse antes de publicarlas.

## Alcance de esta versión

Está implementado el ciclo de tareas directas y por capas, la redacción y
aprobación de propuestas a partir de módulos, vencimientos y reputación. Las
asignaciones y revisiones aparecen en las secciones correspondientes de la
aplicación; no se envían notificaciones push ni correos en esta versión. En
una revisión, el colaborador puede aceptar, pedir cambios o aportar un enlace
a una versión que editó fuera de la plataforma; esta no modifica repositorios
de GitHub directamente. La creación de la PR final también se hace en GitHub
por el creador; el webhook confirma su merge.
La interfaz utiliza un tema claro y muestra la ficha completa de la tarea al
colaborador asignado y a quienes la revisan.
Al iniciar sesión, el perfil carga desde Supabase las habilidades, tareas y
módulos asignados y los proyectos propios que aún tienen trabajo pendiente.
Los borradores de los widgets y la sesión de Supabase se guardan en
`localStorage` del navegador para recuperarlos al recargar la página. Las
contraseñas nunca se guardan allí; cerrar sesión elimina los tokens persistidos.
Los detalles técnicos de fallos se registran en el servidor; la interfaz no
expone excepciones de Supabase ni mensajes de error crudos.

## Pruebas

Desde `pcapp/`, ejecuta `python -m unittest discover -s tests`.
