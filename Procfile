web: gunicorn health_system.wsgi:application --bind 0.0.0.0:$PORT
worker: python manage.py collectstatic --noinput && python manage.py migrate