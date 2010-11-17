Purpose: TurkLime is a GAE application that lets a Limesurvey-based experiment 
to be posted on Amazon Mechanical Turk as an external HIT. 

How it works: The YAML contains an external_hit_url. This URL, along with the other HIT
parameters, are used to post an external HIT on MTurk. At the same time, details of
the experiment are recorded in the datastore. This is used to set up a "listener" for 
a submit coming from Limesurvey. This submit link is at the end of each survey and is: 

http://unconfounded.appspot.com/submit?{PASSTHRULABEL}={PASSTHRUVALUE}&ssid={SAVEDID}&sid={SID} 

# Do we want to grab workerId and assignemntId later? 
# We could message them w/ survey completion request. 

# add a survey component. If worker is not in the datastore yet, we collect some demographic
information. 


Each Limesurvey survey contains 
an external submit URL: 


When the user clicks on this link, 
Bugs/Features: 

1) should turn this into a "real" or "sandbox" version 


#Experiment Details YAML

aws_secret_access_key: <key goes here> 
aws_access_key_id: <id goes here> 
aws_host: mechanicalturk.sandbox.amazonaws.com



external_hit_url: http://209.20.81.65/limesurvey/index.php?sid=52692
lifetime: 3600
max_assignments: 1
approval_delay: 3600
title: Estimate the square root of 2
keywords:
 - easy
 - fast
 - fun
reward: 0.03
duration: 3600
annotation: None.
response_groups:
 - Minimal
 - HITDetail
 - HITQuestion
 - HITAssignmentSummary




http://unconfounded.appspot.com/submit?{PASSTHRULABEL}={PASSTHRUVALUE}&ssid={SAVEDID}&sid={SID}

