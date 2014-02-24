Instructions
============

1. ImageMagick and Ghostscript are required (to support the Python module 'wand'
   and its PDF reading capability).

2. The environment variable ``RESOURCE_PATH`` must be set to your local path to
   the Dropbox ``_LINCS_breast cancer website`` directory. If it is not set the
   scripts will complain. If it is set incorrectly then nothing will work
   properly.

3. Run the build scripts in the following order. The first two scripts cache
   some data to disk in ``../temp/stash`` that is read by the other two. All
   scripts except the ``main`` one accept a ``-n`` option to disable the (slow)
   image processing steps.

   * niepel_2014_cell_line.py
   * niepel_2014_ligand.py
   * niepel_2014_lookup_table.py
   * niepel_2014_main.py

4. Note that ``cell_line.py`` and ``ligand.py`` cache the contents of the Excel
   files they use for input as well as the results of querying the HMS LINCS DB
   and UniProt. If there are updates to any of those data sources, you'll need
   to remove the corresponding files from the ``stash`` directory.

5. All output is placed under
   ``../temp/docroot/explore/breast_cancer_signaling``. To deploy to production,
   copy the contents of this folder into the server docroot hierarchy.
   IMPORTANT: currently the files must be copied to ``$DOCROOT/explore_/br...``
   (note the extra underscore) which is mapped to ``/explore/br...`` with a
   ``RewriteRule``. Also run ``manage.py collectstatic`` on the server to deploy
   the static files.
