from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app as run_wsgi
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers

from boto.mturk.connection import MTurkConnection
from boto.mturk.question import ExternalQuestion
from boto.mturk.price import Price
from boto.exception import BotoClientError, BotoServerError

from pprint import pprint as pp

import cgi, os, yaml, urllib, logging


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


def boto_response_error(response):
  return '%s: %s' % (response.errors[0][0], response.errors[0][1])


class Struct(object):
  def __init__(self, **kwargs):
    self.__dict__ = kwargs


class RequestHandler(webapp.RequestHandler):
  def write(self, data):
    self.response.out.write(data)

  def render(self, path, params):
    self.write(template.render(path, params))


class MainHandler(RequestHandler):
  def get(self):
    self.redirect('/upload')


# Experimenters upload experiment-defining YAML here
class UploadFormHandler(blobstore_handlers.BlobstoreUploadHandler):
  def get(self):
    self.render('templates/upload_form.htm', {
      'form_action': blobstore.create_upload_url('/upload')
    })

  def post(self):
    upload_files = self.get_uploads('file') # 'file' is file upload field in the form

    blob_info = upload_files[0]

    self.redirect('/confirm/%s' % blob_info.key())


# Experimenter see this screen before the actual program is launched on MTurk.
class ConfirmationFormHandler(blobstore_handlers.BlobstoreDownloadHandler):
  def get(self, raw_key):
    blob_reader = blobstore.BlobReader(str(urllib.unquote(raw_key)))

    try:
      data = yaml.load(blob_reader)

      try:
        connection = mturk_connection(data)

        account_balance = connection.get_account_balance()[0]

        self._render('templates/confirmation_form.htm', {
          'experiment_params': [Struct(key=k, value=data[k]) for k in data.keys()]
        , 'account_balance': account_balance
        , 'form_action': '/launch/' + raw_key
        })
      except (BotoClientError, BotoServerError), response:
        logging.error(boto_response_error(response))

        self._render_error('Error: bad AWS credentials')
    except yaml.YAMLError:
      self._render_error('Error: badly formatted YAML file')

  def _render_error(self, message):
    link = Struct(href='/', text='Return to upload form')

    self._render('templates/info.htm', {'message': message, 'link': link})

  def _render(self, path, params):
    self.response.out.write(template.render(path, params))


class Experiment(db.Model):
  url = db.StringProperty()


class LaunchExperiment(blobstore_handlers.BlobstoreDownloadHandler):
  def get(self, raw_resource):
    resource = str(urllib.unquote(raw_resource))
    blob_reader = blobstore.BlobReader(resource)
    d = yaml.load(blob_reader)
    connection = mturk_connection(d)
    experiment = Experiment()
    experiment.url = d['external_hit_url']
    key = experiment.put() # gets primary key from datastore
    url = '%s/landing/%s' % (self.request.host_url, str(key))
    q = ExternalQuestion(external_url=url, frame_height=800)
    response = create_hit(connection, q, d)
    assert(response.status == True)
    temp = os.path.join(os.path.dirname(__file__), 'templates/info.htm')
    if response[0].IsValid == 'True':
      outstr = template.render(temp, {'message': """Your HIT was created. </br>
                                          The HITId is %s </br>
                                       <a href="/">Input another YAML</a>""" % response[0].HITId})
    else:
      outstr = template.render(temp, {'message': "Your HIT was not created"})
    self.response.out.write(outstr)


# grabs the AssignmentId and workerId from a visiting worker
class LandingPage(RequestHandler):
  def get(self, gae_key):
    gae_key = str(urllib.unquote(gae_key))

    worker_id = self.request.GET.get('workerId', '')

    assignment_id = self.request.GET.get('assignmentId', '')

    if assignment_id == 'ASSIGNMENT_ID_NOT_AVAILABLE':
      message = """You need to accept the HIT"""

      self.render('templates/info.htm', {'message': message})
    elif worker_id == "":
      message = """Cannot parse your workerId. Are you accessing this page from outside MTurk?"""

      self.render('templates/info.htm', {'message': message})
    else:
      base_url = db.get(gae_key).url

      params = {'passthru': 'key', 'key': assignment_id}

      url = '%s?%s' % (base_url, urllib.urlencode(params))

      self.redirect(url)


# parses the submit originating from Limesurvey---passes back to
# to MTurk to close the loop. Passes the assignment id, survey id and ssid.
class BackToTurk(RequestHandler):
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
  , ('/confirm/([^/]+)?', ConfirmationFormHandler)
  , ('/launch/([^/]+)?', LaunchExperiment)
  , ('/landing/([^/]+)?', LandingPage)
  , ('/submit', BackToTurk)
  ]


def application():
  return webapp.WSGIApplication(handlers(), debug=True)


def main():
  run_wsgi(application())


if __name__ == "__main__":
  main()
