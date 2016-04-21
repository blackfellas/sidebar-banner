#### sidebar banner updater for /r/blackfellas

Only ImGur album or gallery links are valid urls at the moment. 

An album image  must be less than 500kB each in size (reddit limitations). 

#### Requirements:
* Reddit account (oauth)
* Imgur account (ouath)
* Python 2.7 (locally or set up on a server; I'm using Heroku as an example server)
* Pip (to install the python modules in `requirements.txt`). Heroku does this automatically.
* pgAdmin to create and connect to databases locally and remotely (on Heroku) http://www.pgadmin.org/
* Heroku host (free tier) with Postgres database installed. If you want to run locally, you won't need `Procfile`
* Create a database using sqlalchemy (heroku run python) or pgAdmin.
* Configure your Reddit, Imgur, and Postgres DB credentials by entering them into schedule.cfg (no need to enter Reddit password if using oauth)
* Optional: copy the files to a Dropbox folder and deploy by syncing it with Heroku.


#### Running
* Set up the wiki page on reddit for your bot http://reddit.com/r/YOURSUBREDIT/wiki/YOURBOT-schedule
* After scheduling using the YAML syntax (see https://www.reddit.com/r/AutoModerator/comments/1z7rlu/-/cfrzuxb)
* Send a message to your bot to `schedule` using your subreddit in the subject place
* Run the `banner.py` script (using a task scheduler on your PC, cron, or Heroku scheduler)
* See a live example on http://reddit.com/r/Blackfellas/wiki/blackfellasbot-schedule

