
.DEFAULT_GOAL := help 
help:
	@egrep -h '\s#\s' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?# "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

create-required-network-volumes:
	docker network create postgres_bridge && docker volume create downloads && docker volume create outputs && docker volume create airflowpgdata

connect-to-local-postgres-container:
	docker network connect postgres_bridge nfl_postgres

build-airflow-selenium-images: # build the airflow and selenium images
	docker build -f Dockerfile-airflow -t docker_airflow . && docker build -f Dockerfile-selenium -t docker_selenium .

restart-stack-locally: # restart airflow locally
	docker-compose down && docker-compose up

restart-stack-live: # restart airflow in a live env
	docker-compose down && docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
