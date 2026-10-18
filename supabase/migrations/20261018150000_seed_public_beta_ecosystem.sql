-- Seed a public beta backlog using the existing projects, tasks, and skill schema.
-- Difficulty remains an internal Spanish enum until the database contract is migrated.

INSERT INTO public.skill_catalog (nombre)
SELECT skill.nombre
FROM (
    VALUES
        ('Python'),
        ('Streamlit'),
        ('CSS'),
        ('HTML'),
        ('Accessibility'),
        ('UX Design'),
        ('Testing'),
        ('Supabase'),
        ('PostgreSQL'),
        ('JavaScript'),
        ('Node.js'),
        ('Git'),
        ('GitHub Actions'),
        ('Documentation')
) AS skill(nombre)
ON CONFLICT (nombre_normalizado) DO NOTHING;

INSERT INTO public.projects (titulo, descripcion, owner_id)
SELECT seed.titulo, seed.descripcion, NULL
FROM (
    VALUES
        (
            'KelDev v2 - Core & UI Overhaul',
            'Official open-source initiative to modernize the Streamlit interface, introduce a cohesive global CSS system, organize content into responsive grid layouts, and simplify the platform visual architecture.'
        ),
        (
            'KelDev v2 - Optimizer & New Features',
            'Improve the contributor and maintainer experience by exposing practical project and task management capabilities in the KelDev interface, tightening workflows, and making everyday collaboration faster and safer.'
        ),
        (
            'Open Source Release Radar',
            'Build a small, reusable JavaScript and GitHub Actions tool that tracks releases across open-source repositories and publishes a concise, configurable release digest. This community project broadens KelDev contributions beyond the platform codebase.'
        )
) AS seed(titulo, descripcion)
WHERE NOT EXISTS (
    SELECT 1
    FROM public.projects AS existing
    WHERE existing.titulo = seed.titulo
);

WITH task_seed (
    project_title,
    titulo,
    habilidades_requeridas,
    instrucciones,
    restricciones,
    recursos,
    objetivo,
    entregables,
    criterios_aceptacion,
    modo_entrega,
    duracion_estimada_horas,
    dificultad
) AS (
    VALUES
        (
            'KelDev v2 - Core & UI Overhaul',
            'Translate the authentication screen into clear English',
            '["Python","Streamlit","UX Design"]'::jsonb,
            '1. Update the login and registration copy in pcapp/main.py. 2. Use concise English labels, helpful placeholders, and clear authentication feedback. 3. Keep Supabase Auth calls and session behavior unchanged. 4. Add or update focused tests if the authentication UI has test coverage.',
            'Do not change authentication providers, database fields, or session semantics. All user-facing text must be natural professional English.',
            'pcapp/main.py; Supabase Auth documentation; existing Streamlit patterns.',
            'Make login and registration immediately understandable to international contributors.',
            'English authentication labels, placeholders, and status messages in pcapp/main.py, plus focused tests where applicable.',
            'Login and registration render in English; successful sign-in, registration confirmation, and validation/error states remain functional.',
            'Submit a direct GitHub pull request with the UI changes and relevant tests.',
            3,
            'Fácil'
        ),
        (
            'KelDev v2 - Core & UI Overhaul',
            'Build a responsive global CSS design system',
            '["Python","Streamlit","CSS","Accessibility"]'::jsonb,
            '1. Refactor the global style block in pcapp/main.py into consistent CSS custom properties for color, spacing, borders, and focus states. 2. Apply the tokens to the sidebar, buttons, metrics, inputs, and bordered containers. 3. Add narrow-screen rules without relying on fragile Streamlit-generated class names. 4. Verify keyboard focus and text contrast.',
            'Keep the existing Streamlit layout and avoid JavaScript or new runtime dependencies.',
            'pcapp/main.py; Streamlit CSS selectors already used by the app; WCAG contrast guidance.',
            'Give KelDev a consistent, responsive visual foundation that remains usable with keyboard navigation.',
            'A cohesive CSS token set and responsive component styles in pcapp/main.py.',
            'The major Streamlit components share the design tokens, focus indicators are visible, and content remains usable at mobile widths.',
            'Submit a direct GitHub pull request with before/after screenshots and a short viewport/accessibility checklist.',
            5,
            'Medio'
        ),
        (
            'KelDev v2 - Core & UI Overhaul',
            'Turn the contributor dashboard into a scannable project grid',
            '["Python","Streamlit","CSS","UX Design"]'::jsonb,
            '1. Review the dashboard and project summary rendering in pcapp/main.py. 2. Group project title, summary, progress, and next action into reusable card content. 3. Use Streamlit columns or containers to create a responsive grid that collapses cleanly on small screens. 4. Preserve existing data loading and UUID-based ownership filters.',
            'Do not introduce a new frontend framework or change which projects a user can access.',
            'pcapp/main.py; Streamlit columns and containers documentation.',
            'Help contributors find active projects and their next action at a glance.',
            'Responsive project-card layout in pcapp/main.py with clear empty and populated states.',
            'Cards render existing project data without additional per-card database calls, remain readable on narrow screens, and keep user-specific data filtered by UUID.',
            'Submit a direct GitHub pull request with responsive screenshots and any focused tests.',
            4,
            'Medio'
        ),
        (
            'KelDev v2 - Core & UI Overhaul',
            'Make task details readable with structured sections',
            '["Python","Streamlit","UX Design","Accessibility"]'::jsonb,
            '1. Refactor render_task_details in pcapp/main.py to group task information into concise sections for skills, implementation, deliverables, and logistics. 2. Use headings, captions, and expanders only where they improve scanning. 3. Render difficulty and task status with English labels while retaining the database values expected by existing RPCs. 4. Keep repository links descriptive.',
            'Do not omit any existing task fields or change task assignment and reward behavior.',
            'pcapp/main.py; existing render_task_details helper; Streamlit accessibility guidance.',
            'Let a contributor understand scope, acceptance criteria, and reward before claiming a task.',
            'A structured task-detail presentation used consistently by task discovery and assigned-task views.',
            'All current task fields remain visible, labels are English, external links are understandable, and existing compatible-task behavior is unchanged.',
            'Submit a direct GitHub pull request with focused rendering tests or screenshots.',
            4,
            'Medio'
        ),
        (
            'KelDev v2 - Core & UI Overhaul',
            'Polish profile skills and reputation into an achievement panel',
            '["Python","Streamlit","CSS","UX Design"]'::jsonb,
            '1. Update the profile section in pcapp/main.py to present total reputation, completed tasks, and per-skill scores as a coherent panel. 2. Improve empty-state guidance for profiles without skills. 3. Add clear English help text to skill search and save actions. 4. Keep profile updates filtered by the authenticated user UUID.',
            'Do not change reputation calculations, profile schema, or the canonical skill names.',
            'pcapp/main.py; public.profiles fields; existing skill_catalog helpers.',
            'Make contributor progress easy to understand and give new users a clear next step.',
            'An English profile achievement panel and accessible empty states in pcapp/main.py.',
            'Profile metrics and skill scores use consistent labels; editing still updates only the authenticated profile; empty profiles explain how to find matching tasks.',
            'Submit a direct GitHub pull request with profile screenshots and regression coverage.',
            3,
            'Fácil'
        ),
        (
            'KelDev v2 - Core & UI Overhaul',
            'Improve project and task editor labels and validation',
            '["Python","Streamlit","UX Design","Testing"]'::jsonb,
            '1. Update project/task editor labels, placeholders, help text, and validation feedback in pcapp/main.py. 2. Explain required repository URLs, skill selection, one-person hour estimates, and acceptance criteria in plain English. 3. Preserve field names sent to Supabase RPCs. 4. Add tests for validation cases that are not already covered.',
            'Do not change database column names or weaken server-side validation.',
            'pcapp/main.py; pcapp/integrations.py; existing validation tests.',
            'Make project creation predictable without exposing internal database terminology.',
            'Consistent English form labels and actionable validation messages.',
            'Users can identify missing fields and correct them without seeing implementation field keys; valid project/task submissions retain their existing payload shape.',
            'Submit a direct GitHub pull request with updated tests for changed validation behavior.',
            4,
            'Medio'
        ),
        (
            'KelDev v2 - Core & UI Overhaul',
            'Replace the task-generation prompt with an English-first contract',
            '["Python","Testing","Streamlit"]'::jsonb,
            '1. Rewrite build_project_task_prompt in pcapp/integrations.py in professional English. 2. Require the model to return English task titles and descriptions, concrete file paths, complete JSON fields, catalog skill names, valid GitHub repository URLs, and a single-person estimate of 1-8 hours. 3. Normalize English difficulty labels at the application boundary to the database values accepted by the current schema. 4. Update pcapp/tests/test_integrations.py to assert the English contract.',
            'Keep generated output JSON-only and preserve the existing field names and direct pull request workflow.',
            'pcapp/integrations.py; pcapp/tests/test_integrations.py; task-generation RPC payload contract.',
            'Ensure AI-generated task drafts are immediately useful to English-speaking contributors and valid for the existing database.',
            'An English generation prompt, compatible difficulty normalization, and focused prompt/validation tests.',
            'Prompt instructions require English; valid generated tasks are accepted; invalid duration, difficulty, skills, or missing fields continue to raise clear errors.',
            'Submit a direct GitHub pull request with focused integration tests.',
            4,
            'Medio'
        ),
        (
            'KelDev v2 - Core & UI Overhaul',
            'Add accessible feedback and keyboard states across Streamlit',
            '["Python","Streamlit","CSS","Accessibility"]'::jsonb,
            '1. Audit buttons, forms, expanders, and navigation in pcapp/main.py. 2. Add visible focus styling and clear labels/help text where controls are ambiguous. 3. Replace symbol-only status cues with text or accessible labels. 4. Check the login, profile, create-project, collaborate, and submission flows using keyboard navigation.',
            'Do not add custom JavaScript or remove existing status and error feedback.',
            'pcapp/main.py; Streamlit widget API; WCAG keyboard and contrast guidance.',
            'Make primary contributor journeys understandable and operable without a mouse.',
            'Small accessibility improvements to global styles and the key Streamlit workflows.',
            'All key actions can be reached by keyboard, focus remains visible, and no status is communicated by color alone.',
            'Submit a direct GitHub pull request with a concise manual accessibility test checklist.',
            5,
            'Medio'
        ),
        (
            'KelDev v2 - Optimizer & New Features',
            'Let project owners edit project details from the dashboard',
            '["Python","Streamlit","Supabase","PostgreSQL"]'::jsonb,
            '1. Add an owned-project management section in pcapp/main.py using the existing user overview. 2. Load and edit a selected project title and description. 3. Persist changes through an owner-authorized Supabase update or narrowly scoped RPC. 4. Refresh cached overview data and show explicit success/error feedback.',
            'Every read and write must be authorized by the authenticated UUID; do not trust a client-supplied owner ID.',
            'pcapp/main.py; public.projects.owner_id; existing project RLS policies.',
            'Allow project maintainers to keep project scope current without editing rows manually in GitHub or Supabase.',
            'Owner-only project detail editor with validation, persistence, and updated tests.',
            'A user can edit only projects they own; changes appear after refresh; unauthorized updates are rejected by database policy.',
            'Submit a direct GitHub pull request with focused authorization and UI tests.',
            5,
            'Medio'
        ),
        (
            'KelDev v2 - Optimizer & New Features',
            'Add a safe project deletion workflow for owners',
            '["Python","Streamlit","Supabase","PostgreSQL","Testing"]'::jsonb,
            '1. Design an owner-only delete operation for public.projects and dependent tasks/modules. 2. Add a security-definer RPC or foreign-key strategy in a new Supabase migration that verifies auth.uid() against owner_id and handles dependent rows transactionally. 3. Add a confirmation step and impact summary in pcapp/main.py. 4. Test owner, non-owner, and cascade behavior.',
            'Never accept a project owner UUID from the client. Preserve task/contribution referential integrity and do not silently delete unrelated records.',
            'supabase/migrations/; pcapp/main.py; public.projects, public.tasks, public.project_modules, and public.contributions.',
            'Give maintainers a clear, secure way to remove abandoned projects.',
            'An owner-authorized deletion RPC/migration, confirmation UI, and database/UI tests.',
            'Only the owner can delete; deletion behavior for dependent data is explicit and transactional; the UI requires confirmation and refreshes its project list.',
            'Submit a direct GitHub pull request with migration and authorization tests.',
            6,
            'Difícil'
        ),
        (
            'KelDev v2 - Optimizer & New Features',
            'Let owners edit task specifications without recreating tasks',
            '["Python","Streamlit","Supabase","PostgreSQL"]'::jsonb,
            '1. Add a task editor for tasks belonging to a project owned by the current user in pcapp/main.py. 2. Support title, instructions, objective, constraints, deliverables, resources, acceptance criteria, skills, difficulty, and estimate. 3. Persist through RLS-protected updates or an owner-checking RPC. 4. Prevent edits to assignment and contribution state.',
            'Filter ownership by auth.uid(); do not expose mutable assignment, reputation, or review workflow fields.',
            'pcapp/main.py; public.tasks; task/project RLS policies; skill_catalog.',
            'Allow maintainers to sharpen task scope while preserving assignment and reward integrity.',
            'Owner-only task-specification editor with field validation and regression tests.',
            'Owned task content and skills can be updated; non-owners are rejected; assignment state and contribution data remain unchanged.',
            'Submit a direct GitHub pull request with focused database authorization tests.',
            6,
            'Difícil'
        ),
        (
            'KelDev v2 - Optimizer & New Features',
            'Add an owner action to unassign a stalled task',
            '["Python","Streamlit","Supabase","PostgreSQL","Testing"]'::jsonb,
            '1. Add an owner-authorized database function in a new migration to release a task only when its project owner matches auth.uid() and its state is in progress. 2. Clear asignado_a, return estado to pendiente, and clear deadline_at atomically. 3. Add a confirmation action beside eligible tasks in pcapp/main.py. 4. Cover invalid states and non-owner requests.',
            'Do not delete contribution history or unassign tasks with a submitted contribution in review.',
            'supabase/migrations/; pcapp/main.py; public.tasks; public.contributions.',
            'Help project owners recover work that has stalled before a pull request is submitted.',
            'A guarded unassign RPC, owner-facing confirmation UI, and tests.',
            'Only an owner can release an eligible in-progress task; tasks in review cannot be released; the task becomes available and its deadline is cleared.',
            'Submit a direct GitHub pull request with migration and workflow tests.',
            5,
            'Medio'
        ),
        (
            'KelDev v2 - Optimizer & New Features',
            'Let contributors release a task they can no longer complete',
            '["Python","Streamlit","Supabase","PostgreSQL"]'::jsonb,
            '1. Add a contributor-facing release action for the authenticated user task assignments in pcapp/main.py. 2. Implement a narrowly scoped RPC that checks auth.uid(), in-progress state, and absence of an active contribution. 3. Clear assignment and deadline atomically. 4. Add clear confirmation and refreshed availability feedback.',
            'A contributor must not release another user task or a task with a submitted pull request.',
            'pcapp/main.py; supabase/migrations/; public.tasks; public.contributions.',
            'Reduce abandoned assignments by making it safe and simple for contributors to return unfinished work.',
            'A contributor release RPC and UI action with authorization and state tests.',
            'Only the assigned user can release their eligible task; in-review tasks remain assigned; the task reappears in compatible task discovery.',
            'Submit a direct GitHub pull request with focused RPC and UI tests.',
            5,
            'Medio'
        ),
        (
            'KelDev v2 - Optimizer & New Features',
            'Add search and skill filters to task discovery',
            '["Python","Streamlit","Supabase","UX Design"]'::jsonb,
            '1. Add a search field and optional skill filters to the task discovery view in pcapp/main.py. 2. Filter only the compatible, pending tasks already returned for the authenticated user. 3. Make filters composable and add a one-click clear action. 4. Provide useful empty states and avoid issuing a request for each keystroke.',
            'Do not bypass find_compatible_tasks or expose tasks that do not match the user skill rules.',
            'pcapp/main.py; find_compatible_tasks RPC; skill_catalog.',
            'Help contributors find a good first task quickly without weakening eligibility checks.',
            'English search/filter controls and client-side filtering of eligible task results.',
            'Search matches task titles and descriptions, skill filters behave predictably, clearing filters restores all eligible results, and task claims retain existing server checks.',
            'Submit a direct GitHub pull request with filter behavior tests.',
            4,
            'Medio'
        ),
        (
            'KelDev v2 - Optimizer & New Features',
            'Add status and completion progress to owner project cards',
            '["Python","Streamlit","Supabase","UX Design"]'::jsonb,
            '1. Extend owned-project loading in pcapp/main.py to aggregate task and module counts by state. 2. Show completed, available, and in-progress totals on each project card. 3. Avoid an N+1 query pattern by loading project task states in batches. 4. Add no-task and fully-complete states.',
            'Do not change task state transitions or count contributions as completed tasks.',
            'pcapp/main.py; public.projects; public.tasks; project_modules.',
            'Give owners immediate insight into project health and where contributors are needed.',
            'Project progress summaries based on existing task/module state.',
            'Counts reconcile with stored task states, use English status labels, and render correctly when a project has no tasks.',
            'Submit a direct GitHub pull request with aggregation tests.',
            4,
            'Medio'
        ),
        (
            'KelDev v2 - Optimizer & New Features',
            'Show a contributor activity and reward history',
            '["Python","Streamlit","Supabase","PostgreSQL"]'::jsonb,
            '1. Add a paginated activity section to the profile view in pcapp/main.py using the authenticated user contribution rows. 2. Join task and project titles in bounded batches. 3. Display submission status, dates, and reputation details when available. 4. Add empty/loading/error states and keep private data scoped to the current UUID.',
            'Never query activity by display name. Do not calculate or award reputation in the UI.',
            'pcapp/main.py; public.contributions; public.tasks; public.projects; existing reputation detail fields.',
            'Help contributors understand what they shipped and which skills earned reputation.',
            'A user-scoped, paginated activity history in the profile with clear status labels.',
            'Only the authenticated user activity is shown; task/project names resolve in bounded queries; reputation values are read-only and match Supabase.',
            'Submit a direct GitHub pull request with data-scope and pagination tests.',
            5,
            'Medio'
        ),
        (
            'KelDev v2 - Optimizer & New Features',
            'Add project and task drafts that survive a browser refresh',
            '["Python","Streamlit","Testing"]'::jsonb,
            '1. Review pcapp/browser_storage.py and its tests before extending persistence. 2. Persist the in-progress project form and task drafts using the existing browser-storage helper. 3. Restore drafts only for the current authenticated UUID and clear them after successful publication or sign-out. 4. Add tests for refresh restoration and user isolation.',
            'Do not persist access tokens, passwords, private contribution data, or drafts under a shared key.',
            'pcapp/browser_storage.py; pcapp/main.py; pcapp/tests/test_browser_storage.py.',
            'Prevent contributors from losing carefully written project/task specifications on a refresh.',
            'User-scoped draft persistence integrated with the existing browser storage module.',
            'Drafts restore after refresh for the same user, are isolated across users, and clear on publish/sign-out without storing credentials.',
            'Submit a direct GitHub pull request with browser-storage regression tests.',
            5,
            'Medio'
        ),
        (
            'KelDev v2 - Optimizer & New Features',
            'Allow maintainers to publish tasks without a GitHub repository',
            '["Python","Streamlit","Supabase","PostgreSQL"]'::jsonb,
            '1. Map repository URL requirements in pcapp/main.py and the create_project_with_workflow validation in the consolidated migration. 2. Propose a safe task delivery mode for documentation, triage, and platform-hosted work that does not require a repository URL. 3. Update database validation and UI conditionally by delivery mode. 4. Keep direct GitHub pull request tasks strictly validated.',
            'Do not weaken HTTPS/GitHub validation for tasks that use GitHub pull request delivery.',
            'pcapp/main.py; supabase/migrations/20261014143000_platform_dev_consolidated.sql; generated task tests.',
            'Support worthwhile community contributions that do not naturally produce a code pull request.',
            'A database-backed delivery-mode contract and matching conditional project/task validation.',
            'Repository-less tasks can be published only with an approved alternate delivery route; GitHub-mode tasks still require a valid destination; unauthorized data changes remain blocked.',
            'Submit a direct GitHub pull request with migration, UI, and validation tests.',
            6,
            'Difícil'
        ),
        (
            'Open Source Release Radar',
            'Scaffold a reusable release digest GitHub Action',
            '["GitHub Actions","JavaScript","Node.js","Git"]'::jsonb,
            '1. Create .github/actions/release-radar/action.yml with typed inputs for repository list and maximum releases per repository. 2. Add package metadata and a Node.js entrypoint under tools/release-radar/. 3. Document supported Node runtime and action outputs. 4. Validate the manifest with the repository''s existing checks or a focused YAML test.',
            'Use a supported Node.js runtime and do not commit credentials or personal access tokens.',
            '.github/actions/release-radar/action.yml; tools/release-radar/package.json; tools/release-radar/index.js.',
            'Give open-source maintainers a reusable, configurable action foundation.',
            'A valid composite/action manifest, Node package entrypoint, and concise usage documentation.',
            'The action metadata parses, inputs and outputs are documented, and the entrypoint runs under the declared Node runtime.',
            'Submit a direct GitHub pull request with manifest validation evidence.',
            4,
            'Medio'
        ),
        (
            'Open Source Release Radar',
            'Fetch recent releases with the GitHub REST API',
            '["JavaScript","Node.js","GitHub Actions","Testing"]'::jsonb,
            '1. Implement a small GitHub REST client in tools/release-radar/src/github.js. 2. Request releases for each configured repository, apply the configured result limit, and return normalized name, tag, URL, and publication date fields. 3. Support the Actions-provided token without logging it. 4. Add mocked tests for success, empty repositories, and HTTP errors.',
            'Use HTTPS and least-privilege token access; never print tokens or silently convert API failures into empty release lists.',
            'tools/release-radar/src/github.js; tools/release-radar/test/; GitHub REST API releases documentation.',
            'Provide reliable, testable release metadata for the digest formatter.',
            'A tested GitHub release client with normalized output and explicit failures.',
            'Successful responses normalize deterministically, limits are enforced, empty repositories return an empty list, and API errors include useful non-secret context.',
            'Submit a direct GitHub pull request with unit test results.',
            5,
            'Medio'
        ),
        (
            'Open Source Release Radar',
            'Format releases into a clean Markdown digest',
            '["JavaScript","Node.js","Testing"]'::jsonb,
            '1. Add a pure formatter in tools/release-radar/src/format.js. 2. Group releases by repository and sort newest first. 3. Render repository, release name, tag, date, and URL as readable Markdown. 4. Cover empty input, missing optional release names, and Markdown-sensitive values with unit tests.',
            'Keep the formatter independent of GitHub API and Actions environment variables.',
            'tools/release-radar/src/format.js; tools/release-radar/test/; Node.js test runner.',
            'Produce a release summary that maintainers can paste into issues, discussions, or workflow summaries.',
            'A deterministic Markdown formatter with focused edge-case tests.',
            'Output is stable for the same input, includes links and tags, handles empty data, and safely formats untrusted release text.',
            'Submit a direct GitHub pull request with formatter tests and a sample output.',
            3,
            'Fácil'
        ),
        (
            'Open Source Release Radar',
            'Publish the digest to the GitHub Actions job summary',
            '["JavaScript","GitHub Actions","Node.js","Testing"]'::jsonb,
            '1. Add an Actions adapter in tools/release-radar/src/summary.js that writes the formatted digest to GITHUB_STEP_SUMMARY. 2. Validate the environment path and report filesystem failures explicitly. 3. Wire the adapter into the action entrypoint. 4. Test the write behavior using a temporary summary file and confirm no secret values appear in output.',
            'Do not overwrite an existing job summary; append content and avoid logging environment secrets.',
            'tools/release-radar/src/summary.js; tools/release-radar/index.js; tools/release-radar/test/.',
            'Make release digests visible directly in a workflow run without requiring a third-party service.',
            'An append-only Actions summary adapter integrated with the action entrypoint.',
            'The adapter appends the digest to the configured file, missing configuration and filesystem errors are explicit, and test output contains no credentials.',
            'Submit a direct GitHub pull request with adapter tests.',
            4,
            'Medio'
        ),
        (
            'Open Source Release Radar',
            'Document a copy-and-run release digest workflow',
            '["GitHub Actions","Git","Documentation"]'::jsonb,
            '1. Add a practical example workflow under examples/release-radar/. 2. Show repository inputs, least-privilege token permissions, schedule/manual triggers, and the generated job summary. 3. Add setup and troubleshooting instructions in tools/release-radar/README.md. 4. Validate YAML and ensure the example does not include a real secret.',
            'Do not request write permissions when read-only repository access is sufficient.',
            'examples/release-radar/; tools/release-radar/README.md; .github/actions/release-radar/action.yml.',
            'Let maintainers adopt the action in a few minutes with safe defaults.',
            'A runnable example workflow and concise installation/troubleshooting guide.',
            'The example uses documented inputs, requests least-privilege permissions, can run manually, and contains no credentials.',
            'Submit a direct GitHub pull request with a validated workflow example.',
            3,
            'Fácil'
        )
)
INSERT INTO public.tasks (
    project_id,
    titulo,
    habilidades_requeridas,
    instrucciones,
    restricciones,
    recursos,
    objetivo,
    entregables,
    criterios_aceptacion,
    modo_entrega,
    duracion_estimada_horas,
    dificultad,
    repositorio_url,
    estado,
    asignado_a,
    module_id,
    review_mode,
    claim_timeout_hours,
    peer_review_timeout_hours,
    creator_review_timeout_hours,
    deadline_at
)
SELECT
    project.id,
    seed.titulo,
    seed.habilidades_requeridas,
    seed.instrucciones,
    seed.restricciones,
    seed.recursos,
    seed.objetivo,
    seed.entregables,
    seed.criterios_aceptacion,
    seed.modo_entrega,
    seed.duracion_estimada_horas,
    seed.dificultad,
    'https://github.com/elspanish/Platform',
    'pendiente',
    NULL,
    NULL,
    'direct',
    168,
    48,
    72,
    NULL
FROM task_seed AS seed
JOIN public.projects AS project
  ON project.titulo = seed.project_title
WHERE NOT EXISTS (
    SELECT 1
    FROM public.tasks AS existing
    WHERE existing.project_id = project.id
      AND existing.titulo = seed.titulo
);

NOTIFY pgrst, 'reload schema';
