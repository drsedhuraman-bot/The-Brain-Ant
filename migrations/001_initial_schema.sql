-- Enable UUID generation
create extension if not exists "pgcrypto";

-- Sessions: top-level conversation containers
create table if not exists sessions (
    id          uuid primary key default gen_random_uuid(),
    title       text not null default 'New Session',
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now(),
    metadata    jsonb not null default '{}'
);

-- Tasks: a single user request within a session
create table if not exists tasks (
    id           uuid primary key default gen_random_uuid(),
    session_id   uuid not null references sessions(id) on delete cascade,
    user_input   text not null,
    status       text not null default 'pending'
                     check (status in ('pending','running','completed','failed')),
    result       text,
    error        text,
    created_at   timestamptz not null default now(),
    completed_at timestamptz
);

create index if not exists tasks_session_id_idx on tasks(session_id);
create index if not exists tasks_status_idx on tasks(status);

-- Agent runs: one record per Ant invocation within a task
create table if not exists agent_runs (
    id              uuid primary key default gen_random_uuid(),
    task_id         uuid not null references tasks(id) on delete cascade,
    ant_type        text not null
                        check (ant_type in ('brain','research','coder','writer','analyst')),
    input_summary   text not null,
    output_summary  text,
    status          text not null default 'pending'
                        check (status in ('pending','running','completed','failed')),
    tokens_used     integer not null default 0,
    started_at      timestamptz not null default now(),
    completed_at    timestamptz
);

create index if not exists agent_runs_task_id_idx on agent_runs(task_id);

-- Messages: full conversation history for replay and context
create table if not exists messages (
    id          uuid primary key default gen_random_uuid(),
    session_id  uuid not null references sessions(id) on delete cascade,
    task_id     uuid references tasks(id) on delete set null,
    role        text not null check (role in ('user','assistant','ant_trace')),
    content     text not null,
    ant_type    text check (ant_type in ('brain','research','coder','writer','analyst')),
    created_at  timestamptz not null default now()
);

create index if not exists messages_session_id_idx on messages(session_id);
create index if not exists messages_task_id_idx on messages(task_id);

-- Row Level Security
alter table sessions enable row level security;
alter table tasks enable row level security;
alter table agent_runs enable row level security;
alter table messages enable row level security;

-- Service role bypass
do $$ begin
  if not exists (select 1 from pg_policies where tablename='sessions' and policyname='service_role_all_sessions') then
    create policy "service_role_all_sessions" on sessions for all using (true);
  end if;
  if not exists (select 1 from pg_policies where tablename='tasks' and policyname='service_role_all_tasks') then
    create policy "service_role_all_tasks" on tasks for all using (true);
  end if;
  if not exists (select 1 from pg_policies where tablename='agent_runs' and policyname='service_role_all_runs') then
    create policy "service_role_all_runs" on agent_runs for all using (true);
  end if;
  if not exists (select 1 from pg_policies where tablename='messages' and policyname='service_role_all_messages') then
    create policy "service_role_all_messages" on messages for all using (true);
  end if;
end $$;

-- Trigger: keep sessions.updated_at fresh
create or replace function update_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end;
$$;

drop trigger if exists sessions_updated_at on sessions;
create trigger sessions_updated_at
    before update on sessions
    for each row execute function update_updated_at();
