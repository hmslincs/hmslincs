Requirements
============

* OMERO Python bindings -- see installation instructions here:
  http://www.openmicroscopy.org/site/support/omero4/developers/Python.html
* Python packages: PIL
* ffmpeg with libx264 support (configure --enable-libx264)
* qt-faststart from libav-tools

Usage
=====

1. Add the OMERO Python source directory (``lib/python`` inside the OMERO.py or
   OMERO.server directory) to your ``PYTHONPATH``.

2. Run ``sampattavanich_2014_extract.py`` to download the individual movie
   frames from the OMERO server as JPEG files. If interrupted, it will pick up
   where it left off instead of starting over from the beginning. 26GB of disk
   space is required to store the individual JPEG files, which are placed in the
   ``../temp/sampattavanich_2014/frames`` directory.

3. Run ``sampattavanich_2014_render.py``. A further 2GB of disk space is
   required for processed JPEG files (placed in
   ``../temp/sampattavanich_2014/frames/*/render``) and 100-200MB for final
   rendered MP4 files (placed in
   ``../temp/docroot/explore/sampattavanich-2014/movies``). Up to 4 CPU cores
   will be utilized. If interrupted, it will start over from the beginning.

4. Run ``sampattavanich_2014_build_site.py``. Output will be placed in
   ``../temp/docroot/explore/sampattavanich-2014``. To deploy to production,
   copy the contents of this folder into the server docroot hierarchy.
   IMPORTANT: currently the files must be copied to ``$DOCROOT/explore_/sam...``
   (note the extra underscore) which is mapped to ``/explore/sam...`` with a
   ``RewriteRule``. Also run ``manage.py collectstatic`` on the server to deploy
   the static files.
