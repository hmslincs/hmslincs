Requirements
============

* Python packages: pandas, h5py

Usage
=====

1. Run ``single_cell_dynamics_index.py``. Output will be placed in
   ``../temp/docroot/explore/single-cell-dynamics``.

2. To deploy to production, copy the contents of the ``single-cell-dynamics``
   output directory into the server docroot hierarchy. IMPORTANT: currently the
   files must be copied to ``$DOCROOT/explore_/`` (note the extra underscore).
   This locations is mapped to ``/explore/`` with a ``RewriteRule``.

3. Run ``manage.py collectstatic`` on the server to deploy the static files.
