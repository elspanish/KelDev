UPDATE public.task_reviews review
   SET decision = 'cancelled',
       feedback = 'El flujo de revisión por capas fue deshabilitado.',
       decided_at = now()
  FROM public.contributions contribution
  JOIN public.tasks task ON task.id::text = contribution.task_id::text
 WHERE review.contribution_id = contribution.id::text
   AND review.decision = 'pending'
   AND task.review_mode = 'layered';

UPDATE public.contributions contribution
   SET workflow_state = 'changes_requested',
       estado = 'rechazada',
       creator_feedback = 'El flujo de revisión por capas fue deshabilitado. Esta entrega debe enviarse como Pull Request directa cuando la tarea esté asignada.'
  FROM public.tasks task
 WHERE task.id::text = contribution.task_id::text
   AND task.review_mode = 'layered'
   AND contribution.workflow_state IN (
       'peer_review', 'awaiting_creator', 'awaiting_merge'
   );

UPDATE public.tasks
   SET estado = CASE
           WHEN asignado_a IS NULL THEN 'pendiente'
           ELSE 'en_progreso'
       END,
       deadline_at = CASE
           WHEN asignado_a IS NULL THEN NULL
           ELSE now() + make_interval(hours => claim_timeout_hours)
       END
 WHERE review_mode = 'layered'
   AND estado = 'en_revision';

UPDATE public.projects
   SET review_mode = 'direct'
 WHERE review_mode <> 'direct';

UPDATE public.tasks
   SET review_mode = 'direct'
 WHERE review_mode <> 'direct';

UPDATE public.project_modules
   SET review_mode = 'direct'
 WHERE review_mode <> 'direct';

UPDATE public.module_task_proposals proposal
   SET tasks = (
       SELECT jsonb_agg(
           CASE
               WHEN jsonb_typeof(proposed_task.value) = 'object'
               THEN jsonb_set(
                   proposed_task.value,
                   '{review_mode}',
                   '"direct"'::jsonb,
                   true
               )
               ELSE proposed_task.value
           END
           ORDER BY proposed_task.ordinality
       )
       FROM jsonb_array_elements(proposal.tasks)
           WITH ORDINALITY AS proposed_task(value, ordinality)
   )
 WHERE proposal.estado = 'pendiente_revision'
   AND jsonb_typeof(proposal.tasks) = 'array'
   AND proposal.tasks <> '[]'::jsonb;

ALTER TABLE public.projects
    DROP CONSTRAINT IF EXISTS projects_review_mode_check,
    ADD CONSTRAINT projects_review_mode_check
        CHECK (review_mode = 'direct');

ALTER TABLE public.tasks
    DROP CONSTRAINT IF EXISTS tasks_review_mode_check,
    ADD CONSTRAINT tasks_review_mode_check
        CHECK (review_mode = 'direct');

ALTER TABLE public.project_modules
    DROP CONSTRAINT IF EXISTS project_modules_review_mode_check,
    ADD CONSTRAINT project_modules_review_mode_check
        CHECK (review_mode = 'direct');

ALTER TABLE public.projects
    ALTER COLUMN review_mode SET DEFAULT 'direct';

ALTER TABLE public.tasks
    ALTER COLUMN review_mode SET DEFAULT 'direct';

ALTER TABLE public.project_modules
    ALTER COLUMN review_mode SET DEFAULT 'direct',
    ALTER COLUMN creator_review_timeout_hours SET DEFAULT 72;

REVOKE ALL ON FUNCTION public.submit_layered_task_code(text, text)
    FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.review_layered_task(text, text, text, text)
    FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.creator_decide_layered_task(text, text, text)
    FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.approve_layered_task_with_pr(
    text, text, text, text, integer
) FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.register_layered_final_pr(
    text, text, text, text, integer
) FROM PUBLIC, anon, authenticated, service_role;

NOTIFY pgrst, 'reload schema';
