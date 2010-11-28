from google.appengine.ext import db
from google.appengine.ext import blobstore


class Experiment(db.Model):
  created = db.DateTimeProperty(auto_now_add=True)
  owner = db.UserProperty()
  task_id = db.StringProperty()
  params = blobstore.BlobReferenceProperty()
  url = db.StringProperty()
