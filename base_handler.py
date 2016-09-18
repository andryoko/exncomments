__author__ = 'okoneshnikov'

import json
import config
import webapp2
import logging
import os
import utils
import mimetypes

from webapp2_extras import jinja2

HTTP_URLS = {
  'website': config.WEBSITE_APP_ROOT_URL,
  'static': config.STATIC_ROOT_URL,
}

error_codes = {
  # api errors
  100: 'Invalid parameter value',
  101: 'Missing parameter',
  102: 'Object already exists',
  103: 'Object doesn\'t exist',
  104: 'Object has not property',
  105: 'Comment API error',
  300: 'Permission error',
  301: 'Authentication error',
}

def restapi(func):
  """ Decorator to handle json result."""
  def decorated(self, *args, **kwargs):
    result = func(self, *args, **kwargs)
    # Convert to json
    self.response.headers['Content-Type'] = 'application/json'
    if result is not None:
      json_result = json.dumps(result, indent=2)
    else:
      json_result = "{}"
    self.response.out.write(json_result)
  return decorated

def auth(func):
  """ Decorator to check signature."""
  def decorated(self, *args, **kwargs):
    return func(self, *args, **kwargs)

  return decorated

class BaseHandler(webapp2.RedirectHandler):
  """ Base handlers class."""
  context = {}

  @webapp2.cached_property
  def jinja2(self):
    """Returns an instance of :class:`Jinja2` from the app registry.

    It'll try to get it from the current app registry, and if it is not
    registered it'll be instantiated and registered. A second call to this
    function will return the same instance.

    :param app:
        A :class:`webapp2.WSGIApplication` instance used to store the instance.
        The active app is used if it is not set.
    """
    key = 'webapp2_extras.jinja2.Jinja2'
    _jinja2 = self.app.registry.get(key)
    config = {
      'template_path': os.path.join(os.path.dirname(__file__), "templates")
    }
    if not _jinja2:
      _jinja2 = self.app.registry[key] = jinja2.Jinja2(self.app, config)

    return _jinja2

  def __init__(self, *args, **kwargs):
    self.context['config'] = config
    super(BaseHandler, self).__init__(*args, **kwargs)

    if self.request:
      logging.info('Request: %r', [(arg, self.request.get(arg))
                                   for arg in self.request.arguments()])

  @property
  def urls(self):
    return HTTP_URLS

  def update_context(self, template_name, context):
    context.update(self.context)
    context['page_name'] = template_name.replace(".html", "")
    context['config'] = config
    context['viewer_id'] = context.get('viewer_id') or self.viewer_id
    context['urls'] = self.urls

    return context

  @property
  def viewer_id(self):
    return self.request.headers.get('X-Api-User-Id') or self.request.get('viewer_id')

  @property
  def page(self):
    return int(self.request.get('page', 0) or 0)

  def render_response(self, template_name, **context):
    # Renders a template and writes the result to the response.
    context = self.update_context(template_name, context)
    rv = self.jinja2.render_template(template_name, **context)
    self.response.write(rv)

  def error_result(self, code, message=''):
    assert code in error_codes
    self.error(406)
    return {
      'error': '%s (%s). %s' % (error_codes[code], code, message),
      'code': code,
      'message': message
    }

class StaticFileHandler(webapp2.RequestHandler):
  """Handler to serve static files."""

  def get(self, path):
    abs_path = os.path.abspath(os.path.join(config.STATIC_ROOT_URL, path))
    if os.path.isdir(abs_path) or abs_path.find(os.getcwd()) != 0:
      self.error(403)
      return
    try:
      f = open(abs_path, 'r')
      self.response.headers.add_header('Content-Type', mimetypes.guess_type(abs_path)[0])
      self.response.out.write(f.read())
      f.close()
    except:
      self.error(404)