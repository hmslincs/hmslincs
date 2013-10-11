Instructions
============

1. Run ``pip install -r requirements.txt`` to install the requirements.

2. The environment variable ``RESOURCE_PATH`` must be set to your local path to
   the Dropbox ``Breast Cancer Ligand Response Screen/_LINCS_website``
   directory. If it is not set the scripts will complain. If it is set
   incorrectly then nothing will work properly.

3. Run these python scripts that reside at the top level of the ``niepel_2013``
   module. The first two scripts cache some data to disk in the ``stash``
   directory and must be run prior to the last two.

   * cell_line.py
   * ligand.py
   * lookup_table.py
   * main.py

4. All output is placed in the ``output`` directory.

5. Note that ``cell_line.py`` and ``ligand.py`` cache the contents of the Excel
   files they use for input as well as the results of querying the HMS LINCS DB
   and UniProt. If there are updates to any of those data sources, you'll need
   to remove the corresponding files from the ``stash`` directory.
