from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app as run_wsgi
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers

from boto.mturk.question import ExternalQuestion

import urllib, logging


class Struct(object):
  def __init__(self, **kwargs):
    self.__dict__ = kwargs


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
