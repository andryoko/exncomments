__author__ = 'okoneshnikov'

import unittest
import os
import shutil
import tasks
import scheme
import sqlite3
import comments
from comments import DbManager as db
from datetime import datetime
import utils
import tasks

path = os.path.dirname(__file__)
TEMP_DIR = 'testfiles'
TEST_DB = 'testcomments.db'

# create test db
if os.path.isfile(TEST_DB):
  os.remove(TEST_DB)

scheme.create_scheme(TEST_DB)

db.connection = sqlite3.connect(TEST_DB)
db.connection.row_factory = sqlite3.Row

class SomeTestCase(unittest.TestCase):
  def setUp(self):
    tasks.app.conf.CELERY_ALWAYS_EAGER = True

  def test_celery(self):
    result = tasks.add.delay(2, 3)
    self.assertEqual(result.get(), 5)

  def test_get_parents(self):
    # clear comments tree table
    db.clear('COMMENTSTREE')

    '''
    1 -
    2 - 5
    3 - 6  -
        7  - 8  -
             9  -
             10 -
    4 - 11 - 12 - 13 - 14 -
    '''
    tree_data = (
      (5, 2, 1),
      (6, 3, 1),
      (7, 3, 1),
      (8, 7, 2),
      (8, 3, 1),
      (9, 7, 2),
      (9, 3, 1),
      (10, 7, 2),
      (10, 3, 1),
      (14, 13, 4),
      (14, 12, 3),
      (14, 11, 2),
      (14, 4, 1),
      (13, 12, 3),
      (13, 11, 2),
      (13, 4, 1),
      (12, 11, 2),
      (12, 4, 1),
      (11, 4, 1)
    )

    c = db.connection.cursor()

    for id, parent_id, level in tree_data:
      db.insert('COMMENTSTREE', dict(id=id, parent_id=parent_id, level=level), cursor=c)

    db.commit()

    desired = (
      (1, []),
      (5, [2]),
      (6, [3]),
      (7, [3]),
      (8, [3, 7]),
      (9, [3, 7]),
      (10, [3, 7]),
      (14, [4, 11, 12, 13]),
      (13, [4, 11, 12]),
      (12, [4, 11]),
      (11, [4])
    )

    for id, resp in desired:
      result = db.get_parents(id)
      self.assertEqual(result, resp)

  def test_create_comment(self):

    db.clear_comments()

    # 0 - level
    comment_id1 = db.create_comment('Post', 'id1', 'u1', 'test 1')
    comment_id2 = db.create_comment('Post', 'id2', 'u1', 'test 2')
    comment_id3 = db.create_comment('Post', 'id2', 'u2', 'test 3')

    row = db.get_comment(comment_id1)
    self.assertEqual(row['OBJ_TYPE'], 'Post')
    self.assertEqual(row['OBJ_ID'], 'id1')
    self.assertEqual(row['USER_ID'], 'u1')
    self.assertEqual(row['COMMENT'], 'test 1')

    row = db.get_comment(comment_id2)
    self.assertEqual(row['OBJ_TYPE'], 'Post')
    self.assertEqual(row['OBJ_ID'], 'id2')
    self.assertEqual(row['USER_ID'], 'u1')
    self.assertEqual(row['COMMENT'], 'test 2')

    row = db.get_comment(comment_id3)
    self.assertEqual(row['OBJ_TYPE'], 'Post')
    self.assertEqual(row['OBJ_ID'], 'id2')
    self.assertEqual(row['USER_ID'], 'u2')
    self.assertEqual(row['COMMENT'], 'test 3')

    rows = db.get_comments('Post', 'id1')
    self.assertEqual(set(r['ID'] for r in rows), set([comment_id1]))

    rows = db.get_comments('Post', 'id2')
    self.assertEqual(set(r['ID'] for r in rows), set([comment_id2, comment_id3]))

    rows = db.get_comments('Post', 'id2', 'u1')
    self.assertEqual(set(r['ID'] for r in rows), set([comment_id2]))

    rows = db.get_comments('Post', 'id2', 'u2')
    self.assertEqual(set(r['ID'] for r in rows), set([comment_id3]))

    # comment_id1 - c11
    #               c12 - c121
    #                     c122
    #                     c123

    c11 = db.create_comment('Post', 'id1', 'u1', 'c11', parent_id=comment_id1)
    c12 = db.create_comment('Post', 'id1', 'u2', 'c12', parent_id=comment_id1)

    parents = db.get_parents(c11)
    self.assertEqual(parents, [comment_id1])
    parents = db.get_parents(c12)
    self.assertEqual(parents, [comment_id1])

    c121 = db.create_comment('Post', 'id1', 'u1', 'c121', parent_id=c12)
    c122 = db.create_comment('Post', 'id1', 'u1', 'c122', parent_id=c12)
    c123 = db.create_comment('Post', 'id1', 'u1', 'c123', parent_id=c12)

    parents = db.get_parents(c121)
    self.assertEqual(parents, [comment_id1, c12])
    parents = db.get_parents(c122)
    self.assertEqual(parents, [comment_id1, c12])
    parents = db.get_parents(c123)
    self.assertEqual(parents, [comment_id1, c12])

    rows = db.get_comments_tree(c11)
    self.assertEqual(rows, [])

    rows = db.get_comments_tree(c12)
    self.assertEqual(set(r['ID'] for r in rows), set([c121, c122, c123]))

    rows = db.get_comments_tree(comment_id1)
    self.assertEqual(set(r['ID'] for r in rows), set([c11, c12, c121, c122, c123]))

    # check delete comments

    try:
      db.delete_comment(c12, 'u1')
      self.assertTrue(False, 'Expected CommentAPIError')
    except comments.CommentAPIError, e:
      self.assertEqual(e.code, 1)

    self.assertTrue(db.delete_comment(c121, 'u1'))
    self.assertTrue(db.delete_comment(c122, 'u1'))
    self.assertTrue(db.delete_comment(c123, 'u2'))

    self.assertTrue(db.delete_comment(c12, 'u2'))

  def test_get_report_data(self):
    db.clear_comments()
    db.clear('REPORTS')

    c1 = db.create_comment('Post', 'id1', 'u1', 'c1', created=datetime(2016, 1, 1))
    c2 = db.create_comment('Post', 'id1', 'u1', 'c2', created=datetime(2016, 1, 2))
    c3 = db.create_comment('Post', 'id1', 'u1', 'c3', created=datetime(2016, 1, 3))
    c4 = db.create_comment('Post', 'id2', 'u1', 'c4', created=datetime(2016, 1, 4))
    c5 = db.create_comment('Post', 'id2', 'u1', 'c5', created=datetime(2016, 1, 5))
    c6 = db.create_comment('Post', 'id2', 'u1', 'c6', created=datetime(2016, 1, 6))

    # create report
    owner = 'admin'
    r1 = db.create_report(owner, 'u2')
    r2 = db.create_report(owner, 'u1')
    r3 = db.create_report(owner, 'u1', 'Post')
    r4 = db.create_report(owner, 'u1', 'Post', 'id1')
    r5 = db.create_report(owner, 'u1', 'Post', 'id1', utils.dbdate(datetime(2016, 1, 2)))
    r6 = db.create_report(owner, 'u1', 'Post', 'id2', '', utils.dbdate(datetime(2016, 1, 5)))
    r7 = db.create_report(owner, 'u1', 'Post', '', utils.dbdate(datetime(2016, 1, 2)), utils.dbdate(datetime(2016, 1, 5)))

    data = db.get_report_data(r1)
    self.assertEqual(data, [])

    data = db.get_report_data(r2)
    self.assertEqual([r['id'] for r in data], [c1, c2, c3, c4, c5, c6])

    data = db.get_report_data(r3)
    self.assertEqual([r['id'] for r in data], [c1, c2, c3, c4, c5, c6])

    data = db.get_report_data(r4)
    self.assertEqual([r['id'] for r in data], [c1, c2, c3])

    data = db.get_report_data(r5)
    self.assertEqual([r['id'] for r in data], [c2, c3])

    data = db.get_report_data(r6)
    self.assertEqual([r['id'] for r in data], [c4, c5])

    data = db.get_report_data(r7)
    self.assertEqual([r['id'] for r in data], [c2, c3, c4, c5])


if __name__ == '__main__':
  unittest.main()