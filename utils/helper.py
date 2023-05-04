"""This module is for custom helper airflow classes and functions"""

from datetime import datetime
from airflow.operators.python_operator import PythonOperator
from airflow.hooks.S3_hook import S3Hook
import logging
from airflow.hooks.base_hook import BaseHook
from airflow.contrib.operators.slack_webhook_operator import SlackWebhookOperator


def task_fail_slack_alert(context):
    """Create an airflow task to send an alert to slack when a task fails
    This uses `SlackWebhookOperator` and is passed to the default args for
    `on_failure_callback`.

    Note: this function should only have one variable i.e the dag context
    """
    # get slack webhook token
    slack_webhook_token = BaseHook.get_connection("slack").password

    # context vars
    dag = context["ti"].dag_id
    task = context["ti"].task_id
    exec_date = context["execution_date"].strftime("%Y-%m-%dT%H:%M:%S")
    log_url = context["ti"].log_url
    exception = context["exception"]
    run_id = context["run_id"]
    try_number = context["ti"].try_number - 1
    max_tries = context["ti"].max_tries + 1

    # slack message
    slack_message = (
        f"`DAG`  {dag}"
        f"\n`Run Id`  {run_id}"
        f"\n`Task`  {task} _(try {try_number} of {max_tries})_"
        f"\n`Execution`  {exec_date}"
        f"\n```{exception}```"
    )

    # slack format and attachements
    attachments = {
        "mrkdwn_in": ["text", "pretext"],
        "pretext": ":dead_docker: *Task Failed*",
        "text": slack_message,
        "actions": [
            {
                "type": "button",
                "name": "view log",
                "text": "View log :airflow:",
                "url": log_url,
                "style": "primary",
            },
        ],
        "color": "danger",
        "fallback": "details",
    }

    # create alert for when tasks fail
    failed_alert = SlackWebhookOperator(
        task_id="slack_alert",
        http_conn_id="slack",
        webhook_token=slack_webhook_token,
        message="",
        attachments=[attachments],
        username="airflow",
    )
    return failed_alert.execute(context=context)


class ExtendedPythonOperator(PythonOperator):
    """
    extending the python operator so macros
    get processed for the op_kwargs field.
    """

    template_fields = ("templates_dict", "op_kwargs")


def upload_file_to_S3(aws_conn_id: str, file_path: str, key: str, bucket_name: str):
    """
    Uploads a local file to s3.
    """
    hook = S3Hook(aws_conn_id)
    hook.load_file(file_path, key, bucket_name, replace=True)
    logging.info(f"loaded {file_path} to s3 bucket:{bucket_name} as {key}")
