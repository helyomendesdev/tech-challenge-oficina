#!/bin/sh
# Entrypoint da aplicacao: decide se gunicorn sobe sob o agente New Relic.
#
# O wrapper e condicional de proposito. O resto do grupo roda esta imagem com
# `docker compose` e nao tem conta New Relic: se `newrelic-admin` fosse
# incondicional, a imagem passaria a exigir credencial que eles nao possuem.

set -e

# Respeita comando explicito (o `command:` do docker-compose, o `command` do Job
# de migration). Descartar "$@" faria o compose subir sem rodar migrate e
# collectstatic, e o banco local levantaria desatualizado sem avisar ninguem.
if [ "$#" -eq 0 ]; then
    set -- gunicorn app.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 60
fi

# So o gunicorn e embrulhado. Embrulhar um `sh -c` instrumentaria o shell, nao a
# aplicacao, e o APM apareceria vazio sem erro nenhum.
if [ "$1" = "gunicorn" ] && [ -n "$NEW_RELIC_LICENSE_KEY" ]; then
    echo "INFO: subindo sob o agente New Relic (NEW_RELIC_LICENSE_KEY presente)"
    exec newrelic-admin run-program "$@"
fi

if [ "$1" = "gunicorn" ]; then
    echo "INFO: subindo sem APM (NEW_RELIC_LICENSE_KEY ausente)"
fi
exec "$@"
