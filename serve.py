"""Production WSGI entry point. Install requirements-deploy.txt first."""
import os

from app import create_app


if __name__ == '__main__':
    from waitress import serve
    serve(create_app(), host=os.environ.get('BETWEEN_BIND_HOST', '127.0.0.1'),
          port=int(os.environ.get('PORT', '5000')), threads=4)
