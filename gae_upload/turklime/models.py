from google.appengine.ext import db
from google.appengine.ext import blobstore


class Experiment(db.Model):
  created = db.DateTimeProperty(auto_now_add=True)
  owner = db.UserProperty()
  params = blobstore.BlobReferenceProperty()
  url = db.StringProperty()
