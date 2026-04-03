# Deployment Guide

This guide provides instructions for deploying the Django application to a production environment.

## 1. Prerequisites

*   A server with Python and Poetry installed.
*   A PostgreSQL database.
*   A web server (e.g., Nginx).
*   A process manager (e.g., Gunicorn).

## 2. Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/your-repo.git
    cd your-repo
    ```

2.  **Create and populate the `.env` file:**
    ```bash
    cp backend/.env.example backend/.env
    ```
    Then, edit the `backend/.env` file with your production settings.

3.  **Install dependencies:**
    ```bash
    poetry install --no-dev
    ```

4.  **Run database migrations:**
    ```bash
    poetry run python backend/manage.py migrate
    ```

5.  **Collect static files:**
    ```bash
    poetry run python backend/manage.py collectstatic
    ```

## 3. Gunicorn

The `gunicorn.conf.py` file contains the Gunicorn configuration. You can start the Gunicorn server with the following command:

```bash
poetry run gunicorn --config deployment/gunicorn.conf.py config.wsgi
```

The `gunicorn.service` file is a sample systemd service file that you can use to run Gunicorn as a service.

## 4. Nginx

You should configure Nginx as a reverse proxy to forward requests to Gunicorn. Here is a sample Nginx configuration:

```nginx
server {
    listen 80;
    server_name your_domain.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    location /static/ {
        root /path/to/your/project/backend;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
