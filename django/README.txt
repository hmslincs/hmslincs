* South: http://south.readthedocs.org/en/latest/tutorial/index.html
- - South can see what’s changed in your models.py file and automatically write migrations that match your changes
** To use: 

- Run ./manage.py syncdb to load the South table into the database. Note that syncdb looks different now - South modifies it.

* To convert existing apps (not needed if the converted app is checked in):

./manage.py convert_to_south myapp

* to create a schema migration (if modifying the model, then commit the migration):

make the new migration, using the –auto feature:

./manage.py schemamigration myapp --auto

* apply existing schema migration:

./manage.py migrate myapp
