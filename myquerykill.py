__author__ = 'seanlook.com'

import MySQLdb
import os,sys,time
import commands
import ConfigParser
import threading
import re
import logging

from logging.handlers import TimedRotatingFileHandler


LOG_FILE = 'killquery.log'
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

#handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1024*1024, backupCount=5)
handler = TimedRotatingFileHandler(LOG_FILE, when='d', interval=1, backupCount=7)

formatter = logging.Formatter('%(asctime)s [%(levelname)-5s] %(threadName)16s >> %(message)s')

handler.setFormatter(formatter)

logger.addHandler(handler)

# interval to check config file by seconds
CHECK_CONFIG_INTERVAL = 5
CHECK_PING_MULTI = 10

# get the config changed realtime
def get_kill_options(config_file_path, db_instance):
    cf = ConfigParser.ConfigParser()
    cf.read(config_file_path)

    #o = cf.options(db_instance)
    #print 'options:', o
    v = cf.items(db_instance)
    #kuser = cf.get("crm0", "k_user")

    return v

# concate the sql to filter thread need to be killed
def get_sqlThreads_str(**kwargs):
    #def get_sqlThreads_str(kill_opt = []):
    # k_user, k_longtime, k_lock, k_sleep
    # print kwargs

    k_user = kwargs['k_user']
    k_longtime = kwargs['k_longtime']
    k_lock = kwargs['k_lock']
    k_sleep = kwargs['k_sleep']

    sqlstr = "select CONCAT('kill ', pl.ID, ';') AS killcmd, pl.* from information_schema.processlist pl where 1 "
    if k_user:
        sqlstr = sqlstr + " and user='" + k_user + "'"

    # sleep always means long time. sometimes it should not to be killed
    if k_sleep == '0':
        sqlstr = sqlstr + " and command != 'Sleep' "

    sqlstr += " and ( 0 "

    if k_longtime > '1':
        sqlstr = sqlstr + " or time > " + str(k_longtime)
    if k_lock == '1':
        sqlstr = sqlstr + " or state = 'Locked'"


    sqlstr = sqlstr + " ) order by time desc"
    #sqlstr = sqlstr + " into outfile abc.txt"
    return sqlstr

# do something before really kill threads
# like take snapshot of processlist and engine status that abnormal time for analysis later
def before_kill(conn, threadName):
    logger.info("Gather info before kill using the same connection")
    str_fulllist = "show full processlist"
    str_status = "show engine innodb status"
    str_trx_lockwait = """
        SELECT
            r.trx_id waiting_trx_id,
            r.trx_mysql_thread_id waiting_thread,
            r.trx_query waiting_query,
            b.trx_id blocking_trx_id,
            b.trx_mysql_thread_id blocking_thread,
            b.trx_query blocking_query
        FROM
            information_schema.innodb_lock_waits w
        INNER JOIN information_schema.innodb_trx b ON b.trx_id = w.blocking_trx_id
        INNER JOIN information_schema.innodb_trx r ON r.trx_id = w.requesting_trx_id
    """
    try:
        cur = conn.cursor()

        kill_before_status = threadName + "_beforekill.snapshot"
        fo = open(kill_before_status, "a")
        fo.write("\n\n##########  " + time.asctime() + "  ##########\n")

        logger.debug("Get 'show full processlist' to: %s", kill_before_status)
        cur.execute(str_fulllist)
        rs = cur.fetchall()
        for row in rs:
            fo.write(str(row))
            fo.write("\n")
            #print row

        logger.debug("Get 'innodb_lock_waits' to: %s", kill_before_status)
        cur.execute(str_trx_lockwait)
        rs = cur.fetchall()
        for row in rs:
            fo.write(str(row))
            fo.write("\n")
            #print row

        logger.debug("Get 'show engine innodb status' to: %s", kill_before_status)
        cur.execute(str_status)
        rs = cur.fetchone()
        row = rs.__str__()
        for line in row.split("\n"):
            fo.write(str(line))
            fo.write("\n")
            #print line

        fo.close()
    except MySQLdb.Error, e:
        logger.critical('Error %d: %s', e.args[0], e.args[1])
    finally:
        cur.close()


# run the kill with the given connection and kill options
def do_kill(conn, threadName, kill_dry_run, **kill_opt):
    sqlstr = get_sqlThreads_str(**kill_opt)
    logger.info("SQL to find threads: %s", sqlstr)

    try:
        cur = conn.cursor()
        cur.execute(sqlstr)

        processlist_file = "processlist_" + threadName + "_killed.txt"
        fo = open(processlist_file, "w")

        for row in cur.fetchall():
            fo.write(row.__str__())
            fo.write('\n')
            # print  row
        fo.close()

        # exclude some threads that may meet the kill condition
        shell_threads_to_kill = "grep -Evi '(Binlog|ecdba|Daemon)' " + processlist_file + "|awk -F , '{print $1}' |sed 's/^(//g' | xargs"
        #shell_threads_to_kill = "awk -F , '{print $1}' " + processlist_file + "| sed 's/^(//g;s/L$//g' | xargs"
        threads_to_kill = commands.getoutput(shell_threads_to_kill)

        if len(threads_to_kill) > 0:
            before_kill(conn, threadName)
            logger.warn("Threads to be killed: %s", threads_to_kill)
            if kill_dry_run == 0:
                cur.execute(threads_to_kill)
            else:
                logger.info("Run in dry_run=1 mode (do not kill really, but snapshot is taken.)")
            logger.info("Kill threads done")
        else:
            logger.info("No threads to kill")

    except MySQLdb.Error, e:
        logger.critical('Error %d: %s', e.args[0], e.args[1])
    finally:
        cur.close()

def keep_long_session_kill(db_instance, db_user, threadName):
    logger.debug("Read database info from config: myquerykill.ini")
    db_comm = dict(get_kill_options('mykill.ini', 'db_info'))
    db_host = db_comm[db_instance + '_host']
    db_port = int(db_comm['db_port'])
    #db_port = int(db_comm[db_instance + '_port'])
    db_pass = db_comm['db_pass_'+db_user]

    # use the file to record killed threads for analysis later
    processlist_file = "processlist_" + threadName + "_killed.txt"
    logger.debug("You Can find threads could be killed in %s", processlist_file)
    conn = ""

    try:
        logger.debug("Connect Database %s: host='%s', user='%s, port=%d", db_instance, db_host, db_user, db_port)
        conn = MySQLdb.Connect(host=db_host, user=db_user, passwd=db_pass, port=db_port)

        # count the kill made. Compared to kill_max_count in config file
        kill_count = 0
        kill_max_count_last = 0

        # to make ping not too often, set the counter to wait X times to CHECK_CONFIG_INTERVAL.
        check_ping_wait = 0
        while True:
            kill_opt_global = dict(get_kill_options('mykill.ini', 'global'))
            # kill_max_count=0 means disable all kill
            kill_max_count = int(kill_opt_global['kill_max_count'])

            logger.debug("Get Config max kill times: %d", kill_max_count)

            if kill_max_count != kill_max_count_last:
                logger.info("Max kill times changed, set a clean start")
                kill_count = 0
                if kill_max_count == 0:
                    logger.info("kill_max_count=0, disable kill")
            elif kill_max_count == 999:
                # run kill daemon
                logger.warn("999 max kill times set, always kill")
                kill_count = 0

            # check connection first
            try:

                if check_ping_wait == CHECK_PING_MULTI:
                    logger.info("MySQL ping to keep session alive")
                    conn.ping()
                    check_ping_wait = 0
                else:
                    check_ping_wait += 1

            except MySQLdb.Error, e:
                logger.warn('Error %d: %s', e.args[0], e.args[1])
                if e.args[0] == 2013:
                    conn = MySQLdb.Connect(host=db_host, user=db_user, passwd=db_pass, port=db_port)
                    logger.warn("Reconnect Database %s: host='%s', user='%s, port=%d", db_instance, db_host, db_user, db_port)

            # need kill (more)
            if kill_count < kill_max_count:
                kill_opt = dict(get_kill_options('mykill.ini', db_instance))
                #logger.info("kill_count: %d, kill_max_count: %d", kill_count, kill_max_count)

                pattern = re.compile(db_user)
                # if pattern.match(kill_opt['k_user']):
                # only kill the threads of user set by k_user in config file
                myuserlist=kill_opt['k_user'].replace(' ', '').split(',')
                if kill_opt['k_user'] == 'all':
                    myuserlist.append(db_user)
                    logger.debug("You have set k_user=all")
                    kill_opt['k_user'] = db_user
                if db_user in myuserlist:
                    logger.info("Read kill thread config: KILL %s", str(kill_opt))
                    logger.debug("Current kill count: %d", kill_count)

                    #before_kill(conn, processlist_file)
                    kill_dry_run = int(kill_opt_global['dry_run'])
                    do_kill(conn, threadName, kill_dry_run, **kill_opt)

                    kill_count = kill_count + 1
                else:
                    # Other user in the same db_instance always read the set user to kill
                    # set kill_count to indicate I'm not the set user.
                    # every kill should be detected from kill_max_count, and that change set kill_count=0 back
                    kill_count = kill_max_count
                    logger.info("I'm not the set k_user: %s", kill_opt['k_user'])

            kill_max_count_last = kill_max_count

            time.sleep(CHECK_CONFIG_INTERVAL)

    except MySQLdb.Error, e:
        logger.critical('Error %d: %s', e.args[0], e.args[1])
        sys.exit(1)

    finally:
        if conn:
            conn.close()
            logger.debug('Connection closed OK')


# use multi-thread
class myThread(threading.Thread):
    def __init__(self, threadID, name, db_instance, db_user):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.db_instance = db_instance
        self.db_user = db_user

    def run(self):
        logger.info("Starting kill query Thread: %s", self.name)
        keep_long_session_kill(self.db_instance, self.db_user, self.name)
        logger.info("Exiting Thread: %s", self.name)


if __name__ == '__main__':
    db_instances = ['crm0', 'crm1', 'crm2', 'crm3']
    #db_instances = ['crm0']
    db_users = ['ecuser', 'ec_read']
    # start keep-session-kill threads for every user and db_instance
    for i in db_instances:
        for u in db_users:
            # threadName like dbnqqame_user
            thread_to_killquery = myThread(100, i + "_" + u, i, u)
            thread_to_killquery.start()
            time.sleep(0.8)


#thread_crm0_ecweb.start()
#thread_crm0_ecdbsvr.start()

# regular match
# write file
# exception
# logfile rotate
# password encrytion

