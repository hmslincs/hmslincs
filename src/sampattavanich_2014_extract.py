import sys
import os
import errno
import getpass
import pickle
from omero.gateway import BlitzGateway


def makedirs_exist_ok(name):
    try:
        os.makedirs(name)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


src_dir = os.path.abspath(os.path.dirname(__file__))
frame_dir = os.path.join(src_dir, '..', 'temp', 'sampattavanich_2014', 'frames')

HOST = 'lincs-omero.hms.harvard.edu'
PORT = 4064
GROUP = 'Public'

# Read username and password.
print "Connecting to OMERO server: %s:%d" % (HOST, PORT)
username = getpass._raw_input('Username: ')
password = getpass.getpass()

# Connect to the Python Blitz Gateway.
conn = BlitzGateway(username, password, host=HOST, port=PORT)
connected = conn.connect()
if not connected:
    print >> sys.stderr, ("Error: Connection not available, please check your "
                          "username and password.")
    sys.exit(1)
else:
    print "Login successful.\n"

# Set our default group so we can see the data.
# (I thought I had to do this, but now I am not sure it's needed.
# -JLM 2013/12/04)
try:
    group = next(g for g in conn.listGroups() if g.getName() == GROUP)
except StopIteration:
    print >> sys.stderr, "Error: could not find group '%s'" % GROUP
conn.setGroupForSession(group.getId())

# Get plate of interest.
# (ID 1552 is "RTK ligands induce differing FOXO3a translocation dynamics")
plate = conn.getObject('Plate', 1552)
# Get list of lists of well objects from the plate.
well_grid = plate.getWellGrid()

# Loop over all wells in the plate.
for (raw_row_num, row) in enumerate(well_grid):
    for (raw_col_num, well) in enumerate(row):
        # Fix up row and column numbers to match Pat's nomenclature.
        row_num = raw_row_num + 1
        col_num = raw_col_num + 2
        # Construct paths and create output directory. (I dislike this naming
        # format but it's what Pat has chosen. -JLM)
        output_dir = 'r%dc%d' % (row_num, col_num)
        full_output_dir = os.path.join(frame_dir, output_dir)
        makedirs_exist_ok(full_output_dir)
        # Get image object and a few of its useful attributes.
        image = well.getImage()
        name = image.getName()
        size_t = image.getSizeT()
        # Render first channel only, as yellow.
        image.setColorRenderingModel()
        image.setActiveChannels([1], colors=['FF0'])
        # Loop over each frame in the movie.
        for frame in xrange(0, size_t):
            # Print progress for this well, overwriting the same line each time.
            print "\r%s - %s  %d/%d" % (output_dir, name, frame+1, size_t),
            sys.stdout.flush()
            # Construct output filename for this frame.
            filename = os.path.join(full_output_dir, '%03d.jpg' % frame)
            # Skip the render + export process if the file already exists.
            if not os.path.exists(filename):
                try:
                    with open(filename, 'wb') as fd:
                        # Note: This is where we incur the server render and
                        # data transfer costs. Everything else up until this
                        # point is pretty quick.
                        #
                        # Use full quality (compression=1.0).
                        jpeg_data = image.renderJpeg(z=0, t=frame,
                                                     compression=1.0)
                        # Write the data out to the file.
                        fd.write(jpeg_data)
                except KeyboardInterrupt as e:
                    # On interrupt, remove the file. This is so we don't leave a
                    # partial file -- we'll try to re-download this file again
                    # on the next run.
                    try:
                        os.unlink(fd.name)
                    except:
                        pass
                    # Re-raise the KeyboardInterrupt so the process does exit.
                    raise e
        # Get real-time offset in seconds for each movie frame.
        delta_t = [pi.deltaT for pi in
                   image.getPrimaryPixels().copyPlaneInfo(theC=0, theZ=0)]
        # Write it to disk.
        dt_filename = os.path.join(full_output_dir, 'delta_t.pck')
        with open(dt_filename, 'wb') as fd:
            pickle.dump(delta_t, fd, protocol=2)

        # Print a newline here (since the progress output doesn't).
        print

print "Done"
