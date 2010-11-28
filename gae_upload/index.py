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

from pprint import pprint as pp

import cgi, os, yaml, urllib


def mturk_connection(data):
  return MTurkConnection(
    aws_access_key_id=data['aws_access_key_id']
  , aws_secret_access_key=data['aws_secret_access_key']
  , host=data['aws_host']
  )


# Experimenters upload experiment-defining YAML here
class MainHandler(webapp.RequestHandler):
  def get(self):
    upload_url = blobstore.create_upload_url('/upload')
    temp = os.path.join(os.path.dirname(__file__), 'templates/create_experiment.htm')
    outstr = template.render(temp, {'upload_url': upload_url})
    self.response.out.write(outstr)


class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
  def post(self):
    upload_files = self.get_uploads('file') # 'file' is file upload field in the form
    blob_info = upload_files[0]
    self.redirect('/serve/%s' % blob_info.key())


# Experimenter see this screen before the actual program is launched on MTurk.
class ServeHandler(blobstore_handlers.BlobstoreDownloadHandler):
  def get(self, raw_resource):
    resource = str(urllib.unquote(raw_resource))
    blob_reader = blobstore.BlobReader(resource)
    message = ""
    try:
      d = yaml.load(blob_reader)
      for key in d.keys():
        message = message + "%s: %s </br>"%(key, d[key])
        try:
          connection = mturk_connection(d)
          balance = connection.get_account_balance()[0]
          temp = os.path.join(os.path.dirname(__file__), 'templates/confirm_details.htm')
          outstr = template.render(temp, {'message': message, 'blob_key': raw_resource, 'balance': balance})
        except:
          temp = os.path.join(os.path.dirname(__file__), 'templates/info.htm')
          outstr = template.render(temp, {'message':"""Your YAML file parses, but there is something wrong with
                                                       your AWS keys or the AWS host name </br>
                                                        <a href="/">Return to file input</a>"""})
    except:
      message = """There was a problem with your YAML file format. </br>
                   Check the example. </br>
                   <a href="/">Return to file input</a>"""
      temp = os.path.join(os.path.dirname(__file__), 'templates/info.htm')
      outstr = template.render(temp, {'message': message})

    self.response.out.write(outstr)


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
    url = "http://unconfounded.appspot.com/landing/" + str(key)
    q = ExternalQuestion(external_url=url, frame_height=800)
    keywords=['easy','fast','interesting']
    create_hit_rs = connection.create_hit(
      question=q,
      lifetime= d['lifetime'],
      max_assignments= d['max_assignments'],
      title=d['title'],
      keywords=d['keywords'],
      reward = d['reward'],
      duration=d['duration'],
      approval_delay= d['approval_delay'],
      annotation=d['annotation'],
      response_groups=d['response_groups'])
    assert(create_hit_rs.status == True)
    temp = os.path.join(os.path.dirname(__file__), 'templates/info.htm')
    if create_hit_rs[0].IsValid == 'True':
      outstr = template.render(temp, {'message': """Your HIT was created. </br>
                                          The HITId is %s </br>
                                       <a href="/">Input another YAML</a>""" % create_hit_rs[0].HITId})
    else:
      outstr = template.render(temp, {'message': "Your HIT was not created"})
    self.response.out.write(outstr)


# grabs the AssignmentId and workerId from a visiting worker
class LandingPage(webapp.RequestHandler):
  def get(self, gae_key):
    gae_key = str(urllib.unquote(gae_key))
    worker_id = self.request.GET.get('workerId', '')
    assignment_id = self.request.GET.get('assignmentId', '')
    temp = os.path.join(os.path.dirname(__file__), 'templates/info.htm')
    if assignment_id == 'ASSIGNMENT_ID_NOT_AVAILABLE':
      message = """You need to accept the HIT"""
      outstr = template.render(temp, {'message': message})
      self.response.out.write(outstr)
    elif worker_id == "":
      message = """Cannot parse your workerId. Are you accessing this page from outside MTurk?"""
      outstr = template.render(temp, {'message': message})
      self.response.out.write(outstr)
    else:
      key = assignment_id
      base = db.get(gae_key).url
      redirect_url = base + "?passthru=key&key=%s" % key
      self.redirect(redirect_url)


# parses the submit originating from Limesurvey---passes back to
# to MTurk to close the loop. Passes the assignment id, survey id and ssid.
class BackToTurk(webapp.RequestHandler):
  def get(self):
    assignment_id = self.request.GET.get('key', '')
    ssid = self.request.GET.get('ssid', '')
    sid = self.request.GET.get('sid', '')
    # need to add survey ID from limesurvey
    #sandbox_url = "http://workersandbox.mturk.com/mturk/externalSubmit"
    sandbox_url = "http://www.mturk.com/mturk/externalSubmit"
    param = "?assignmentId=" + assignment_id + "&response_id=" + ssid + "&survey_id=" + sid
    self.redirect(sandbox_url + param)


def handlers():
  return [
    ('/', MainHandler)
  , ('/upload', UploadHandler)
  , ('/serve/([^/]+)?', ServeHandler)
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
