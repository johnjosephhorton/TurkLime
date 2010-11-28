from google.appengine.ext import db
from google.appengine.ext import blobstore
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from boto.exception import BotoClientError, BotoServerError

from turklime import mturk

import cgi, yaml, logging


class RequestHandler(webapp.RequestHandler):
  def write(self, data):
    self.response.out.write(data)

  def render(self, path, params):
    self.write(template.render(path, params))

  def reply(self, code, text):
    self.response.set_status(code)

    self.write(cgi.escape(text))

  def bad_request(self, text='Bad request'):
    self.reply(400, text)


def upload_required(fn):
  def _fn(self, *args, **kwargs):
    key = self.request.get('key', None)

    if key:
      try:
        self.reader = blobstore.BlobReader(key)

        try:
          self.data = yaml.load(self.reader)

          return fn(self, *args, **kwargs)
        except yaml.YAMLError:
          self._render_error('Error: badly formatted YAML file')
      except blobstore.Error:
        return self.bad_request('Bad key')
    else:
      self.bad_request('No key')

  return _fn


def mturk_connection_required(fn):
  def _fn(self, *args, **kwargs):
    self.connection = mturk.connection(self.data)

    try:
      return fn(self, *args, **kwargs)
    except (BotoClientError, BotoServerError), response:
      message = '%s: %s' % (response.errors[0][0], response.errors[0][1])

      logging.error(message)

      self._render_error('Error: bad AWS credentials')

  return _fn


def experiment_required(fn):
  def _fn(self, *args, **kwargs):
    key = self.request.get('key', None)

    if key:
      try:
        self.experiment = db.get(key)

        return fn(self, *args, **kwargs)
      except db.BadKeyError:
        self.bad_request('Bad key')
    else:
      self.bad_request('No key')

  return _fn
