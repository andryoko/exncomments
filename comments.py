__author__ = 'okoneshnikov'
import sqlite3
import config
from datetime import datetime
import utils
import scheme

class CommentAPIError(Exception):
  codes = {
    1: 'Delete comment error. Comment has children comments',
    2: 'Save history error. Invalid action. It must be add/delete/modified'
  }

  def __init__(self, code, message=None):
    assert code in CommentAPIError.codes

    message = message or self.codes[code]
    Exception.__init__(self, message)
    self.code = code

  def __repr__(self):
    return '<%s message=%s, code=%s>' % (self.__class__.__name__,
                                         self.message, self.code)

  def __str__(self):
    return '%s comment api error. %s, code %s' % (self.__class__.__name__,
                                                 self.message, self.code)

class DbManager(object):
  """ Hide SQL realization to this class."""
  connection = sqlite3.connect(config.DB_NAME, check_same_thread=False)
  connection.row_factory = sqlite3.Row

  @classmethod
  def commit(cls):
    cls.connection.commit()


  @classmethod
  def insert(cls, table_name, params, cursor=None):
    assert table_name in scheme.scheme_dict

    items = []
    for field, descr in scheme.scheme_dict[table_name]:

      if 'AUTOINCREMENT' in descr:
        value = 'NULL'

      elif descr.startswith('TEXT') or descr.startswith('CHAR('):
        value = "'%s'" % params.get(field, params.get(field.lower(), ''))
      else:
        value = '%s' % params.get(field, params.get(field.lower(), 'NULL'))

      items.append(value)

    values = ','.join(items)

    sql = "INSERT INTO %s VALUES (%s)" % (table_name, values)
    c = cursor or cls.connection.cursor()
    c.execute(sql)
    return c


  @classmethod
  def log(cls, comment_id, user_id, action, comment=None):
    """ Store user action to HISTORY table."""

    if not action in scheme.history_actions:
      raise CommentAPIError(2)

    now = datetime.utcnow()
    params = dict(id=comment_id,
                  user_id=user_id,
                  action=action,
                  comment_id=comment_id,
                  created_date=utils.dbdate(now))
    if comment:
      params['comment'] = comment

    cls.insert('HISTORY', params)


  @classmethod
  def clear(cls, table_name):
    """Delete from table all rows."""
    sql = 'DELETE FROM %s' % table_name
    c = cls.connection.cursor()
    c.execute(sql)
    cls.connection.commit()

  @classmethod
  def clear_comments(cls):
    cls.clear('COMMENTSTREE')
    cls.clear('COMMENTS')

  @classmethod
  def get(cls, table_name, id):
    c = cls.connection.cursor()
    sql = "SELECT * FROM %s WHERE ID=%s" % (table_name, id)
    c.execute(sql)
    result = c.fetchone()
    return result

  @classmethod
  def create_comment(cls, obj_type, obj_id, user_id, comment, parent_id=None, created=None):
    """ Create comment. Add row to COMMENTS table and several rows to
    COMMENTSTREE table. For example, if comment has parents p1->p2->p3 then
    add 3 rows:
      (comment_id, p1, 1), (comment_id, p2, 2), (comment_id, p2, 3)

    @params obj_type: object type.
    @params obj_id: object id.
    @params user_id: user id.
    @params comment: comment text.
    @param parent_id: parent comments id.
    @return: new comment id.
    """
    assert obj_type and obj_id and user_id

    now = created or datetime.utcnow()

    params = dict(
      created_date=utils.dbdate(now),
      updated_date=utils.dbdate(now),
      obj_type=obj_type,
      obj_id=obj_id,
      user_id=user_id,
      parent_id=parent_id if parent_id else 'NULL',
      comment=comment
    )

    c = cls.insert('COMMENTS', params)
    new_id = c.lastrowid

    # get all parent nodes
    parents = []
    if parent_id:
      parents = cls.get_parents(parent_id)
      parents.append(parent_id)

    # add rows to COMMENTSTREE table
    for index, pid in enumerate(parents):
      cls.insert('COMMENTSTREE', dict(id=new_id, parent_id=pid, level=index+1))

    cls.log(new_id, user_id, 'add', comment)
    cls.connection.commit()
    return new_id


  @classmethod
  def get_parents(cls, comment_id):
    """
    Return comment parents.
    @comment_id: comment id.
    @return: parents list.
    """
    assert comment_id
    sql = 'SELECT * FROM COMMENTSTREE WHERE ID=%s' % comment_id
    c = cls.connection.cursor()
    c.execute(sql)
    result = [(r['PARENT_ID'], r['LEVEL']) for r in c.fetchall()]
    result.sort(key=lambda x: x[1])

    return [p[0] for p in result]


  @classmethod
  def get_comments(cls, obj_type, obj_id, user_id=None, limit=20, offset=0):
    c = cls.connection.cursor()
    sql = "SELECT * FROM COMMENTS WHERE OBJ_TYPE = '%s' AND OBJ_ID = '%s' AND PARENT_ID IS NULL" % (obj_type, obj_id)
    if not user_id is None:
      sql = sql + " AND USER_ID = '%s'" % user_id

    sql = sql + " ORDER BY CREATED_DATE LIMIT %d OFFSET %d" % (limit, offset)

    c.execute(sql)
    result = c.fetchall()
    return result

  @classmethod
  def get_comment(cls, comment_id):
    return cls.get('COMMENTS', comment_id)

  @classmethod
  def delete_comment(cls, comment_id, user_id):
    c = cls.connection.cursor()
    # check children
    sql = "SELECT count(*) FROM COMMENTS WHERE PARENT_ID=%s" % comment_id
    c.execute(sql)
    result = c.fetchone()

    if result[0]:
      raise CommentAPIError(1)
    else:
      sql = "DELETE FROM COMMENTS WHERE ID=%s" % comment_id
      c.execute(sql)
      sql = "DELETE FROM COMMENTSTREE WHERE ID=%s" % comment_id
      c.execute(sql)

      cls.log(comment_id, user_id, 'delete')
      cls.connection.commit()

    return True


  @classmethod
  def update_comment(cls, comment_id, user_id, comment):
    c = cls.connection.cursor()
    sql = "UPDATE COMMENTS SET COMMENT='%s' WHERE ID=%s" % (comment, comment_id)
    c.execute(sql)

    cls.log(comment_id, user_id, 'modified', comment)
    cls.connection.commit()


  @classmethod
  def get_comments_tree(cls, comment_id):
    """ Return comment children (all levels).
    @param comment_id: comment id.
    """
    c = cls.connection.cursor()
    sql = "SELECT * FROM COMMENTS, COMMENTSTREE " \
          "WHERE COMMENTSTREE.PARENT_ID=%s AND " \
          "COMMENTS.ID=COMMENTSTREE.ID ORDER BY COMMENTS.ID" % comment_id
    c.execute(sql)
    result = c.fetchall()
    return result

  @classmethod
  def get_reports(cls, user_id, limit=20, offset=0):
    c = cls.connection.cursor()

    if user_id:
      sql = "SELECT * FROM REPORTS WHERE OWNER='%s' " \
            "ORDER BY CREATED_DATE DESC LIMIT %d OFFSET %d" % (user_id, limit, offset)
    else:
      sql = "SELECT * FROM REPORTS " \
            "ORDER BY CREATED_DATE DESC LIMIT %d OFFSET %d" % (limit, offset)

    c.execute(sql)
    result = c.fetchall()
    return result

  @classmethod
  def create_report(cls, owner, user_id, obj_type=None, obj_id=None,
                    start_date=None, end_date=None,
                    status='working', file_type='csv'):
    """Add report description to REPORTS table."""
    assert user_id
    now = datetime.utcnow()
    c = cls.insert('REPORTS', dict(
      owner=owner,
      user_id=user_id,
      obj_type=obj_type or '',
      obj_id=obj_id or '',
      start_date=start_date or '',
      end_date=end_date or '',
      status=status,
      file_type=file_type,
      file_name='',
      created_date=utils.dbdate(now),
      updated_date=utils.dbdate(now)
    ))
    cls.connection.commit()
    return c.lastrowid

  @classmethod
  def get_report_data(cls, report_id):
    report = cls.get('REPORTS', report_id)
    assert report

    c = cls.connection.cursor()
    sql = "SELECT * FROM COMMENTS WHERE USER_ID='%s'" % report['user_id']

    if report['obj_type'] and report['obj_id']:
      sql += " AND OBJ_TYPE='%s' AND OBJ_ID='%s'" % (report['obj_type'], report['obj_id'])
    elif report['obj_type']:
      sql += " AND OBJ_TYPE='%s'" % report['obj_type']

    if report['start_date']:
      sql += " AND CREATED_DATE >= '%s'" % report['start_date']

    if report['end_date']:
      sql += " AND CREATED_DATE <= '%s'" % report['end_date']

    sql += " ORDER BY CREATED_DATE"
    c.execute(sql)
    data = c.fetchall()
    return data

  @classmethod
  def get_report_file_name(cls, report_id):
    return 'static/reports/report_%s.csv' % report_id


  @classmethod
  def update_report(cls, report_id, file_name, file_type='csv', status='completed', description=''):
    c = cls.connection.cursor()
    sql = "UPDATE REPORTS SET FILE_TYPE='%s', FILE_NAME='%s', " \
          "STATUS='%s', DESCRIPTION='%s' WHERE ID=%s" % \
          (file_type, file_name, status, description, report_id)
    c.execute(sql)
    cls.connection.commit()