#!/usr/bin/env python
# -*- coding: utf-8 -*-

import praw
import logging, logging.config, os
from configparser import ConfigParser
global r

cfg_file = ConfigParser()
path_to_cfg = os.getcwd() #os.path.abspath(os.path.dirname(sys.argv[0]))
path_to_cfg = os.path.join(path_to_cfg, 'schedulebot.cfg')
cfg_file.read(path_to_cfg)

def login():
    try:
        r = praw.Reddit(user_agent=cfg_file.get('reddit', 'user_agent'), client_id = cfg_file.get('reddit', 'client_id'), client_secret = cfg_file.get('reddit', 'client_secret'), username = cfg_file.get('reddit', 'username'), password = cfg_file.get('reddit', 'password'))
        
    except Exception as e:
         logging.error(e)           
    return r
    
#def conn():
#    dbname = cfg_file.get('database', 'database')
#    dbuser = cfg_file.get('database', 'user')
#    dbpassword = cfg_file.get('database', 'password')
#    dbhost = cfg_file.get('database', 'host')
#    
#    try:    
#        con = psycopg2.connect(database=dbname, user=dbuser, password=dbpassword, host=dbhost)
#        print('  connected to database: ' + dbname)
#        return con
#    except Exception as e:
#        logging.error(e)
#    return

if __name__ == '__main__':
    print ('login.py')
    login()
else:
    print ('  login module imported')
    
