import os
from airflow.models import Variable
from airflow.models.connection import Connection
from datetime import timedelta, datetime
from utils.helper import (
    ExtendedPythonOperator,
)
from airflow.operators.dummy_operator import DummyOperator
from airflow.models import DAG
from plugins.selenium_plugin.operators.selenium_operator import SeleniumOperator
# from airflow_dbt.operators.dbt_operator import DbtRunOperator, DbtTestOperator
from airflow.operators.bash_operator import BashOperator
# from airflow.operators.delete_files_plugin import DeleteFolderContentsOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
# from airflow.operators.postgres_operator import BulkCSVLoadOperator, BulkViewDumpOperator
import pendulum
from draftkings_nfl.ingestion.selenium.selenium_download import download_nfl_wrapper
from draftkings_nfl.ingestion.plugins.ingestor import run_preprocess_data_and_insert_db


# specify local timezon
local_tz = pendulum.timezone("Europe/London")

# global variables
DAG_CONFIG = Variable.get("base_config", deserialize_json=True)
AIRFLOW_HOME = os.getenv("AIRFLOW_HOME")
# DAG default args
DEFAULT_ARGS = {
    "owner": "feng_tian",
    "start_date": datetime.now(tz=local_tz),
    "retries": 2,
    "retries_delay": timedelta(minutes=2),
}
# specify dag to run any intervals that have not been run since last execution
CATCHUP = False


def create_bronze_nfl_dag(
    dag_id: str,
    config: dict,
    schedule: str,
    airflow_home: str,
    catchup: bool,
    default_args: dict,
):
    """Create nfl dag

    Args:
        dag_id (str): unique name for dag
        config (dict): dictionary of variables for dag
        schedule (str): airflow schedule string
        airflow_home (str): airflow home path
        mlflow_tracking_uri (string): connection uri for mlflow
        catchup (bool): run any intervals that have not been run since last execution
        default_args (dict): default args for dag
    Returns:
        airflow dag
    """

    dag = DAG(
        dag_id, schedule_interval=schedule, catchup=catchup, default_args=default_args
    )
    # variables for dag
    local_downloads = os.path.join(airflow_home, "downloads", dag_id)
    local_outputs = os.path.join(airflow_home, "outputs", dag_id)

    selenium_download_path = os.path.join("/home/seluser/downloads", dag_id)
    execution_date_as_datetime = (
        '{{ dag.timezone.convert(execution_date).strftime("%Y%m%dT%H%M%S") }}'
    )
    url_config = config['url_config']
    
    query_year_range = config.get("query_year_range", "")
    if query_year_range:
        y1, y2 = map(int, query_year_range.split('-'))
        query_year_range = list(range(y1, y2+1, 1))
    else: 
        query_year_range = [datetime.now().year-1]


    with dag:

        # dummy task to specify start of dag
        start = DummyOperator(task_id="start")

        # bash operator to make client directory if it doesnt exist
        make_client_dir = BashOperator(
            task_id="make_client_dir",
            bash_command='mkdir -p "{{ params.local_downloads }}" "{{ params.local_outputs }}"',
            params={"local_downloads": local_downloads, "local_outputs": local_outputs},
        )

        # selenium operator to download pro-football-reference data and preprocess
        get_web_content = SeleniumOperator(
            selenium_address="airflow_selenium",
            container_download_path=selenium_download_path,
            script=download_nfl_wrapper,
            script_args=[
                dag_id,
                config['query_target'],
                local_downloads,
                query_year_range,
                config['query_team_name'],
                url_config
            ],
            task_id="get_web_content",
        )

        # preprocess data and save to disk
        data_preprocess = ExtendedPythonOperator(
            python_callable=run_preprocess_data_and_insert_db,
            op_kwargs={
                "file_dir": local_downloads,
                "query_target": client,
                "output_file_name": target_file_name,
                "postgres_conn_id": config["postgres_conn_id"],
                "headers": config['preprocessing_config']["headers"],
                "skip_rows": 0,
            },
            task_id="data_preprocess",
        )

        # # upload pro-football-reference data to s3
        # upload_data_s3 = ExtendedPythonOperator(
        #     python_callable=upload_file_to_S3,
        #     op_kwargs={
        #         "aws_conn_id": config["aws_conn_id"],
        #         "file_path": os.path.join(local_downloads, target_file_name + ".csv"),
        #         "key": os.path.join(dag_id, target_file_name + ".csv"),
        #         "bucket_name": config["s3_bucket"],
        #     },
        #     task_id="upload_data_s3",
        # )
        create_bronze_schema = PostgresOperator(
        task_id="create_bronze_schema",
        sql="""
            CREATE SCHEMA IF NOT EXISTS pet (
            pet_id SERIAL PRIMARY KEY,
            name VARCHAR NOT NULL,
            pet_type VARCHAR NOT NULL,
            birth_date DATE NOT NULL,
            OWNER VARCHAR NOT NULL);
          """,
    )

        # insert data into database
        insert_data_db = BulkCSVLoadOperator(
            postgres_conn_id=config["postgres_conn_id"],
            postgres_table=config["postgres_table"],
            postgres_schema=config["postgres_schema"],
            file_name=target_file_name + "_processed.csv",
            selected_columns=config["selected_columns"],
            primary_key=eval(config["primary_key"]),
            local_path=local_downloads,
            truncate=False,
            task_id="insert_data_db",
            retries=0,
        )

        # # bash operator to install dbt utils
        # dbt_deps = BashOperator(
        #     task_id="dbt_deps",
        #     bash_command="cd {{ params.airflow_home }}/nfl-dbt && dbt deps",
        #     params={"airflow_home": airflow_home},
        # )

        # # dbt run command
        # dbt_run = DbtRunOperator(
        #     task_id="dbt_run",
        #     full_refresh=eval(config["dbt_full_refresh"]),
        #     target=config["dbt_target"],
        #     vars=config["dbt_vars"],
        #     models=config["dbt_models"],
        #     exclude=config["dbt_exclude"],
        #     verbose=eval(config["dbt_verbose"]),
        #     dir=os.path.join(airflow_home, "nfl-dbt"),
        # )

        # # dbt test command
        # dbt_test = DbtTestOperator(
        #     task_id="dbt_test",
        #     target=config["dbt_target"],
        #     vars=config["dbt_vars"],
        #     models=config["dbt_models"],
        #     exclude=config["dbt_exclude"],
        #     verbose=eval(config["dbt_verbose"]),
        #     dir=os.path.join(airflow_home, "nfl-dbt"),
        #     retries=0,
        # )

        # delete local files
        # delete_local_files = DeleteFolderContentsOperator(
        #     dir_path=local_downloads, task_id="delete_local_files"
        # )

        # dummy task to mark the end of the dag
        end = DummyOperator(task_id="end")

        # set task dependencies
        (
            start
            >> make_client_dir
            >> get_web_content
            >> data_preprocess
            # >> [
            #     # upload_data_s3,
            #     insert_data_db,
            # ]
            # >> delete_local_files
            >> end
        )

        # dynamically add tasks to save reporting tables
        reporting_table_tasks_list = []
        # for table_name, params in config["reporting_tables"].items():
        #     reporting_table = BulkViewDumpOperator(
        #         postgres_conn_id=config["postgres_conn_id"],
        #         postgres_table=table_name,
        #         postgres_schema=params["postgres_schema"],
        #         file_name=table_name + ".csv",
        #         local_path=local_outputs,
        #         task_id="save_" + table_name + "_table",
        #     )
        #     reporting_table_tasks_list.append(reporting_table)
        # delete_local_files >> reporting_table_tasks_list >> end

    return dag

GLOBAL_DETAILS = DAG_CONFIG['global_details']
BRONZE_CONFIG = DAG_CONFIG['bronze_layer']

# dynamically create dags based on keys in `base_config` airflow variable
for config in BRONZE_CONFIG['datasets']:
    client = config["query_target"]
    # specify hour scheduler for dag
    schedule = config["cron_scheduler"]
    # https://www.pro-football-reference.com/ updates stats 
    # by 6pm on the Tuesday following the week's games.

    # create dag dynamically
    globals()[client] = create_bronze_nfl_dag(
        client,
        config,
        schedule,
        AIRFLOW_HOME,
        CATCHUP,
        DEFAULT_ARGS,
    )
