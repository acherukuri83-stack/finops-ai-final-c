-- W1 PR2 fills this with the full schema (see docs/issues/W1-foundation-data-tools.md).
create extension if not exists vector;
create table if not exists schema_marker (id int primary key, note text);
insert into schema_marker values (1, 'finops enterprise schema v1 placeholder') on conflict do nothing;
