# FastAPI Boilerplate with PostgreSQL and MinIO

A comprehensive FastAPI boilerplate application with PostgreSQL database and MinIO object storage, all containerized with Docker Compose.

## Features

- **FastAPI**: Modern, fast web framework for building APIs
- **PostgreSQL**: Robust relational database
- **MinIO**: S3-compatible object storage
- **SQLAlchemy**: SQL toolkit and ORM
- **Pydantic**: Data validation using Python type annotations
- **Docker Compose**: Easy development environment setup
- **Alembic**: Database migration tool (ready to configure)

## Project Structure

```
├── main.py              # FastAPI application entry point
├── config.py            # Configuration settings
├── database.py          # Database connection and setup
├── models.py            # SQLAlchemy database models
├── schemas.py           # Pydantic schemas for request/response
├── minio_client.py      # MinIO client configuration
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker configuration for FastAPI app
├── docker-compose.yml   # Docker Compose configuration
├── init.sql             # PostgreSQL initialization script
├── .env.example         # Environment variables template
├── .gitignore           # Git ignore rules
└── README.md            # This file
```

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Git (optional, for cloning)

### 1. Environment Setup

Copy the environment template and customize if needed:

```bash
cp .env.example .env
```

### 2. Start Services

Run all services using Docker Compose:

```bash
docker-compose up -d
```

This will start:
- FastAPI application on `http://localhost:8000`
- PostgreSQL database on `localhost:5432`
- MinIO on `http://localhost:9000` (Console: `http://localhost:9001`)
- pgAdmin on `http://localhost:5050`

### 3. Verify Installation

Check if all services are running:

```bash
docker-compose ps
```

Visit the FastAPI documentation at: `http://localhost:8000/docs`

## API Endpoints

### Health Check
- `GET /` - Welcome message
- `GET /health` - Health check endpoint

### User Management
- `POST /users/` - Create a new user
- `GET /users/` - List all users
- `GET /users/{user_id}` - Get user by ID

### Item Management
- `POST /items/` - Create a new item
- `GET /items/` - List all items

### File Management (MinIO)
- `POST /upload/` - Upload a file
- `GET /files/` - List all files
- `GET /files/{filename}` - Get download URL for a file

## Development

### Local Development (without Docker)

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your local database and MinIO settings
```

3. Start PostgreSQL and MinIO locally or use Docker for just these services:
```bash
docker-compose up -d postgres minio
```

4. Run the FastAPI application:
```bash
uvicorn main:app --reload
```

### Database Migrations

This project uses **Alembic** for database migrations. Migrations are automatically handled in the Docker setup.

#### How Migrations Work

1. **Migration Files**: Located in `alembic/versions/` - these contain the SQL commands to modify your database schema
2. **Automatic Setup**: When you run `docker-compose up`, migrations are automatically applied
3. **Version Control**: Each migration has a unique ID and can be applied/rolled back

#### Migration Commands

```bash
# Create a new migration (after modifying models.py)
alembic revision --autogenerate -m "Add new field to user table"

# Apply all pending migrations
alembic upgrade head

# Rollback to previous migration
alembic downgrade -1

# Check current migration status
alembic current

# View migration history
alembic history

# Run migrations manually in Docker
docker-compose run migrate python migrate.py
```

#### Adding New Fields to User Model

1. Modify the `User` model in `models.py`
2. Create a new migration:
   ```bash
   alembic revision --autogenerate -m "Add new field"
   ```
3. Review the generated migration file
4. Apply the migration:
   ```bash
   alembic upgrade head
   ```

#### Migration Best Practices

- Always review generated migration files before applying
- Test migrations on a copy of production data
- Create descriptive migration messages
- Never edit applied migration files
- Use `alembic downgrade` to rollback if needed

## Configuration

### Environment Variables

Key environment variables (see `.env.example`):

- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`
- `SECRET_KEY` - Change this in production!

### MinIO Configuration

Default MinIO credentials:
- Access Key: `minioadmin`
- Secret Key: `minioadmin`
- Console: `http://localhost:9001`

### PostgreSQL Configuration

Default PostgreSQL credentials:
- Username: `postgres`
- Password: `postgres`
- Database: `fastapi_db`

### pgAdmin Configuration

Default pgAdmin credentials:
- Email: `admin@example.com`
- Password: `admin`
- URL: `http://localhost:5050`

## Production Deployment

For production deployment:

1. Change default passwords and secrets
2. Use environment-specific `.env` files
3. Configure proper CORS origins
4. Set up SSL/TLS certificates
5. Use a reverse proxy (nginx)
6. Set up monitoring and logging
7. Configure backup strategies for PostgreSQL and MinIO

## Testing

To run tests (you'll need to add test files):

```bash
pytest
```

## Useful Commands

```bash
# View logs
docker-compose logs -f fastapi-app

# Stop all services
docker-compose down

# Stop and remove volumes (careful - this deletes data!)
docker-compose down -v

# Rebuild and restart
docker-compose up --build -d

# Access PostgreSQL directly
docker-compose exec postgres psql -U postgres -d fastapi_db

# Access MinIO CLI
docker-compose exec minio-client mc ls myminio
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions, please create an issue in the repository.
