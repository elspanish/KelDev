# Instrucciones de Desarrollo: KelDev (ECC Framework)

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
- Al fusionar una entrega: suma 50, 80 o 140 puntos por cada habilidad requerida coincidente, según la dificultad (Fácil, Medio o Difícil). Actualiza `reputacion_habilidades`, recalcula `reputacion` y aumenta `tareas_completadas` una sola vez.
- Filtrar siempre los datos del usuario usando su UUID (`id`), NUNCA por su nombre de usuario.

##5. Esquema de la base de datos (Supabase)
-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.profiles (
  id uuid NOT NULL,
  email text NOT NULL DEFAULT ''::text,
  nombre text NOT NULL DEFAULT ''::text,
  descripcion text NOT NULL DEFAULT ''::text,
  habilidades jsonb NOT NULL DEFAULT '[]'::jsonb,
  reputacion integer NOT NULL DEFAULT 0,
  tareas_completadas integer NOT NULL DEFAULT 0,
  reputacion_habilidades jsonb NOT NULL DEFAULT '{}'::jsonb,
  CONSTRAINT profiles_pkey PRIMARY KEY (id),
  CONSTRAINT profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id)
);
CREATE TABLE public.projects (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  titulo text NOT NULL,
  descripcion text NOT NULL DEFAULT ''::text,
  owner_id uuid,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  review_mode text NOT NULL DEFAULT 'direct'::text CHECK (review_mode = 'direct'::text),
  CONSTRAINT projects_pkey PRIMARY KEY (id),
  CONSTRAINT projects_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES auth.users(id)
);
CREATE TABLE public.tasks (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  project_id bigint NOT NULL,
  titulo text NOT NULL,
  habilidades_requeridas jsonb NOT NULL DEFAULT '[]'::jsonb,
  instrucciones text NOT NULL DEFAULT ''::text,
  restricciones text NOT NULL DEFAULT ''::text,
  recursos text NOT NULL DEFAULT ''::text,
  objetivo text NOT NULL DEFAULT ''::text,
  entregables text NOT NULL DEFAULT ''::text,
  criterios_aceptacion text NOT NULL DEFAULT ''::text,
  modo_entrega text NOT NULL DEFAULT 'Pull Request de GitHub'::text,
  duracion_estimada_horas integer NOT NULL DEFAULT 4 CHECK (duracion_estimada_horas >= 1 AND duracion_estimada_horas <= 8),
  dificultad text NOT NULL DEFAULT 'Medio'::text CHECK (dificultad = ANY (ARRAY['Fácil'::text, 'Medio'::text, 'Difícil'::text])),
  estado text NOT NULL DEFAULT 'pendiente'::text CHECK (estado = ANY (ARRAY['pendiente'::text, 'en_progreso'::text, 'en_revision'::text, 'completada'::text])),
  asignado_a uuid,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  deadline_at timestamp with time zone,
  claim_timeout_hours integer NOT NULL DEFAULT 24,
  repositorio_url text NOT NULL DEFAULT ''::text,
  module_id text,
  review_mode text NOT NULL DEFAULT 'direct'::text CHECK (review_mode = 'direct'::text),
  peer_review_timeout_hours integer NOT NULL DEFAULT 48 CHECK (peer_review_timeout_hours >= 1 AND peer_review_timeout_hours <= 720),
  creator_review_timeout_hours integer NOT NULL DEFAULT 72 CHECK (creator_review_timeout_hours >= 1 AND creator_review_timeout_hours <= 720),
  CONSTRAINT tasks_pkey PRIMARY KEY (id),
  CONSTRAINT tasks_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id),
  CONSTRAINT tasks_asignado_a_fkey FOREIGN KEY (asignado_a) REFERENCES auth.users(id)
);
CREATE TABLE public.contributions (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  task_id bigint NOT NULL,
  usuario_id uuid NOT NULL,
  github_pr_url text NOT NULL,
  github_owner text,
  github_repo text,
  github_pr_number integer,
  reputacion_otorgada boolean NOT NULL DEFAULT false,
  estado text NOT NULL DEFAULT 'pendiente_revision'::text CHECK (estado = ANY (ARRAY['pendiente_revision'::text, 'aceptada'::text, 'rechazada'::text])),
  puntuacion integer NOT NULL DEFAULT 5 CHECK (puntuacion >= 0),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  code_url text,
  workflow_state text NOT NULL DEFAULT 'awaiting_merge'::text CHECK (workflow_state = ANY (ARRAY['peer_review'::text, 'changes_requested'::text, 'awaiting_creator'::text, 'awaiting_merge'::text, 'completed'::text, 'rejected'::text])),
  round_number integer NOT NULL DEFAULT 1,
  creator_feedback text NOT NULL DEFAULT ''::text,
  reputacion_detalle jsonb NOT NULL DEFAULT '{}'::jsonb,
  reputacion_detalle_completo boolean NOT NULL DEFAULT false,
  CONSTRAINT contributions_pkey PRIMARY KEY (id),
  CONSTRAINT contributions_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(id),
  CONSTRAINT contributions_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES auth.users(id)
);
CREATE TABLE public.project_modules (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  project_id bigint NOT NULL,
  titulo text NOT NULL,
  estado text NOT NULL DEFAULT 'pendiente'::text CHECK (estado = ANY (ARRAY['pendiente'::text, 'en_progreso'::text, 'en_revision'::text, 'completado'::text])),
  asignado_a uuid,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  descripcion text NOT NULL DEFAULT ''::text,
  repositorio_url text NOT NULL DEFAULT ''::text,
  review_mode text NOT NULL DEFAULT 'direct'::text CHECK (review_mode = 'direct'::text),
  habilidades_requeridas jsonb NOT NULL DEFAULT '[]'::jsonb,
  claim_timeout_hours integer NOT NULL DEFAULT 72 CHECK (claim_timeout_hours >= 1 AND claim_timeout_hours <= 720) NOT VALI),
  creator_review_timeout_hours integer NOT NULL DEFAULT 72 CHECK (creator_review_timeout_hours >= 1 AND creator_review_timeout_hours <= 720) NOT VALI),
  task_claim_timeout_hours integer NOT NULL DEFAULT 72 CHECK (task_claim_timeout_hours >= 1 AND task_claim_timeout_hours <= 720) NOT VALI),
  peer_review_timeout_hours integer NOT NULL DEFAULT 48 CHECK (peer_review_timeout_hours >= 1 AND peer_review_timeout_hours <= 720) NOT VALI),
  deadline_at timestamp with time zone,
  CONSTRAINT project_modules_pkey PRIMARY KEY (id),
  CONSTRAINT project_modules_asignado_a_fkey FOREIGN KEY (asignado_a) REFERENCES auth.users(id),
  CONSTRAINT project_modules_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id)
);
CREATE TABLE public.task_assignment_history (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  task_id text NOT NULL,
  collaborator_id uuid NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  assigned_at timestamp with time zone NOT NULL DEFAULT now(),
  expired_at timestamp with time zone,
  CONSTRAINT task_assignment_history_pkey PRIMARY KEY (id),
  CONSTRAINT task_assignment_history_collaborator_id_fkey FOREIGN KEY (collaborator_id) REFERENCES auth.users(id)
);
CREATE TABLE public.task_reviews (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  task_id text NOT NULL,
  reviewer_id uuid NOT NULL,
  decision text NOT NULL DEFAULT 'pending'::text CHECK (decision = ANY (ARRAY['pending'::text, 'accepted'::text, 'changes_requested'::text, 'edited'::text, 'cancelled'::text])),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  contribution_id text,
  previous_reviewer_ids ARRAY NOT NULL DEFAULT '{}'::uuid[],
  feedback text NOT NULL DEFAULT ''::text,
  revised_code_url text,
  assigned_at timestamp with time zone NOT NULL DEFAULT now(),
  deadline_at timestamp with time zone,
  decided_at timestamp with time zone,
  CONSTRAINT task_reviews_pkey PRIMARY KEY (id),
  CONSTRAINT task_reviews_reviewer_id_fkey FOREIGN KEY (reviewer_id) REFERENCES auth.users(id)
);
CREATE TABLE public.project_module_assignments (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  module_id bigint NOT NULL,
  collaborator_id uuid NOT NULL,
  assigned_at timestamp with time zone NOT NULL DEFAULT now(),
  expired_at timestamp with time zone,
  CONSTRAINT project_module_assignments_pkey PRIMARY KEY (id),
  CONSTRAINT project_module_assignments_module_id_fkey FOREIGN KEY (module_id) REFERENCES public.project_modules(id),
  CONSTRAINT project_module_assignments_collaborator_id_fkey FOREIGN KEY (collaborator_id) REFERENCES auth.users(id)
);
CREATE TABLE public.module_task_proposals (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  module_id bigint NOT NULL,
  proposer_id uuid NOT NULL,
  tasks jsonb NOT NULL,
  estado text NOT NULL DEFAULT 'pendiente_revision'::text CHECK (estado = ANY (ARRAY['pendiente_revision'::text, 'cambios_solicitados'::text, 'aceptada'::text])),
  feedback text NOT NULL DEFAULT ''::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  decided_at timestamp with time zone,
  CONSTRAINT module_task_proposals_pkey PRIMARY KEY (id),
  CONSTRAINT module_task_proposals_module_id_fkey FOREIGN KEY (module_id) REFERENCES public.project_modules(id),
  CONSTRAINT module_task_proposals_proposer_id_fkey FOREIGN KEY (proposer_id) REFERENCES auth.users(id)
);
CREATE TABLE public.skill_catalog (
  nombre text NOT NULL CHECK (length(btrim(nombre)) >= 1 AND length(btrim(nombre)) <= 80),
  nombre_normalizado text DEFAULT lower(btrim(nombre)) UNIQUE,
  created_at timestamp with time zone NOT NULL DEFAULT now()
);
