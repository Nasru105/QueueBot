from prometheus_client import Counter, start_http_server

# Метрики
queue_joined = Counter('queue_joined_total', 'Users joined the queue', ['chat', 'queue', 'user_name'])
queue_leaved = Counter('queue_leaved_total', 'Users left the queue', ['chat', 'queue', 'user_name'])

# Запуск сервера метрик (Prometheus будет их забирать)
start_http_server(9090)
