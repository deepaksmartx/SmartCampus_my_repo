-- If creating a user with role "Security" fails on PostgreSQL with an enum error,
-- your DB has a native ENUM for roles that predates Security. Add the value (type name is often `userrole`):

ALTER TYPE userrole ADD VALUE 'Security';

-- If the type name is wrong, list enums: SELECT typname FROM pg_type WHERE typtype = 'e';
