# ArNet Backend - Enterprise SaaS AI-First Platform

A production-grade Django backend architecture for ArNet, an Enterprise SaaS AI-First Platform providing multi-tenant B2B Helpdesk, CRM, AI Orchestration, RAG, and Automation capabilities.

## 🏗️ Architecture Overview

This backend follows **enterprise-grade architectural principles** with strict separation of concerns and scalability in mind:

### Core Architectural Layers

```
┌─────────────────────────────────────────────────────────────┐
│                        API Layer                            │
│                (Views, Serializers)                        │
├─────────────────────────────────────────────────────────────┤
│                     Service Layer                           │
│            (Business Logic, Orchestration)                  │
├─────────────────────────────────────────────────────────────┤
│                    Selector Layer                           │
│                (Read-Only Queries)                         │
├─────────────────────────────────────────────────────────────┤
│                     Model Layer                             │
│                  (Data Structure)                          │
├─────────────────────────────────────────────────────────────┤
│                 Infrastructure Layer                        │
│           (Celery, Redis, WebSocket, etc.)                │
└─────────────────────────────────────────────────────────────┘
```

### Multi-Tenancy Strategy

- **Shared Database + org_id scoping**: All tenants share the same database with strict organization-level isolation
- **JWT-based tenant resolution**: Every request carries tenant context in JWT claims
- **Automatic tenant scoping**: Middleware automatically filters data by organization
- **Future-ready for tenant scaling**: Architecture supports evolution to more complex tenancy models

### Key Features

- 🏢 **Multi-Tenant Architecture** with strict data isolation
- 🔐 **JWT Authentication** with tenant claims
- 📊 **Comprehensive Audit Logging** for compliance and security
- 🔧 **ASGI-First** architecture ready for WebSockets and real-time features
- 🎯 **Event-Driven Foundation** prepared for future automation pipelines
- 🚀 **Async Task Processing** with Celery
- 📈 **Performance Optimized** with proper indexing and caching
- 🛡️ **Security-First** design with RBAC foundations

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.12+ (for local development)
- Git

### 1. Clone and Setup

```bash
cd ArNet-Backend-Rizz

# Copy environment configuration
cp .env.example .env

# Edit .env with your settings
nano .env
```

### 2. Start with Docker

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f django

# Run migrations
docker-compose exec django python manage.py migrate

# Create superuser
docker-compose exec django python manage.py createsuperuser

# Collect static files
docker-compose exec django python manage.py collectstatic --noinput
```

### 3. Access the Platform

- **API Documentation**: http://localhost:8000/api/docs/
- **Admin Interface**: http://localhost:8000/admin/
- **Health Check**: http://localhost:8000/health/

## 📁 Project Structure

```
ArNet-Backend-Rizz/
├── apps/                           # Django applications
│   ├── common/                     # Shared models and utilities
│   │   ├── models.py              # Base models (UUID, TimeStamp, TenantAware)
│   │   └── admin.py               # Common admin classes
│   ├── iam/                        # Identity & Access Management
│   │   ├── models.py              # Custom User model
│   │   ├── api/                   # Authentication endpoints
│   │   └── admin.py               # User administration
│   ├── organizations/              # Multi-tenant organization management
│   │   ├── models.py              # Organization model with features/limits
│   │   ├── api/                   # Organization API endpoints
│   │   └── admin.py               # Organization administration
│   └── audit/                      # Audit logging and compliance
│       ├── models.py              # Comprehensive audit trail
│       └── api/                   # Audit log API endpoints
├── core/                           # Django core configuration
│   ├── settings/                   # Environment-specific settings
│   │   ├── base.py                # Shared settings
│   │   ├── local.py               # Development settings
│   │   └── production.py          # Production settings
│   ├── tenancy/                    # Multi-tenant infrastructure
│   │   ├── middleware.py          # Tenant resolution middleware
│   │   └── utils.py               # Tenant utilities and decorators
│   ├── celery.py                  # Celery configuration
│   ├── urls.py                    # URL configuration
│   ├── asgi.py                    # ASGI configuration
│   └── wsgi.py                    # WSGI configuration
├── infrastructure/                 # Infrastructure components
│   ├── celery/                    # Celery task definitions
│   ├── postgres/                  # Database initialization
│   ├── redis/                     # Redis configuration
│   └── websocket/                 # WebSocket routing (future)
├── docker-compose.yml              # Multi-service Docker setup
├── Dockerfile                      # Optimized Python container
├── requirements.txt                # Python dependencies
└── README.md                      # This file
```

## 🔧 Development Setup

### Local Development (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DJANGO_SETTINGS_MODULE=core.settings.local
export DATABASE_URL=postgresql://user:pass@localhost:5432/arnet_dev

# Run migrations
python manage.py migrate

# Start development server
python manage.py runserver
```

### Celery Workers (for background tasks)

```bash
# Start Celery worker
celery -A core.celery worker --loglevel=info

# Start Celery beat (scheduler)
celery -A core.celery beat --loglevel=info

# Monitor with Flower (optional)
pip install flower
celery -A core.celery flower
```

## 🗄️ Database Schema

### Core Models

#### Organization (Tenant)
```sql
organizations:
  - id (UUID, PK)
  - name, slug, display_name
  - subscription_tier (free, starter, professional, enterprise)
  - features (JSON) - feature flags per tier
  - limits (JSON) - usage limits per tier
  - status, is_active
  - created_at, updated_at, deleted_at
```

#### User (Custom Auth)
```sql
users:
  - id (UUID, PK)
  - email (unique, USERNAME_FIELD)
  - organization_id (FK → organizations)
  - first_name, last_name, display_name
  - status (active, inactive, pending, suspended)
  - email_verified, two_factor_enabled
  - preferences (JSON), metadata (JSON)
  - created_at, updated_at, deleted_at
```

#### AuditLog (Compliance)
```sql
audit_logs:
  - id (UUID, PK)
  - organization_id (FK → organizations)
  - actor_user_id (FK → users)
  - action, action_category, outcome
  - entity_type, entity_id, entity_name
  - correlation_id, ip_address, user_agent
  - risk_score, is_sensitive
  - details (JSON), changes (JSON), metadata (JSON)
  - created_at
```

## 🔐 Authentication & Authorization

### JWT Token Structure
```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "org_id": "uuid",
  "org_slug": "acme-corp",
  "org_name": "Acme Corporation",
  "subscription_tier": "professional",
  "role": "admin",
  "features": ["ai_assistant", "advanced_automation"],
  "exp": 1234567890
}
```

### API Endpoints

#### Authentication
- `POST /api/v1/auth/login/` - Login with email/password
- `POST /api/v1/auth/refresh/` - Refresh JWT token
- `POST /api/v1/auth/logout/` - Logout (blacklist token)
- `POST /api/v1/auth/register/` - User registration
- `GET /api/v1/auth/me/` - Current user info

#### Organizations
- `GET /api/v1/organizations/me/` - Current user's organization
- `GET /api/v1/organizations/{id}/features/` - Organization features
- `GET /api/v1/organizations/{id}/usage/` - Usage statistics

#### Audit Logs
- `GET /api/v1/audit/logs/` - List audit logs (tenant-scoped)
- `GET /api/v1/audit/logs/security/` - Security-relevant logs
- `GET /api/v1/audit/logs/high-risk/` - High-risk actions
- `GET /api/v1/audit/logs/statistics/` - Audit statistics

## 🚀 Deployment

### Production Deployment

1. **Environment Setup**
```bash
# Copy and configure production environment
cp .env.example .env.production

# Set production values
DJANGO_SETTINGS_MODULE=core.settings.production
DEBUG=False
SECRET_KEY=your-production-secret-key
ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com
```

2. **Database & Redis**
```bash
# Use managed services or dedicated servers
DATABASE_URL=postgresql://user:pass@db.yourdomain.com:5432/arnet_prod
REDIS_URL=redis://redis.yourdomain.com:6379/0
CELERY_BROKER_URL=redis://redis.yourdomain.com:6379/1
```

3. **Static Files & Media**
```bash
# Configure AWS S3 for production
USE_S3=True
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_STORAGE_BUCKET_NAME=arnet-production-assets
```

4. **Security Configuration**
```bash
# Enable security features
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

### Docker Production

```bash
# Build production image
docker build -t arnet-backend:latest .

# Run with production settings
docker run -d \
  --name arnet-backend \
  -e DJANGO_SETTINGS_MODULE=core.settings.production \
  -e DATABASE_URL=postgresql://... \
  -e REDIS_URL=redis://... \
  -p 8000:8000 \
  arnet-backend:latest
```

## 🧪 Testing

```bash
# Run all tests
python manage.py test

# Run with coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report -m
coverage html  # Generate HTML report
```

## 🔍 Monitoring & Observability

### Health Checks
- **Database**: `GET /health/` - Django health check
- **Celery**: Monitor worker status via Flower
- **Redis**: Connection health via health check endpoints

### Logging
- **Application Logs**: Configured in `core/settings/base.py`
- **Audit Logs**: Comprehensive audit trail in database
- **Celery Logs**: Worker task execution logs

### Metrics (Future Implementation)
- API request metrics
- Database query performance
- Celery task execution metrics
- Organization usage statistics

## 🤝 Contributing

### Code Style
- **Python**: Follow PEP 8, use Black for formatting
- **Django**: Follow Django best practices
- **Architecture**: Maintain strict layer separation

### Development Workflow
1. Create feature branch from `main`
2. Follow the architectural patterns established
3. Add tests for new functionality
4. Update documentation
5. Submit pull request

### Adding New Apps
```bash
# Create new app in apps/ directory
cd apps
python ../manage.py startapp myapp

# Add to INSTALLED_APPS in settings
# Follow the established patterns for:
# - Models (inherit from TenantAwareModel)
# - API (use tenant-aware viewsets)
# - Admin (use TenantAwareAdmin)
```

## 📚 Architecture Deep Dive

### Why This Architecture?

1. **Scalability**: Designed to handle enterprise-scale loads
2. **Maintainability**: Clear separation of concerns and DRY principles
3. **Security**: Multi-layered security with audit trails
4. **Flexibility**: Event-driven foundation for future AI integrations
5. **Compliance**: Built-in audit logging for SOC 2, GDPR, etc.

### Multi-Tenancy Patterns

The platform uses **Shared Database + org_id** pattern because:
- **Cost Effective**: Single database for all tenants
- **Maintenance Friendly**: One schema to manage
- **Performance**: Proper indexing ensures good performance
- **Scalable**: Can evolve to other patterns if needed

### Event-Driven Preparation

While not fully implemented, the architecture prepares for:
- **Domain Events**: Service layer designed for event publishing
- **Automation Pipelines**: Celery tasks can trigger workflows
- **WebSocket Notifications**: ASGI-ready for real-time features
- **AI Orchestration**: Background tasks ready for ML operations

## 📄 License

This project is proprietary to ArNet. All rights reserved.

## 🆘 Support

For questions and support:
- **Documentation**: Check this README and code comments
- **Issues**: Create issues for bugs or feature requests
- **Architecture Questions**: Consult the technical lead

---

**Built with ❤️ for Enterprise SaaS Excellence**