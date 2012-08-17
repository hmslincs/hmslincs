# one-time setup
HMSLINCSDIR=<INITIALIZE>

DJANGODIR=$HMSLINCSDIR/django
SERVERDIR="$DJANGODIR/hmslincs_server"
SETTINGS="$SERVERDIR/settings.py"
mv $SETTINGS $SETTINGS.hold
ln -s $HMSLINCSDIR/tmp/setup/settings.py $SERVERDIR

psql -qc 'DROP DATABASE IF EXISTS django' postgres django

cd $DJANGODIR
manage.py syncdb  # configure the admin user

psql -qc 'ALTER DATABASE django RENAME TO django_init' postgres django

createdb -U django -T django_init django

rm $SETTINGS
mv $SETTINGS.hold $SETTINGS


######################################################################
# after the setup above, do this to reset the database:

psql -qc 'DROP DATABASE IF EXISTS django' postgres django
createdb -U django -T django_init django
