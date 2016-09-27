__author__ = 'seanlook.com'

DB_AUTH = {"ecuser": "uKewXESsn/oukUQAEyR+iA==",
           "ec_read": "password encrypted by prpcryptec.py"}

# configuration file read interval, 10s
CHECK_CONFIG_INTERVAL = 10

# mysql connection ping interval to keepalive
# 10 times * 10 = 100 seconds. DO NOT exceed *wait_timeout*
CHECK_PING_MULTI = 10
CONFIG_FILE_PATH = 'mysqk.ini'
