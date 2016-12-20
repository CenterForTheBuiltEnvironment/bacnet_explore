import smtplib

def send_email(email_address, body, subject):
  gmail_user = "bacpypes.driver@gmail.com"
  gmail_pwd = "fitPC.2016"
  FROM = "bacpypes_driver"
  TO = email_address if type(email_address) is list else [email_address]  # must be a list
  SUBJECT = subject
  TEXT = body
  # Prepare actual message
  message = """\From: %s\nTo: %s\nSubject: %s\n\n%s
  """ % (FROM, ','.join(TO), SUBJECT, TEXT)
  try:
    # server = smtplib.SMTP(SERVER)
    print 'Connecting to gmail server...'
    server = smtplib.SMTP("smtp.gmail.com", 587)  # or port 587 or 465 doesn't seem to work!
    print 'ehlo...'
    server.ehlo()
    print 'starttls...'
    server.starttls()
    print 'login...'
    server.login(gmail_user, gmail_pwd)
    print 'sendmail...'
    server.sendmail(FROM, TO, message)
    server.close()
    print 'Successfully sent the email.'
  except:
    print "Failed to send the email."

if __name__=='__main__':
  email_list = ['erdongwei@berkeley.edu']
  send_email(email_list, 'TEST BODY', '[SAT Reset] TEST SUBJECT')
