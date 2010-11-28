TurkLime is a Google App Engine hosted application for posting
Limesurvey-based experiments to Amazon Mechanical Turk as external HITs.

To run a new instance of the application:
  - edit the application name in gae_upload/app.yaml
  - deploy to Google App Engine

To start a new experiment:
  - visit http://{application_name}.appspot.com/ and login
  - upload a YAML config file (formatted like static/example.yaml.txt)
  - check/confirm the experiment parameters to create the HIT
