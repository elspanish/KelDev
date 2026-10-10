CREATE OR REPLACE FUNCTION public.claim_task(p_task_id text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_user_id uuid := auth.uid();
    v_task public.tasks%ROWTYPE;
BEGIN
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Debes iniciar sesión para aceptar una tarea';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(v_user_id::text, 0));
    IF EXISTS (
        SELECT 1 FROM public.tasks
         WHERE asignado_a = v_user_id AND estado = 'en_progreso'
    ) OR EXISTS (
        SELECT 1 FROM public.project_modules
         WHERE asignado_a = v_user_id AND estado = 'en_progreso'
    ) THEN
        RAISE EXCEPTION 'Termina o entrega tu asignación en progreso antes de aceptar otra';
    END IF;

    SELECT task.* INTO v_task
      FROM public.tasks task
      JOIN public.profiles profile ON profile.id = v_user_id
      JOIN public.projects project ON project.id = task.project_id
     WHERE task.id::text = p_task_id
       AND task.estado = 'pendiente'
       AND project.owner_id IS DISTINCT FROM v_user_id
       AND NOT EXISTS (
           SELECT 1 FROM public.task_assignment_history history
            WHERE history.task_id = task.id::text
              AND history.collaborator_id = v_user_id
       )
       AND EXISTS (
           SELECT 1
             FROM public.jsonb_text_values(to_jsonb(task.habilidades_requeridas)) required(skill)
             JOIN public.jsonb_text_values(to_jsonb(profile.habilidades)) owned(skill)
               ON lower(trim(required.skill)) = lower(trim(owned.skill))
       )
     FOR UPDATE OF task;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'La tarea ya no está disponible o tus habilidades no coinciden';
    END IF;

    UPDATE public.tasks
       SET estado = 'en_progreso',
           asignado_a = v_user_id,
           deadline_at = now() + make_interval(hours => v_task.claim_timeout_hours)
     WHERE id = v_task.id;

    INSERT INTO public.task_assignment_history (task_id, collaborator_id)
    VALUES (v_task.id::text, v_user_id);
END;
$$;

CREATE OR REPLACE FUNCTION public.is_task_reviewer(p_task_id text)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT auth.uid() IS NOT NULL
       AND EXISTS (
           SELECT 1
             FROM public.task_reviews review
            WHERE review.task_id = p_task_id
              AND review.reviewer_id = auth.uid()
              AND review.decision = 'pending'
       )
$$;

REVOKE ALL ON FUNCTION public.is_task_reviewer(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_task_reviewer(text) TO authenticated;

DROP POLICY IF EXISTS "Authenticated users can view tasks" ON public.tasks;
CREATE POLICY "Users can view available or participating tasks"
    ON public.tasks FOR SELECT TO authenticated
    USING (
        estado = 'pendiente'
        OR asignado_a = auth.uid()
        OR EXISTS (
            SELECT 1
              FROM public.projects project
             WHERE project.id = tasks.project_id
               AND project.owner_id = auth.uid()
        )
        OR public.is_task_reviewer(id::text)
    );
