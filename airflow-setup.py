import airflow
from airflow import models, settings
from airflow.contrib.auth.backends.password_auth import PasswordUser
from sqlalchemy import create_engine
user = PasswordUser(models.User())
user.username = 'airflow_admin'
user.email = 'oliver.fengtian@gmail.com'
user.password = 'airflow'
# Set the value as either False / True depending if you want the user to be an admin
user.superuser = True
engine = create_engine("postgresql://airflow:airflow@postgres:5432/airflow")
session = settings.Session(bind=engine)
session.add(user)
session.commit()
session.close()
exit()