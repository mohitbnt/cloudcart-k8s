# CloudCart

CloudCart is a production-style containerized retail application used as the application layer for the Docker, Kubernetes, AWS EKS, Terraform, CI/CD, observability, and GitOps work.

## Architecture

```text
Browser
  |
  v
Cloudflare
  |
  +----------------------------+
  |                            |
  v                            v
Frontend                   API Gateway
Nginx                      (future public API endpoint)
  |                            |
  | /api/*                     +--> Catalog
  v                            +--> Identity
API Gateway                    +--> Cart
                               +--> Order
                               +--> Inventory
                               +--> Payment
                               +--> Notification

PostgreSQL: durable business data
Redis: sessions and shopping carts
```

The intended AWS/EKS public architecture is:

```text
Internet
   |
   v
Cloudflare DNS
   |
   +------------------------------+
   |                              |
   v                              v
shop.cloudsystemonline.com   api.cloudsystemonline.com
   |                              |
   +------------+-----------------+
                |
                v
        AWS Application Load Balancer
                |
                v
              EKS
                |
        +-------+-------+
        |               |
   Frontend         API Gateway
                        |
          +-------------+-------------+
          |      |      |      |      |
       Catalog Identity Cart  Order  ...
```

Cloudflare is the DNS/edge provider. Route 53 is not part of the planned architecture, and NAT Gateway is not used in the planned VPC design.

The frontend is plain HTML/CSS/JavaScript and is intentionally kept dependency-free. Nginx serves the static frontend and, in Docker Compose, proxies `/api/` requests to the Gateway.

## Configuration model

CloudCart follows an **environment-driven configuration model**. Application code does not hardcode Docker, Kubernetes, or production service endpoints.

The same application image can therefore be promoted through environments without rebuilding the image just because a service endpoint changes.

### Docker Compose

For the current Docker Compose deployment, one `.env` file is supplied to the services through `env_file`.

The Compose file uses the same `.env` for convenience, while each application reads only the variables it needs.

Examples:

```env
DATABASE_URL=postgresql+psycopg://cloudcart:<password>@postgres:5432/cloudcart
REDIS_URL=redis://redis:6379/0
CATALOG_URL=http://catalog:8000
IDENTITY_URL=http://identity:8000
INVENTORY_URL=http://inventory:8000
PAYMENT_URL=http://payment:8000
API_BASE=/api
```

Docker Compose provides DNS names such as `postgres`, `redis`, `catalog`, and `identity` through the Compose network.

### Kubernetes / EKS

Kubernetes will use a more structured configuration model:

```text
                    Kubernetes
                        |
              +---------+---------+
              |                   |
         ConfigMap             Secret
              |                   |
       non-sensitive          sensitive values
       configuration
              |                   |
              +---------+---------+
                        |
                        v
                   Deployment
                        |
                        v
                     Pod/Container
```

We will **not copy the entire `.env` file into every Kubernetes Deployment**.

Instead, each Deployment will explicitly receive the variables required by that application, using `env`, `envFrom`, `configMapKeyRef`, and/or `secretKeyRef` as appropriate.

For example, the Catalog Deployment may receive only:

```yaml
env:
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: cloudcart-database
        key: database-url
```

The Order Deployment may receive:

```yaml
env:
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: cloudcart-database
        key: database-url
  - name: INVENTORY_URL
    value: http://inventory:8000
  - name: PAYMENT_URL
    value: http://payment:8000
```

The exact Kubernetes Service names and configuration will be defined during the Kubernetes phase.

This gives us three important properties:

1. **Secrets remain in Kubernetes Secrets rather than ordinary ConfigMaps.**
2. **Each workload receives only the configuration it needs.**
3. **The same container image can run in Docker, local Kubernetes, and EKS with environment-specific configuration.**

## Environment variable reference

| Variable | Purpose | Current Docker Compose consumer(s) |
|---|---|---|
| `POSTGRES_USER` | PostgreSQL username | `postgres` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `postgres` and database-backed application configuration |
| `POSTGRES_DB` | PostgreSQL database name | `postgres` |
| `POSTGRES_PORT` | PostgreSQL port reference | Configuration |
| `DATABASE_URL` | SQLAlchemy PostgreSQL connection URL | `catalog`, `identity`, `inventory`, `order`, `payment`, `notification` |
| `REDIS_URL` | Redis connection URL | `identity`, `cart` |
| `CATALOG_URL` | Catalog service endpoint | `gateway` |
| `IDENTITY_URL` | Identity service endpoint | `gateway` |
| `CART_URL` | Cart service endpoint | `gateway` |
| `ORDER_URL` | Order service endpoint | `gateway` |
| `INVENTORY_URL` | Inventory service endpoint | `order` |
| `PAYMENT_URL` | Payment service endpoint | `order` |
| `NOTIFICATION_URL` | Notification service endpoint | `gateway` |
| `SESSION_TTL_SECONDS` | Redis session lifetime in seconds | `identity` |
| `SESSION_COOKIE_NAME` | Browser session cookie name | `identity` |
| `SESSION_COOKIE_SECURE` | Whether the session cookie requires HTTPS | `identity` |
| `ENVIRONMENT` | Application environment identifier | Services that read it |
| `API_BASE` | Browser-facing API base URL | `frontend` |
| `ALLOWED_ORIGINS` | Allowed credentialed browser origins for CORS | `gateway` |

### Configuration categories

The variables can also be viewed in four groups:

#### Database configuration

```env
POSTGRES_USER=...
POSTGRES_PASSWORD=...
POSTGRES_DB=...
POSTGRES_PORT=5432
DATABASE_URL=...
```

`POSTGRES_PASSWORD` is sensitive and should be treated as a secret. `DATABASE_URL` may also contain the database password and therefore should be treated as sensitive.

#### Redis and session configuration

```env
REDIS_URL=...
SESSION_TTL_SECONDS=86400
SESSION_COOKIE_NAME=cloudcart_session
SESSION_COOKIE_SECURE=false
```

`REDIS_URL` can contain credentials in a future deployment and should then be treated as sensitive.

#### Service discovery configuration

```env
CATALOG_URL=...
IDENTITY_URL=...
CART_URL=...
ORDER_URL=...
INVENTORY_URL=...
PAYMENT_URL=...
NOTIFICATION_URL=...
```

These are environment-specific service endpoints. Docker Compose uses Compose service names; Kubernetes will use Kubernetes Service DNS names.

#### Frontend and CORS configuration

```env
API_BASE=/api
ALLOWED_ORIGINS=...
```

For Docker Compose, `API_BASE=/api` makes the browser use the Nginx reverse proxy in front of the Gateway.

For the future production deployment, the API base will be supplied through deployment configuration rather than being hardcoded into frontend application code.

## Authentication

Identity stores users in PostgreSQL and sessions in Redis. The browser receives only the `cloudcart_session` HttpOnly cookie.

Endpoints:

```text
POST /identity/register
POST /identity/login
GET  /identity/me
POST /identity/logout
```

The default demo account is created automatically:

```text
Email:    demo@example.com
Password: demo123
```

Registration creates the user and signs them in immediately.

## Cart

The browser-facing cart API uses the session cookie instead of exposing the Redis session ID to JavaScript:

```text
GET    /cart
POST   /cart/items
PATCH  /cart/items/{product_id}
DELETE /cart/items/{product_id}
DELETE /cart
```

The older session-ID routes are retained for backend testing compatibility.

## Docker Compose

### Environment file

Create the local environment file from the example:

```bash
cp .env.example .env
```

Set a strong PostgreSQL password and make sure it matches the password used by `DATABASE_URL`.

Do not commit `.env` to Git. Commit only `.env.example` with placeholder values.

### Validate configuration

```bash
docker compose -f compose.production.yaml config
```

### Build and start

```bash
docker compose -f compose.production.yaml up --build -d
```

### Check containers

```bash
docker compose -f compose.production.yaml ps
```

Only the frontend and Gateway are published to the Docker host:

```text
Frontend -> 8080
Gateway  -> 8000
```

The following remain internal to the Compose network:

```text
catalog
identity
cart
inventory
order
payment
notification
postgres
redis
```

### Open the storefront

```text
http://DOCKER_HOST_IP:8080
```

### Gateway health

```bash
curl http://localhost:8000/health
```

### Catalog through the frontend Nginx proxy

```bash
curl http://localhost:8080/api/catalog/products
```

## Docker Compose to Kubernetes configuration mapping

The configuration model intentionally changes between Compose and Kubernetes.

### Docker Compose

```text
.env
  |
  +--> postgres
  +--> catalog
  +--> identity
  +--> inventory
  +--> order
  +--> payment
  +--> notification
  +--> cart
  +--> gateway
```

This is convenient for a single-host learning/development environment.

### Kubernetes

```text
                    ConfigMap
                       |
                       | non-sensitive configuration
                       v
                 +-------------+
                 | Deployment  |
                 +-------------+
                       ^
                       |
                    Secret
                       |
                       | sensitive configuration
                       |
                       +----------------+
                                        |
                                        v
                                   Pod/Container
```

More precisely, each Deployment will define the configuration required by its own container.

For example:

```text
catalog Deployment
  └── DATABASE_URL

identity Deployment
  ├── DATABASE_URL
  ├── REDIS_URL
  ├── SESSION_TTL_SECONDS
  ├── SESSION_COOKIE_NAME
  └── SESSION_COOKIE_SECURE

order Deployment
  ├── DATABASE_URL
  ├── INVENTORY_URL
  └── PAYMENT_URL

gateway Deployment
  ├── CATALOG_URL
  ├── IDENTITY_URL
  ├── CART_URL
  ├── ORDER_URL
  ├── NOTIFICATION_URL
  └── ALLOWED_ORIGINS

frontend Deployment
  └── API_BASE
```

The exact Secret/ConfigMap split and Kubernetes manifests will be created during the Kubernetes phase.

## Container image strategy

The application consists of these custom images:

```text
catalog
identity
cart
inventory
order
payment
notification
gateway
frontend
```

PostgreSQL and Redis use their upstream public images and are not built as CloudCart application images.

The application images are designed to be environment-independent. Environment-specific configuration is injected at runtime.

For ECR Public, immutable version tags should be preferred over relying on `latest`, for example:

```text
cloudcart/catalog:1.0.0
cloudcart/identity:1.0.0
cloudcart/cart:1.0.0
...
```

Kubernetes can then reference the same image version while supplying different environment configuration through ConfigMaps, Secrets, and Deployment manifests.

## Kubernetes migration principle

The Docker Compose deployment is intentionally simple:

```text
Single .env
      |
      v
Docker Compose
      |
      v
Containers
```

The Kubernetes deployment will be more granular:

```text
                     Git repository
                           |
                  Kubernetes manifests
                           |
             +-------------+-------------+
             |                           |
          ConfigMaps                  Secrets
             |                           |
             +-------------+-------------+
                           |
                      Deployments
                           |
                           v
                         Pods
```

The application code and container images should not need to change simply because:

```text
Docker Compose
      ->
Local Kubernetes
      ->
AWS EKS
```

The deployment configuration changes; the application image remains the same.

## Stop

```bash
docker compose -f compose.production.yaml down
```

Do not use `-v` unless you intentionally want to delete the PostgreSQL and Redis volumes.
