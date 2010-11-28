from boto.mturk.connection import MTurkConnection


def connection(data):
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
