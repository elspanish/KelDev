# Instrucciones de Desarrollo: Plataforma Dev (ECC Framework)

## 1. Contexto Tecnológico
- **UI Framework:** Streamlit (No usar FastAPI, Tkinter ni Flask).
- **Backend/Database:** Supabase Client (`supabase-py`).
- **Autenticación:** Supabase Auth (Email/Contraseña) mediante `st.session_state.user`.

## 2. Reglas de Código Estrictas para Copilot
- **PROHIBIDO:** Usar `input()`, `print()`, `sys.exit()` o cualquier comando de consola interactiva.
- **Entradas:** Toda interacción de usuario debe ser mediante widgets de Streamlit (`st.text_input`, `st.button`, `st.selectbox`, `st.text_area`).
- **Mensajes de Estado:** Sustituir `print()` por `st.success()`, `st.error()`, `st.info()` o `st.warning()`.
- **Manejo de Sesión:** Toda variable global de usuario debe depender de `st.session_state.user.id` (UUID devuelto por Supabase Auth).
- **Control de Errores:** Envolver llamadas de base de datos en bloques `try...except Exception as e:` y mostrar el error con `st.error(e)`.

## 3. Esquema de Base de Datos (Supabase)
- `profiles`: id (UUID, PK), email (text), nombre (text), habilidades (array/text), reputacion (int), tareas_completadas (int).
- `projects`: id (int/UUID, PK), titulo (text), descripcion (text).
- `tasks`: id (int/UUID, PK), project_id (FK), titulo (text), habilidades_requeridas (array), instrucciones (text), restricciones (text), recursos (text), objetivo (text), entregables (text), criterios_aceptacion (text), estado ('pendiente', 'en_progreso', 'en_revision', 'completada'), asignado_a (UUID, FK).
- `contributions`: id (PK), task_id (FK), usuario_id (UUID, FK), github_pr_url (text), estado ('pendiente_revision', 'aceptada', 'rechazada'), puntuacion (int).

## 4. Lógica de Negocio Automática
- Al aprobar una entrega: `reputacion = reputacion_actual + (puntuacion * 100)` y `tareas_completadas = tareas_completadas + 1`.
- Filtrar siempre los datos del usuario usando su UUID (`id`), NUNCA por su nombre de usuario.
