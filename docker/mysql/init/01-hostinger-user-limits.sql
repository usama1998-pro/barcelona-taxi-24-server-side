-- Hostinger-style MySQL user resource limits (shared plans).
-- Applied only on first container start (empty mysql_data volume).
-- Reset with: docker compose down -v && docker compose up -d
--
-- To reproduce connection exhaustion faster in local tests, temporarily lower
-- MAX_CONNECTIONS_PER_HOUR (e.g. 20) and rebuild the volume.

ALTER USER 'taxi'@'%' WITH
  MAX_CONNECTIONS_PER_HOUR 500
  MAX_USER_CONNECTIONS 10
  MAX_QUERIES_PER_HOUR 0
  MAX_UPDATES_PER_HOUR 0;

FLUSH PRIVILEGES;
