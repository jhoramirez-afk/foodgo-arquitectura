-- Ejecutar en la base foodgo_usuarios del PostgreSQL Docker local de Usuarios.
-- pgAdmin: host 127.0.0.1, puerto 54321, usuario foodgo_ep02.
-- Son consultas de lectura. El CRUD se realiza por HTTP en Postman.
SELECT current_database() AS base, current_user AS usuario, inet_server_port() AS puerto_interno, version() AS version_postgresql;

SELECT table_name AS tabla FROM information_schema.tables
WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name;

SELECT u.id AS usuario_id, u.nombre, u.email, d.id AS direccion_id,
       d.alias, d.calle, d.comuna, d.usuario_id AS clave_foranea
FROM public.usuarios u LEFT JOIN public.direcciones d ON d.usuario_id=u.id
WHERE lower(u.email)='valentina.rojas@example.com'
ORDER BY u.id,d.id;

SELECT tc.table_name AS tabla, tc.constraint_type AS restriccion, kcu.column_name AS columna
FROM information_schema.table_constraints tc
LEFT JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name=kcu.constraint_name AND tc.constraint_schema=kcu.constraint_schema
WHERE tc.table_schema='public' AND tc.table_name IN ('usuarios','direcciones')
ORDER BY tc.table_name,tc.constraint_type,kcu.column_name;
