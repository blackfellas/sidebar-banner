#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# The main subreddit's sidebar must include strings to denote the beginning and ending location of the list, the bot will not update the sidebar if these strings are not present
# With the default delimiters the sidebar should include a chunk of text like:

# [](#banner_start)
# banner text here
# [](#banner_end)
#

from configparser import ConfigParser
import html as HTMLParser
import logging, logging.config, re, os

import time
from time import sleep
from datetime import datetime, timedelta
from dateutil import parser, rrule, tz
import yaml

from requests.exceptions import HTTPError
import requests

from sqlalchemy import create_engine
from sqlalchemy import Column, Text, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql.expression import func


from imgurpython import ImgurClient
import random

# global reddit session
from login import login


cfg_file = ConfigParser()
path_to_cfg = os.getcwd() #os.path.abspath(os.path.dirname(sys.argv[0]))
path_to_cfg = os.path.join(path_to_cfg, 'cred.cfg')
cfg_file.read(path_to_cfg)
engine = create_engine(
        cfg_file.get('database', 'system')+'://'+\
        cfg_file.get('database', 'user')+':'+\
        cfg_file.get('database', 'password')+'@'+\
        cfg_file.get('database', 'host')+'/'+\
        cfg_file.get('database', 'database'))
print ("  engine running...")
Base = declarative_base()
Session = sessionmaker(bind=engine, expire_on_commit=False)
session = Session()

global r, client

def passes():
    client = ImgurClient(cfg_file.get('imgur', 'client_id'), cfg_file.get('imgur', 'client_secret'))
    r = login()
    return r, client

try:
    r, client = passes()
except Exception as e:
    print(e, '--retrying one last time')
    sleep(30)
    r, client = passes()

class Subreddit(Base):

    """Table containing the subreddits for the bot to monitor.

    name - The subreddit's name. "gaming", not "/r/gaming".
    enabled - Subreddit schedule will not be executed if False
    schedule_yaml - YAML definition of the subreddit's schedule
    updated - Time that the subreddit was last updated (UTC)
    """

    __tablename__ = 'schedule'

    name = Column(Text, nullable=False, primary_key=True)
    enabled = Column(Integer, nullable=False, default=1)
    schedule_yaml = Column(Text)
    updated = Column(Integer, nullable=False)
    banner_limit = Column(Integer, nullable = False, default=5)
    banner_name = Column(Text, nullable = False, default='banner')
    last_run = Column(Integer, nullable=False)
    

class ScheduledEvent(object):
    _defaults = {'repeat': None,
                 'rrule': None,
                 'url': None,
                 'title': None}
    repeat_regex = re.compile(r'^(\d+)\s+(minute|hour|day|week|month|year)s?$')
    url_regex = re.compile(r'^(https?:\/\/)?(www\.)?imgur\.com\/(a|gallery)\/\w+\/?$')
    freq_dict = {'minute': rrule.MINUTELY,
                 'hour': rrule.HOURLY,
                 'day': rrule.DAILY,
                 'week': rrule.WEEKLY,
                 'month': rrule.MONTHLY,
                 'year': rrule.YEARLY,
                 }

    def __init__(self, values, default=None):
        values = lowercase_keys_recursively(values)

        # anything not defined in the "values" dict will be defaulted
        init = self._defaults.copy()
        init.update(values)

        # convert the dict to attributes
        self.__dict__.update(init)
        

        try:
            self.first = parser.parse(self.first)#, default=default)
            if not self.first.tzinfo:
                self.first = self.first.replace(tzinfo=tz.tzutc())
        except Exception as e:
            
            raise ValueError('Error parsing date from `first`.')

        try:
            if self.repeat:
                match = self.repeat_regex.match(self.repeat)
                interval = int(match.group(1))
                if interval == 0:
                    raise ValueError('Invalid repeat interval.')
                self.rrule = rrule.rrule(self.freq_dict[match.group(2)],
                                         interval=interval,
                                         dtstart=self.first)
                
            elif self.rrule:
                self.rrule = rrule.rrulestr(self.rrule, dtstart=self.first)
        except Exception as e:
            raise ValueError('Error parsing repeat interval.')

        try:
            if self.title:
                self.title = self.replace_placeholders(self.title)
        except Exception as e:
            raise ValueError('Error in title:', e)
       

    def is_due(self, start_time, end_time):
        	
        if self.rrule and self.rrule.before(start_time, inc=True):
            print ('{title}: {due}'.format(title=self.title, due = "due!" if bool(self.rrule.between(start_time, end_time, inc=True)) else "not due"))
            next_recurrence = self.rrule.after(start_time, inc=True) 
            
            print ('Next recurrence: {0}\n'.format((next_recurrence).strftime('%a, %b %d %Y, %I:%M %p')))
            return bool(self.rrule.between(start_time, end_time, inc=True)), start_time - self.rrule.before(start_time, inc=True), self.title
            			
        else:
            print ('{0}: pending: {1}\n'.format(self.title, self.first))
            return start_time <= self.first <= end_time, start_time - end_time, self.title
        
   

        


    def execute(self, bot, subreddit, BANNER, LIMIT):

        album_id = get_album_id(self.url)
        album = client.get_album(album_id)
        album_title = self.title
        album = album.images
        COUNT = len(album)
        if COUNT < LIMIT:
            print('Not enough images!')
            send_error_message(bot, cfg_file.get('reddit', 'owner_username'), subreddit.display_name,   'Not enough '
                               ' images in album ["{0}"]({1})'.format(album_title, self.url))
            return
     
        # Pick x random ones if greater than limit
        if COUNT > LIMIT:
            album = random.sample(album, COUNT)
        banner_number = 0
        sidebar_format = "* [{title}]({link} '{desc}')" 
        sidebar_lines = []           
        bigpic = []
        
        for image in album:
            hyperlink = "#%s" %subreddit
            description = ""
            if image['size'] > 512000:
                print ('too big: %s' %(image['link']))
                title = '{0} - ({1} kB) -  {2} x {3}px'.format(image['link'], float(image['size'])/1000, image['width'], image['height'])
                description = image['description'] if image['description'] else description
                bigpic.append(sidebar_format.format(title=title, link=image['link'], desc=description))
                continue
            banner_number += 1
            url = image['link']
            local_name = localize_name(album_id, url)
            download_image(url, local_name)



            if image['description']:           
                pattern = re.compile(r'(https?|ftp):\/\/[^\s\/$.?#].[^\s]*', re.IGNORECASE|re.MULTILINE)
                matched = pattern.search(image['description'])
                blob = re.sub(pattern, '', image['description'])
                description = blob
                description = description.replace("'", '’')
                
                if matched:
                    hyperlink = matched.group(0)
                    #format for reddit markup that breaks urls with parentheses
                    hyperlink = hyperlink.replace('(', '\(')
                    hyperlink = hyperlink.replace(')', '\)')

           
            title = image['title'] if image['title'] else 'Untitled'
            line = sidebar_format.format(title=title, link=hyperlink, desc=description)
 
            css_name = BANNER + '%d' % banner_number
            print('%s: adding %s to stylesheet...' % (title, css_name))
            
            try:
                sup = r.subreddit(subreddit)
                sup.stylesheet.upload(css_name, local_name)
            except Exception as e:
                print (e)
                return
            sidebar_lines.append(line)
            if banner_number >= LIMIT:
                break
        if banner_number < LIMIT:
            print ('Not enough valid images')
            send_error_message(cfg_file.get('reddit', 'owner_username'), subreddit,   'Not enough valid'
                               ' images in album ["{0}"]({1}); check that the following image sizes are less than 500kB. '
                               'Images ideally should be greater than 300px wide and 1:1 or greater aspect ratio: \n\n{2}'.format(album_title, self.url, '\n'.join(bigpic)))
            return
        bar = '\n'.join(sidebar_lines)
        bar = '{0} {1}\n{2}\n'.format('#####',album_title, bar)
        
        r.config.decode_html_entities = True
        current_sidebar = sup.description
        current_sidebar = HTMLParser.unescape(current_sidebar)
        replace_pattern = re.compile('%s.*?%s' % (re.escape(cfg_file.get('reddit', 'start_delimiter')), re.escape(cfg_file.get('reddit', 'end_delimiter'))), re.IGNORECASE|re.DOTALL|re.UNICODE)
        new_sidebar = re.sub(replace_pattern,
                            '%s\n%s\n%s' % (cfg_file.get('reddit', 'start_delimiter'), bar, cfg_file.get('reddit', 'end_delimiter')),
                            current_sidebar)
        
        sup.mod.update(description=new_sidebar, key_color=sup.key_color, show_media=sup.show_media, allow_images=True, spoilers_enabled=True)
        print ('%s sidebar updated!' %subreddit)
        styles = sup.stylesheet()
        sup.stylesheet.update(stylesheet=styles.stylesheet)
        print ('%s stylesheet set!' %subreddit)
        if bigpic:
            send_error_message(bot, cfg_file.get('reddit', 'owner_username'), subreddit,   'The following '
                               ' images in album ["{0}"]({1}) were not valid and were skipped; check that their sizes are less than 500kB. '
                               'Images ideally should be greater than 300px wide and 1:1 or greater aspect ratio: \n\n{2}'.format(album_title, self.url, '\n'.join(bigpic)))
            
            
    def error_album (error):
        pass
            

        
    def replace_placeholders(self, string):
        date_regex = re.compile(r'\{\{date([+-]\d+)?\s+([^}]+?)\}\}')
        now = datetime.now(self.first.tzinfo)

        match = date_regex.search(string)
        while match:
            date = now
            if match.group(1):
                offset = int(match.group(1))
                date += timedelta(days=offset)
            format_str = match.group(2)
            string = date_regex.sub(date.strftime(format_str), string, count=1)
            match = date_regex.search(string)

        return string


 
def download_image(url, local_name):
    if os.path.exists(local_name):
        return
    location = os.path.split(local_name)[0]
    if not os.path.exists(location):
        os.makedirs(location)
    page = requests.get(url)
    image = page.content
    with open(local_name, 'wb') as f:
        f.write(image)
 
def localize_name(album_id, image_link):
    image_name = image_link.split('/')[-1]
    return os.path.join('images', album_id, image_name)
 
def get_album_id(album_url):
    album_url = album_url.replace('/gallery/', '/a/')
    album_id = album_url.split('/a/')[-1].split('/')[0]
    return album_id

def update_from_wiki(bot, subreddit, requester, start_timestamp):
    print ("Updating events from the %s wiki." %subreddit)
    username = cfg_file.get('reddit', 'username')
    try:

        page = subreddit.wiki[cfg_file.get('reddit', 'wiki_page_name')]

        
    except Exception:
            
        send_error_message(requester, subreddit.display_name,
            'The wiki page could not be accessed. Please ensure the page '
            'http://www.reddit.com/r/{0}/wiki/{1} exists and that {2} '
            'has the "wiki" mod permission to be able to access it.'
            .format(subreddit.display_name,
                    cfg_file.get('reddit', 'wiki_page_name'),
                    username))
        return False

    html_parser = HTMLParser
    page_content = html_parser.unescape(page.content_md)

    # check that all the events are valid yaml
    event_defs = yaml.safe_load_all(page_content)
    event_num = 1
    try:
        for event_def in event_defs:
            event_num += 1
    except Exception as e:
        indented = ''
        for line in str(e).split('\n'):
            indented += '    {0}\n'.format(line)
        send_error_message(requester, subreddit.display_name,
            'Error when reading schedule from wiki - '
            'Syntax invalid in section #{0}:\n\n{1}'
            .format(event_num, indented))
        return False
    
    # reload and actually process the events
    event_defs = yaml.safe_load_all(page_content)
    event_num = 1
    kept_sections = []
    for event_def in event_defs:
        # ignore any non-dict sections (can be used as comments, etc.)
        if not isinstance(event_def, dict):
            continue

        event_def = lowercase_keys_recursively(event_def)

        try:
            check_event_valid(event_def)
            #event = ScheduledEvent(event_def)
        except ValueError as e:
            send_error_message(requester, subreddit.display_name,
                'Invalid event in section #{0} - {1}'
                .format(event_num, e))
            return False

        event_num += 1
        kept_sections.append(event_def)

    # Update the subreddit, or add it if necessary
    try:
        db_subreddit = (session.query(Subreddit)
                       .filter(Subreddit.name == subreddit.display_name.lower())
                       .one())
        
    except NoResultFound:
        db_subreddit = Subreddit()
        db_subreddit.name = subreddit.display_name.lower()
        session.add(db_subreddit)

    db_subreddit.updated = int(start_timestamp)
    db_subreddit.schedule_yaml = page_content
    session.commit()
    logging.info("Update from wiki complete")

    bot.message('{0} schedule updated'.format(username),
                   "{0}'s schedule was successfully updated for /r/{1}"
                   .format(username, subreddit.display_name))
    return True


def lowercase_keys_recursively(subject):
    """Recursively lowercases all keys in a dict."""
    lowercased = dict()
    for key, val in subject.items():
        if isinstance(val, dict):
            val = lowercase_keys_recursively(val)
        lowercased[key.lower()] = val

    return lowercased


def check_event_valid(event):
    """Checks if an event defined on a wiki page is valid."""

    validate_keys(event)
    validate_values_not_empty(event)

    validate_type(event, 'first', str)
    validate_type(event, 'repeat', str)
    validate_type(event, 'rrule', str)
    validate_type(event, 'title', str)
    validate_regex(event, 'url', ScheduledEvent.url_regex)
    validate_regex(event, 'repeat', ScheduledEvent.repeat_regex)


def validate_values_not_empty(check):
    for key, val in check.items():
        if isinstance(val, dict):
            validate_values_not_empty(val)
        elif (val is None or
              (isinstance(val, (str, list)) and len(val) == 0)):
            raise ValueError('`{0}` set to an empty value'.format(key))


def validate_keys(check):
    valid_keys = set(['first', 'rrule', 'title', 'url'])
    valid_keys |= set(ScheduledEvent._defaults.keys())
    for key in check:
        if key not in valid_keys:
            raise ValueError('Invalid variable: `{0}`'.format(key))

    # make sure that all of the required keys are being set
    if ('title' not in check or 'first' not in check or
            'url' not in check): 
        raise ValueError('All the required variables were not set.')
    
        

def validate_type(check, key, req_type):
    
    if key not in check:
        return

    if req_type == int:
        try:
            int(str(check[key]))
        except ValueError:
            raise ValueError('{0} must be an integer'.format(key))
    else:
        if not isinstance(check[key], req_type):
            raise ValueError('{0} must be {1}'.format(key, req_type))


def validate_regex(check, key, pattern):
    if key not in check:
        return

    if not re.match(pattern, check[key]):
        raise ValueError('Invalid {0}: {1}'.format(key, check[key]))



def send_error_message(bot, user, sr_name, error):
    """Sends an error message to the user if a wiki update failed."""
    bot.message('Error processing wiki in /r/{0}'.format(sr_name),
                   '**Error updating from [wiki configuration in /r/{0}]'
                   '(http://www.reddit.com/r/{0}/wiki/{1})**:\n\n---\n\n{2}'
                   .format(sr_name,
                           cfg_file.get('reddit', 'wiki_page_name'),
                           error))


def process_messages(bot, start_timestamp):
    
    
    stop_time = session.query(func.max(Subreddit.updated)).one()
    
    owner_username = cfg_file.get('reddit', 'owner_username')
    update_srs = set()
    #invite_srs = set()
    print ('Reading messages and commands...')

    try:
        for message in r.inbox.messages():
            if int(message.created_utc) <= stop_time[0]:
                break

            if message.was_comment:
                continue

            if message.body.strip().lower() == 'schedule':
                print ('schedule message')
                # handle if they put in something like '/r/' in the subject
                if '/' in message.subject:
                    sr_name = message.subject[message.subject.rindex('/')+1:]
                else:
                    sr_name = message.subject

                if (sr_name.lower(), message.author) in update_srs:
                    continue

                try:
                    subreddit = r.subreddit(sr_name)
                    if (message.author == owner_username) or (message.author in subreddit.moderator):
                        update_srs.add((sr_name.lower(), message.author))
                    else:
                        send_error_message(bot, message.author, sr_name,
                            'You do not moderate /r/{0}'.format(sr_name))
                except HTTPError as e:
                    send_error_message(bot, message.author, sr_name,
                        'Unable to access /r/{0}'.format(sr_name))

        # do requested updates from wiki pages
        updated_srs = []
        for subreddit, sender in update_srs:
            if update_from_wiki(bot, r.subreddit(subreddit),
                                r.redditor(sender), start_timestamp):
                updated_srs.append(subreddit)
                logging.info('Updated from wiki in /r/{0}'.format(subreddit))
            else:
                logging.info('Error updating from wiki in /r/{0}'
                             .format(subreddit))

    except Exception as e:
        logging.error('ERROR: {0}'.format(e))
        raise

 
def main():
    bot = r.user.me()

    logging.config.fileConfig(path_to_cfg)

    start_timestamp = time.mktime(datetime.now().timetuple())
    start_time = datetime.utcfromtimestamp(start_timestamp)
    start_time = start_time.replace(tzinfo=tz.tzutc())
    print ("Start time %s" %start_time)

    logging.info("checking for update messages")
    try:
        process_messages(bot, start_timestamp)
    except KeyboardInterrupt:
        raise
    except Exception as e:
        logging.error('ERROR: {0}'.format(e))
        session.rollback()

    subreddits = (session.query(Subreddit)
                         .filter(Subreddit.enabled == 1)
                         .all())
    for sr in subreddits:
        
        logging.info('\nPROCESSING: {0}'.format(sr.name.upper()))
        
        LIMIT = sr.banner_limit
        BANNER = sr.banner_name
        last_run = sr.last_run
        
        if  last_run:
            last_run = float(last_run)
            last_run = datetime.utcfromtimestamp(last_run)
            last_run = last_run.replace(tzinfo=tz.tzutc())
        else:
            last_run = start_time
     	
        schedule = [ScheduledEvent(d, sr.updated)
                    for d in yaml.safe_load_all(sr.schedule_yaml)
                    if isinstance(d, dict)]
       
        #Only one event should be queued per subreddit
        title = ""
        event_due = ""
        event_backup, title_bk = None, None
        to_do = "daily show"
        cwd = 'dropbox'
        past_due = timedelta(days=999999999)
        for event in schedule:
            MC = event.is_due(last_run, start_time)
            if MC[0] and MC[1]:
                if MC[1] < past_due:
                    past_due = MC[1]
                    event_due = event
                    title = MC[2]                   
            if to_do.lower() in MC[2].lower():
                event_backup = event
                title_bk = MC[2] + ' -- backup'
        if not event_due and (cwd.lower() in os.getcwd().lower()):
            event_due = event_backup
            title = title_bk
        if event_due:
            
            try:
                print ('executing {0} in {1}'.format(title, sr.name))
                event_due.execute(bot, sr.name, BANNER, LIMIT)  
                sr.last_run = int(start_timestamp)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                session.rollback()                
                logging.error('ERROR in /r/{0}: {1}. Rolling back'.format(sr.name, e))
             
    session.commit()   
                


if __name__ == '__main__':
    main()
