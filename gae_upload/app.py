from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app as run_wsgi
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers

from boto.mturk.connection import MTurkConnection
from boto.mturk.question import ExternalQuestion
from boto.exception import BotoClientError, BotoServerError

import cgi, yaml, urllib, logging


def mturk_connection(data):
  return MTurkConnection(
    aws_access_key_id=data['aws_access_key_id']
  , aws_secret_access_key=data['aws_secret_access_key']
  , host=data['aws_host']
  )


def create_hit(connection, question, data):
  return connection.create_hit(
    question=question
  , lifetime=data['lifetime']
  , max_assignments=data['max_assignments']
  , title=data['title']
  , keywords=data['keywords']
  , reward=data['reward']
  , duration=data['duration']
  , approval_delay=data['approval_delay']
  , annotation=data['annotation']
  , response_groups=data['response_groups']
  )


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
    self.connection = mturk_connection(self.data)

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
        self.experiment = Experiment.get(key)

        return fn(self, *args, **kwargs)
      except db.BadKeyError:
        self.bad_request('Bad key')
    else:
      self.bad_request('No key')

  return _fn


class Struct(object):
  def __init__(self, **kwargs):
    self.__dict__ = kwargs


class Experiment(db.Model):
  created = db.DateTimeProperty(auto_now_add=True)
  params = blobstore.BlobReferenceProperty()
  url = db.StringProperty()


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


class MainHandler(RequestHandler):
  def get(self):
    self.redirect('/upload')


# Experimenters upload experiment-defining YAML here
class UploadFormHandler(blobstore_handlers.BlobstoreUploadHandler):
  def get(self):
    params = {'form_action': blobstore.create_upload_url('/upload')}

    output = template.render('templates/upload_form.htm', params)

    self.response.out.write(output)

  def post(self):
    key = self.get_uploads('file')[0].key()

    confirmation_form_url = '/confirm?' + urllib.urlencode({'key': key})

    self.redirect(confirmation_form_url)


# Experimenter see this screen before the actual program is launched on MTurk.
class ConfirmationFormHandler(RequestHandler):
  @upload_required
  @mturk_connection_required
  def get(self):
    self.render('templates/confirmation_form.htm', {
      'experiment_params': [self._experiment_param(key, self.data[key]) for key in sorted(self.data.keys())]
    , 'account_balance': self.connection.get_account_balance()[0]
    , 'form_action': self.request.url
    })

  @upload_required
  @mturk_connection_required
  def post(self):
    experiment = Experiment()
    experiment.params = self.reader.blob_info.key()
    experiment.url = self.data['external_hit_url']

    key = experiment.put()

    url = '%s/task?%s' % (self.request.host_url, urllib.urlencode({'key': key}))

    question = ExternalQuestion(external_url=url, frame_height=800)

    response = create_hit(self.connection, question, self.data)

    assert(response.status == True)

    if response[0].IsValid == 'True':
      link = Struct(href='/', text='Create another experiment')

      self.render('templates/info.htm', {'message': 'Created HIT: ' + response[0].HITId, 'link': link})
    else:
      self._render_error('Error: could not create HIT')

  def _experiment_param(self, key, value):
    if type(value) == list: value = ', '.join(value)

    return Struct(label=key.replace('_', ' ').capitalize(), value=value)

  def _render_error(self, message):
    self.render('templates/info.htm', {
      'message': message
    , 'link': Struct(href='/', text='Return to upload form')
    })


# grabs the AssignmentId and workerId from a visiting worker
class MechanicalTurkTaskHandler(RequestHandler):
  @experiment_required
  def get(self):
    worker_id = self.request.GET.get('workerId', None)

    assignment_id = self.request.GET.get('assignmentId', None)

    if worker_id is None:
      self.bad_request('No workerId')
    elif assignment_id is None:
      self.bad_request('No assignmentId')
    elif assignment_id == 'ASSIGNMENT_ID_NOT_AVAILABLE':
      self.render('templates/info.htm', {'message': 'You need to accept the HIT'})
    else:
      params = {'passthru': 'key', 'key': assignment_id}

      url = '%s?%s' % (self.experiment.url, urllib.urlencode(params))

      self.redirect(url)


# parses the submit originating from Limesurvey---passes back to
# to MTurk to close the loop. Passes the assignment id, survey id and ssid.
class MechanicalTurkSubmitHandler(RequestHandler):
  def get(self):
    params = {
      'assignmentId': self.request.GET.get('key', '')
    , 'response_id': self.request.GET.get('ssid', '')
    , 'survey_id': self.request.GET.get('sid', '')
    }

    host_url = 'https://www.mturk.com' # TODO: use turkSubmitTo parameter passed into LandingPage

    submit_url = '%s/mturk/externalSubmit?%s' % (host_url, urllib.urlencode(params))

    self.redirect(submit_url)


def handlers():
  return [
    ('/', MainHandler)
  , ('/upload', UploadFormHandler)
  , ('/confirm', ConfirmationFormHandler)
  , ('/task', MechanicalTurkTaskHandler)
  , ('/submit', MechanicalTurkSubmitHandler)
  ]


def application():
  return webapp.WSGIApplication(handlers(), debug=True)


def main():
  run_wsgi(application())


if __name__ == "__main__":
  main()
