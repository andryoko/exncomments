__author__ = 'okoneshnikov'
from celery import Celery
from celery.utils.log import get_task_logger
import csv

from comments import DbManager as dbm
from scheme import comments_meta
import sqlite3
import config

app = Celery('tasks', backend='rpc://', broker='amqp://')
app.config_from_object('celeryconfig')

log = get_task_logger('__name__')

@app.task
def add(x, y):
    return x + y

@app.task
def create_report(report_id):
  dbm.connect(config.DB_NAME)

  data = dbm.get_report_data(report_id)
  file_name = dbm.get_report_file_name(report_id)

  with open(file_name, 'wb') as csvfile:
    fieldnames = [item[0] for item in comments_meta]
    writer = csv.writer(csvfile, delimiter=',', quoting=csv.QUOTE_ALL)

    writer.writerow(fieldnames)
    for r in data:
      row = []
      for val in r:
        if isinstance(val, int):
          row.append(val)
        else:
          row.append((val or '').encode('utf-8'))

      writer.writerow(row)

  # update report row
  dbm.update_report(report_id, file_name)
  dbm.connection.close()

  return file_name