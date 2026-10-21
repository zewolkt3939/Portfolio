#!/bin/sh
set -eu
psql --set=ON_ERROR_STOP=1 --set=portfolio_password="$PORTFOLIO_DB_PASSWORD" --set=umami_password="$UMAMI_DB_PASSWORD" --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-'SQL'
  CREATE USER portfolio WITH PASSWORD :'portfolio_password';
  CREATE DATABASE portfolio OWNER portfolio;
  CREATE USER umami WITH PASSWORD :'umami_password';
  CREATE DATABASE umami OWNER umami;
SQL
