from app import create_app
from app.config import get_env_value

app = create_app()

if __name__ == '__main__':
    port = int(get_env_value('SERVER_PORT', 3000))
    app.run(host='0.0.0.0', port=port)
