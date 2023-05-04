# Selenium on Airflow

- [Selenium on Airflow](#selenium-on-airflow)
  - [Summary](#summary)
  - [Design](#design)
  - [Quick Start](#quick-start)
    - [Initial configuration](#initial-configuration)
    - [Configure your environment variables](#configure-your-environment-variables)
    - [Start your Docker containers](#start-your-docker-containers)
    - [Create an airflow user](#create-an-airflow-user)
    - [Configure airflow variables](#configure-airflow-variables)
    - [Configure airflow connections](#configure-airflow-connections)
  - [Architecture](#architecture)
  - [Structure](#structure)

## Summary

The purpose of this repo is to use the Selenium web driver to automate tasks on the web, in a Dockerised airflow environment.

## Design 

<details>
    <summary> Show/Hide Details</summary>

The overall Airflow Dag can be viewed below:
    ![Airflow DAG](../nfl-application/images/Airflow-Workflow.drawio.png)

A summary of the overall system design including airflow, postgres and dash app, can be viewed below:
    ![System Design](../nfl-application/images/Local-system-design.drawio.png)

</details>

## Quick Start

### Initial configuration
1. Create the required Docker network to enable the containers to communicate AND the following named volumes.

    `create-required-network-volumes`

    - `downloads` - used to persist downloaded data from pro-football-references

    - `outputs` - used to persist outputs of cleaned data

    - `airflowpgdata` - used to persist airflow postgres data

2. If running locally connect the Docker network to the postgres container used for nfl i.e. `nfl_postgres`. Make sure the `nfl_postgres` container is running first:
   
    `make connect-to-local-postgres-container`

3. Currently nfl-application is not a submodule of nfl-airflow yet but with integration on Github it will be. 

</details>

### Configure your environment variables


1. Set up your .env file in the home folder of this repo i.e. in the same folder as the README.md and ensure it contains the following variables:

    ```
    AIRFLOW_UID=501
    AIRFLOW_GID=0
    ```


### Start your Docker containers


1. Build and run docker compose to start all necessary containers, mainly airflow and selenium:

    There is a convenient [Makefile](Makefile) which should take care of the build.

    To build the images run `make build-airflow-selenium-images`

    In production run:

    `make restart-stack-live`

    Locally run:

    `make restart-stack-locally`


After entering the above command you should see the following containers by running `docker ps` or `docker container ls

Notes:
* More information about the purpose of each container is available in the [Architecture section](#architecture) of this repo
* The airflow webserver will be available at `localhost:8080`


### Create an airflow user

Run the following script in the docker container e.g `airflow_worker` and update `username`, `email` and `password`.

```
python
import airflow
from airflow import models, settings
from airflow.contrib.auth.backends.password_auth import PasswordUser
from sqlalchemy import create_engine
user = PasswordUser(models.User())
user.username = 'airflow'
user.password = 'airflow'
user.email = ''
# Set the value as either False / True depending if you want the user to be an admin
user.superuser = True
engine = create_engine("postgresql://airflow:airflow@postgres:5432/airflow")
session = settings.Session(bind=engine)
session.add(user)
session.commit()
session.close()
exit()
```

### Configure airflow variables


1. On the airflow webserver add a json variable named [base_config](nfl-airflow/nfl-application/config/base_config.json)
```json
{
    "global_details": {
        "postgres_conn_id": "postgres_default",
        "scraping_start_year": "2022",
        "scraping_end_year": "2023",
        "scheduler": "*/3 6-7 * * 2"
    },
    "credentials":{},
    "bronze_layer": {
        "bronze_destination_url": "/mnt/deltalake/bronze",
        "datasets": [
            {
                "query_target": "games",
                "url_config": {
                    "url": "www.pro-football-reference.com/years/{year}/games.htm",
                    "table_id": "games"
                },
                "query_year": "2022",
                "query_year_range": "2019-2022",
                "query_team_name": "test",
                "primary_key": "True",
                "preprocessing_config": {
                    "headers": [0]
                },
                "cron_scheduler": "*/3 6-7 * * 2"
                
        },
        {
            "query_target": "all_teams",
            "url_config": {
                "url": "www.pro-football-reference.com/teams/",
                "table_id": "teams_active"
            },
            "query_year": "",
            "query_team_name": "",
            "primary_key": "True",
            "preprocessing_config": {
                "headers": [
                    0,1
                ]
            },
            "cron_scheduler": "*/3 6-7 * * 2"
        }
    ]
    },
    "silver_layer": {},
    "gold_layer": {},
    "machine_learning": {}
}
```

Example airflow variables:

*Definition of keys passed to the airflow variable:*

| Variable           | Definition                                                                                              |
| ------------------ | ------------------------------------------------------------------------------------------------------- |
| bronze_layer    | Parameters to config how scraper and ingestion will be run|
| postgres_conn_id   | Postgres connnection ID in airflow|
| scheduler   | Specify cronjob when the DAG should be triggered to start                       |
| datasets   | Specify which data to scrape from the website                       |
|query_year_range| dynamically scrape data between two years|
|url_config|query target base url, replace year or team name with `{year}`, `{team_name}` to enable dynamic query|
|url_config|query target base url, replace year or team name with `{year}`, `{team_name}`, `table_id` can be found via Inspect function on Google Chrome at target table source html code|



### Configure airflow connections

**Example airflow connections:**
    
1.  **Update the postgres connection named `postgres_default`:**
![Postgres Connection](images/Screenshot%202023-04-27%20at%2009.20.11.png)

Notes:

- Keep the `Conn Id` and `Type` as is and update `Host`, `Schema`, `Login` and `Password` with your postgres details.
- Note if running locally use `nfl_postgres` as the host. Alternatively use the server address.
- This connection is required to insert the scraped data into the postgres database.



## Architecture

This repo makes use of the following tech stack:
1. `Airflow` for orchestrating tasks
2. `Selenium web driver` to automate tasks on the web

All applications are packaged up using `Docker` to isolate the software from its env so that it works in different development environments. We also make use of the docker compose tool to define and run multiple Docker container applications.

`Airflow` consist of several components:

 * `Workers` - Execute the assigned tasks
 * `Scheduler` - Responsible for adding the necessary tasks to the queue
 * `Web server` - HTTP Server provides access to DAG/task status information
 * `Postgres Database` - Contains information about the status of tasks, DAGs, Variables, connections, etc.
 * `Celery` - Queue mechanism and enables multiple tasks to run in parallel
## Structure

```
├── Dockerfile-airflow            <-  extends the airflow image
├── Dockerfile-selenium           <- extends the selenium image
├── Dockerfile-selenium           <- convenient file to build images and restart containers
├── README.md                     <- repo documentation
├── nfl-application                  <- nfl-application submodule
├── dags                          <- airflow dags
│   └── nfl_dag.py                 <- example dag to download data with selenium and run ingestion tasks
├── config                        <- airflow configuration directory
│   └── airflow.cfg                 <- config file for airflow
├── docker-compose.yml            <- defines multiple docker containers
├── docker-compose.prod.yml       <- yaml file for running containers in production
├── plugins                       <- airflow plugins
│   └── selenium_plugin                 <- plugin to create a selenium operator
└── utils                         <- utility functions and classes
    ├── __init__.py
    └── helper.py                       <- helper functions and classes for airflow tasks
```

