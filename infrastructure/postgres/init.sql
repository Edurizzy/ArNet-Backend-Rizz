-- PostgreSQL initialization script for ArNet
-- This script sets up the database with necessary extensions

-- Create the database if it doesn't exist
-- (This is handled by Docker, but kept for reference)

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Enable vector extension for future AI/RAG functionality
-- This extension is provided by the pgvector/pgvector image
CREATE EXTENSION IF NOT EXISTS "vector";

-- Create a schema for storing vector embeddings (future use)
CREATE SCHEMA IF NOT EXISTS embeddings;

-- Grant permissions to the application user
-- (User creation is handled by Docker environment variables)

-- You can add additional database setup here as needed