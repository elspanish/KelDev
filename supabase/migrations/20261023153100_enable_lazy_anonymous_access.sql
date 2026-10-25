-- Allow anonymous visitors to browse public work without exposing private data.
GRANT USAGE ON SCHEMA public TO anon, authenticated;

DROP POLICY IF EXISTS "Public users can view projects" ON public.projects;
CREATE POLICY "Public users can view projects"
    ON public.projects FOR SELECT TO anon USING (true);
GRANT SELECT ON public.projects TO authenticated;
REVOKE SELECT ON public.projects FROM anon;
GRANT SELECT (id, titulo, descripcion, created_at)
    ON public.projects TO anon;
REVOKE INSERT, UPDATE, DELETE ON public.projects FROM anon;

DROP POLICY IF EXISTS "Public users can view available tasks" ON public.tasks;
CREATE POLICY "Public users can view available tasks"
    ON public.tasks FOR SELECT TO anon USING (estado = 'pendiente');
GRANT SELECT ON public.tasks TO authenticated;
REVOKE SELECT ON public.tasks FROM anon;
GRANT SELECT (
    id, project_id, titulo, habilidades_requeridas, objetivo,
    dificultad, estado, created_at
) ON public.tasks TO anon;
REVOKE INSERT, UPDATE, DELETE ON public.tasks FROM anon;

DROP POLICY IF EXISTS "Public users can view skill catalog"
    ON public.skill_catalog;
CREATE POLICY "Public users can view skill catalog"
    ON public.skill_catalog FOR SELECT TO anon USING (true);
GRANT SELECT ON public.skill_catalog TO authenticated;
REVOKE SELECT ON public.skill_catalog FROM anon;
GRANT SELECT (nombre) ON public.skill_catalog TO anon;
REVOKE INSERT, UPDATE, DELETE ON public.skill_catalog FROM anon;

-- A signed-in anonymous user may only read and personalize their own profile.
DROP POLICY IF EXISTS "Authenticated users can view profiles"
    ON public.profiles;
CREATE POLICY "Authenticated users can view profiles"
    ON public.profiles FOR SELECT TO authenticated USING (id = auth.uid());
DROP POLICY IF EXISTS "Users can update their own profile"
    ON public.profiles;
CREATE POLICY "Users can update their own profile"
    ON public.profiles FOR UPDATE TO authenticated
    USING (id = auth.uid()) WITH CHECK (id = auth.uid());
GRANT SELECT ON public.profiles TO authenticated;
REVOKE UPDATE ON public.profiles FROM anon, authenticated;
GRANT UPDATE (nombre, descripcion, habilidades)
    ON public.profiles TO authenticated;

CREATE OR REPLACE FUNCTION public.reject_anonymous_critical_action()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    v_user_id uuid := auth.uid();
BEGIN
    IF coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false) IS NOT TRUE THEN
        RETURN NEW;
    END IF;

    IF TG_TABLE_NAME = 'projects' AND NEW.owner_id = v_user_id THEN
        RAISE EXCEPTION 'Crea una cuenta permanente para crear un proyecto';
    ELSIF TG_TABLE_NAME = 'tasks'
       AND NEW.asignado_a = v_user_id
       AND NEW.estado IN ('en_progreso', 'en_revision') THEN
        RAISE EXCEPTION 'Crea una cuenta permanente para reclamar una tarea';
    ELSIF TG_TABLE_NAME = 'project_modules'
       AND NEW.asignado_a = v_user_id
       AND NEW.estado = 'en_progreso' THEN
        RAISE EXCEPTION 'Crea una cuenta permanente para reclamar un módulo';
    END IF;

    RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION public.reject_anonymous_critical_action()
    FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS require_permanent_project_owner ON public.projects;
CREATE TRIGGER require_permanent_project_owner
    BEFORE INSERT OR UPDATE OF owner_id ON public.projects
    FOR EACH ROW EXECUTE FUNCTION public.reject_anonymous_critical_action();

DROP TRIGGER IF EXISTS require_permanent_task_assignment ON public.tasks;
CREATE TRIGGER require_permanent_task_assignment
    BEFORE UPDATE OF asignado_a, estado ON public.tasks
    FOR EACH ROW EXECUTE FUNCTION public.reject_anonymous_critical_action();

DROP TRIGGER IF EXISTS require_permanent_module_assignment
    ON public.project_modules;
CREATE TRIGGER require_permanent_module_assignment
    BEFORE UPDATE OF asignado_a, estado ON public.project_modules
    FOR EACH ROW EXECUTE FUNCTION public.reject_anonymous_critical_action();
