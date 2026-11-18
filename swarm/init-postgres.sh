#!/bin/sh
set -eu
APP_PASSWORD=$(cat /run/secrets/db_password)
psql --username "$POSTGRES_USER" --dbname postgres -v ON_ERROR_STOP=1 --set=app_password="$APP_PASSWORD" <<'SQL'
CREATE ROLE foodgo_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
CREATE DATABASE foodgo_usuarios OWNER foodgo_app ENCODING 'UTF8';
CREATE DATABASE foodgo_restaurantes OWNER foodgo_app ENCODING 'UTF8';
CREATE DATABASE foodgo_pedidos OWNER foodgo_app ENCODING 'UTF8';
CREATE DATABASE foodgo_pagos OWNER foodgo_app ENCODING 'UTF8';
CREATE DATABASE foodgo_delivery OWNER foodgo_app ENCODING 'UTF8';
CREATE DATABASE foodgo_notificaciones OWNER foodgo_app ENCODING 'UTF8';
CREATE DATABASE foodgo_cupones OWNER foodgo_app ENCODING 'UTF8';
CREATE DATABASE foodgo_resenas OWNER foodgo_app ENCODING 'UTF8';
SQL
unset APP_PASSWORD
