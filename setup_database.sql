-- =======================================================
--  DATABASE SETUP SCRIPT
--  Run this in PostgreSQL to create the database
-- =======================================================
--
--  How to run this script:
--
--  Option A: Using psql command line
--    psql -U postgres -f setup_database.sql
--
--  Option B: Connect to PostgreSQL first, then run
--    psql -U postgres
--    \i setup_database.sql
--
--  Option C: Use pgAdmin or any PostgreSQL GUI tool
--    Open this file and execute it
--
-- =======================================================

-- Create the database (run as postgres superuser)
CREATE DATABASE docqa;

-- Create the user
CREATE USER docqa WITH PASSWORD 'docqa_password';

-- Grant privileges on database
GRANT ALL PRIVILEGES ON DATABASE docqa TO docqa;

-- Connect to the new database
\c docqa

-- Enable pgvector extension (REQUIRED for vector similarity search)
CREATE EXTENSION IF NOT EXISTS vector;

-- Grant privileges on schema
GRANT ALL ON SCHEMA public TO docqa;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO docqa;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO docqa;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO docqa;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO docqa;

-- Verify setup
\echo '=========================================='
\echo '  Database setup complete!'
\echo '=========================================='
\echo ''
\echo '  Database: docqa'
\echo '  User: docqa'
\echo '  Password: docqa_password'
\echo '  pgvector: enabled'
\echo ''
\echo '  You can now run the application:'
\echo '  python run.py'
\echo ''
\echo '=========================================='
