__author__ = 'okoneshnikov'
import config
import sqlite3

# TABLES

comments_meta = (
  ('ID', 'INTEGER PRIMARY KEY AUTOINCREMENT'),
  ('CREATED_DATE', 'TEXT NOT NULL'),
  ('UPDATED_DATE', 'TEXT NOT NULL'),
  ('OBJ_TYPE', 'CHAR(50) NOT NULL'),
  ('OBJ_ID', 'CHAR(50) NOT NULL'),
  ('USER_ID', 'CHAR(50) NOT NULL'),
  ('PARENT_ID', 'INT'),
  ('COMMENT', 'TEXT')
)

comments_tree_meta = (
  ('ID', 'INTEGER NOT NULL'),
  ('PARENT_ID', 'INT NOT NULL'),
  ('LEVEL', 'INT NOT NULL')
)

report_statuses = ('working', 'completed', 'failed')
report_meta = (
  ('ID', 'INTEGER PRIMARY KEY AUTOINCREMENT'),
  ('OWNER', 'CHAR(50)'),
  # query parameters
  ('USER_ID', 'CHAR(50)'),
  ('OBJ_TYPE', 'CHAR(50)'),
  ('OBJ_ID', 'CHAR(50)'),
  ('START_DATE', 'TEXT'),
  ('END_DATE', 'TEXT'),
  ('CREATED_DATE', 'TEXT NOT NULL'),
  ('UPDATED_DATE', 'TEXT NOT NULL'),
  ('STATUS', 'TEXT NOT NULL'),
  ('FILE_TYPE', 'TEXT NOT NULL'),
  ('FILE_NAME', 'TEXT'),
  ('DESCRIPTION', 'TEXT')
)

history_actions = ('add', 'delete', 'modified')
history_meta = (
  ('ID', 'INTEGER NOT NULL'),
  ('USER_ID', 'CHAR(50)'),
  # add/change/delete
  ('ACTION', 'TEXT'),
  ('COMMENT_ID', 'INTEGER NOT NULL'),
  ('COMMENT', 'TEXT'),
  ('CREATED_DATE', 'TEXT NOT NULL'),
)

scheme_dict = {
  'COMMENTS': comments_meta,
  'COMMENTSTREE': comments_tree_meta,
  'REPORTS': report_meta,
  'HISTORY': history_meta
}

# INDEXES

object_index_sql = '''CREATE INDEX object_index
ON COMMENTS
  (OBJ_TYPE, OBJ_ID, PARENT_ID)
'''

user_index_sql = '''CREATE INDEX user_index
ON COMMENTS
  (USER_ID)
'''

tree_id_index_sql = '''CREATE INDEX tree_id_index
ON COMMENTSTREE
(ID)
'''
tree_parent_index_sql = '''CREATE INDEX tree_parent_index
ON COMMENTSTREE
(PARENT_ID)
'''

def create_scheme(dbname):
  conn = sqlite3.connect(dbname)
  c = conn.cursor()

  for name, description in scheme_dict.items():
    sql = 'CREATE TABLE %s (%s)' % \
          (name, ','.join(["%s %s" % field for field in description]))
    c.execute(sql)

  c.execute(object_index_sql)
  c.execute(user_index_sql)
  c.execute(tree_id_index_sql)
  c.execute(tree_parent_index_sql)

  conn.commit()
  conn.close()

if __name__ == '__main__':
  create_scheme(config.DB_NAME)