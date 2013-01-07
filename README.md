hmslincs
========
Hit this url to kill all the FastCGI workers on dev:

http://dev.lincs.hms.harvard.edu/cgi-bin/cleanup.cgi

Specifically, it kills all dev.lincs... virtualenv python processes on the webserver 
nodes that are owned by www-data. Loading scripts are run on the login nodes, 
so even if a loading script is running it won't be affected.