import webapp2
import os, sys
import logging
from paste import httpserver

# Calculate the path based on the location of the WSGI script.
workspace = os.path.dirname(__file__)
if not workspace in sys.path:
  sys.path.append(workspace)

import base_handler
import config
from comments import DbManager as dbm
from comments import CommentAPIError
import tasks

# test object types
object_types = [
  'Post',
  'Object1',
  'Object2',
  'Objec13'
]

# test object ids
object_ids = ['id%d' % (x+1) for x in range(10)]
# test users
users_ids = ['admin'] + ['uid%d' % (x+1) for x in range(10)]

COMMENTS_PAGE_SIZE = 10
REPORTS_PAGE_SIZE = 10

class CommentsHandler(base_handler.BaseHandler):
  def get(self):
    obj_type = self.request.get('obj_type', object_types[0])
    obj_id = self.request.get('obj_id', object_ids[0])
    limit = int(self.request.get('limit', COMMENTS_PAGE_SIZE) or COMMENTS_PAGE_SIZE)
    error = None
    comments = []
    more = False

    if obj_type and not obj_type in object_types:
      error = 'Invalid object type'
    elif obj_id and not obj_id in object_ids:
      error = 'Invalid object id'
    elif obj_type and obj_id:
      offset = self.page*limit
      comments = dbm.get_comments(obj_type, obj_id, limit=limit+1, offset=offset)
      if len(comments) > limit:
        more = True
        comments = comments[:limit]

    context = {
      'obj_type': obj_type,
      'obj_id': obj_id,
      'comments': comments,
      'error': error,
      'object_types': object_types,
      'object_ids': object_ids,
      'user_ids': users_ids,
      'page': self.page,
      'prev_page': self.page-1,
      'next_page': self.page+1 if more else None
    }

    if not self.viewer_id:
      context['viewer_id'] = users_ids[0]

    self.render_response('comments_page.html', **context)

class EditCommentHandler(base_handler.BaseHandler):
  def get(self):
    obj_type = self.request.get('obj_type')
    obj_id = self.request.get('obj_id')
    comment_id = self.request.get('comment_id')
    parent_id = self.request.get('parent_id')

    context = {
      'obj_type': obj_type,
      'obj_id': obj_id,
      'comment_id': comment_id,
      'parent_id': parent_id,
      'object_types': object_types,
      'object_ids': object_ids,
      'user_ids': users_ids,
      'tree': self.request.get('tree')
    }

    if comment_id:
      comment = dbm.get_comment(comment_id)
      context['comment'] = comment
      if comment:
        context['obj_type'] = comment['OBJ_TYPE']
        context['obj_id'] = comment['OBJ_ID']
        context['user_id'] = comment['USER_ID']
        context['parent_id'] = comment['PARENT_ID']

    self.render_response('comment_page.html', **context)

  def post(self):
    obj_type = self.request.get('obj_type')
    obj_id = self.request.get('obj_id')
    comment = self.request.get('comment')
    parent_id = self.request.get('parent_id')
    comment_id = self.request.get('comment_id')
    error = None

    if comment_id:
      # update comment
      dbm.update_comment(comment_id, self.viewer_id, comment)
    else:
      # create new comment
      comment_id = dbm.create_comment(obj_type, obj_id, self.viewer_id, comment, parent_id)

    context = {
      'obj_type': obj_type,
      'obj_id': obj_id,
      'comment_id': comment_id,
      'parent_id': parent_id,
      'comment': dbm.get_comment(comment_id),
      'error': error,
      'object_types': object_types,
      'object_ids': object_ids,
      'user_ids': users_ids,
      'tree': self.request.get('tree')
    }

    self.render_response('comment_page.html', **context)

class CommentsTreeHandler(base_handler.BaseHandler):
  def get(self):
    comment_id = self.request.get('comment_id')
    page = self.request.get('page')
    comment = dbm.get_comment(comment_id)

    if comment:
      rows = dbm.get_comments_tree(comment_id)

      # create tree
      nodes = dict((r['ID'], {'children': [], 'value': r}) for r in rows)
      nodes[comment['ID']] = {'children': [], 'value': comment}

      for r in rows:
        nodes[r['PARENT_ID']]['children'].append(nodes[r['ID']])

      context = {
        'parent': comment,
        'page': page,
        'viewer_id': self.viewer_id,
        'comments_tree': nodes[comment['ID']]['children']
      }

      self.render_response('comments_tree_page.html', **context)
    else:
      return self.error(404)


  @base_handler.restapi
  def post(self):
    pass

class ReportsCommentsHandler(base_handler.BaseHandler):

  def get(self):
    limit = int(self.request.get('limit', REPORTS_PAGE_SIZE) or
                REPORTS_PAGE_SIZE)

    more = False
    offset = self.page*limit
    reports = dbm.get_reports(self.viewer_id, limit+1, offset)

    if len(reports) > limit:
      more = True
      reports = reports[:limit]

    context = {
      'viewer_id': self.viewer_id,
      'reports': reports,
      'page': self.page,
      'prev_page': self.page-1,
      'next_page': self.page+1 if more else None
    }

    self.render_response('reports_page.html', **context)

  @base_handler.restapi
  def post(self):
    report_id = self.request.get('report_id')
    action = self.request.get('action')

    if not report_id:
      return self.error_result(101, "Required report_id parameter.")

    if not action in ('restart',):
      return  self.error_result(100, "Invalid action parameter.")

    # run task to create report
    tasks.create_report.delay(report_id)

    return {'result': True}

class NewReportHandler(base_handler.BaseHandler):

  def get(self, error=None):
    user_id = self.request.get('user_id')
    obj_type = self.request.get('obj_type')
    obj_id = self.request.get('obj_id')

    context = {
      'user_id': user_id,
      'obj_type': obj_type,
      'obj_id': obj_id,
      'object_types': [''] + object_types,
      'object_ids': [''] + object_ids,
      'user_ids': users_ids
    }

    self.render_response('new_report_page.html', **context)

  def post(self):
    user_id = self.request.get('user_id')
    obj_type = self.request.get('obj_type')
    obj_id = self.request.get('obj_id')
    start_date = self.request.get('start_date', '')
    end_date = self.request.get('end_date', '')

    if start_date:
      start_date += " 00:00:00"

    if end_date:
      end_date += " 00:00:00"

    assert self.viewer_id

    if not (user_id or obj_type):
      return self.get("Required user_id or obj_type parameters")

    report_id = dbm.create_report(self.viewer_id, user_id, obj_type, obj_id,
                      start_date, end_date)

    # run task to create report
    tasks.create_report.delay(report_id)

    self.redirect('/comment/reports?viewer_id=%s' % self.viewer_id)

class DeleteCommentHandler(base_handler.BaseHandler):

  @base_handler.restapi
  def post(self):
    comment_id = self.request.get('comment_id')

    if not self.viewer_id in users_ids:
      return self.error_result(100, 'Invalid viewer_id=%r' % self.viewer_id)

    try:
      dbm.delete_comment(comment_id, self.viewer_id)
    except CommentAPIError, e:
      return self.error_result(105, str(e))

    return {'result': True}

application = webapp2.WSGIApplication([
    ('/comment/add/?', EditCommentHandler),
    ('/comment/edit/?', EditCommentHandler),
    ('/comment/delete/?', DeleteCommentHandler),
    ('/comment/tree/?', CommentsTreeHandler),
    ('/comment/new_report/?', NewReportHandler),
    ('/comment/reports/?', ReportsCommentsHandler),
    ('/', CommentsHandler),
    ('/static/(.+)', base_handler.StaticFileHandler) # only for dev server

], debug=True)

def main():
  httpserver.serve(application,
                  host=config.WEBSITE_APP_HOST,
                  port=config.WEBSTIE_APP_PORT)

if __name__ == '__main__':
    main()

