#!/bin/bash
nohup /opt/asf/tools/alertmonitor/alertmon.sh &
# Name of the application
NAME="asfui"
# Django project directory
DJANGO_DIR=/opt/asf/frontend/asfui/
#we will communicte using this unix socket
SOCKFILE="$DJANGO_DIR/gunicorn.sock"
mkdir -p $DJANGO_DIR/logs
# the user to run as
#USER=asf
# the group to run as
GROUP=asf
# how many worker processes should Gunicorn spawn
NUM_WORKERS=3
# which settings file should Django use
DJANGO_SETTINGS_MODULE=core.settings
# WSGI module name
DJANGO_WSGI_MODULE=core.wsgi
echo "Starting $NAME as `whoami`"
# Activate the virtual environment
cd $DJANGO_DIR
source $DJANGO_DIR/bin/activate
export DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE
export PYTHONPATH=$DJANGO_DIR:$PYTHONPATH
# Create the run directory if it doesn't exist
RUNDIR=$(dirname $SOCKFILE)
test -d $RUNDIR || mkdir -p $RUNDIR
# Start your Django Unicorn
# Programs meant to be run under supervisor should not daemonize themselves (do not use --daemon)
#--user=$USER --group=$GROUP \
#--log-file=-
exec $DJANGO_DIR/bin/gunicorn ${DJANGO_WSGI_MODULE}:application \
--name $NAME \
--workers $NUM_WORKERS \
--bind=unix:$SOCKFILE \
--log-level=debug \
--log-file=$DJANGO_DIR/logs/gunicorn.log
