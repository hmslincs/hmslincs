import sys
import os
import errno
import subprocess
import datetime
import pickle
import multiprocessing
import itertools
import Queue
from PIL import Image, ImageFont, ImageDraw


src_dir = os.path.abspath(os.path.dirname(__file__))
resource_dir = os.path.join(src_dir, '..', 'resources')
temp_dir = os.path.join(src_dir, '..', 'temp', 'sampattavanich_2014')
html_dir = os.path.join(src_dir, '..', 'temp', 'docroot', 'explore',
                        'sampattavanich-2014')

# Constants for image size and annotation layout.
CROP_SIZE = 700
CROP_2 = CROP_SIZE / 2
OUTPUT_DIMS = (300,) * 2
MARGIN = 6
SCALE_BAR_LENGTH_MICRONS = 50
SCALE_BAR_HEIGHT_PIXELS = 3

# Scale is hard-coded since metadata in OMERO is wrong (per discussion with Pat
# on 2013/12/04).
MICRONS_PER_PIXEL = 0.6450

# Limit workers since this is more disk I/O limited.
MAX_PROCESSES = 4

# Input and output base directories.
INPUT_BASE = os.path.join(temp_dir, 'frames')
OUTPUT_BASE = os.path.join(html_dir, 'movies')
# Per-frame subdirectory name for post-processed frame output.
PROCESSED_SUBDIR = 'processed'

# Create font objects for text annotation).
font_name = 'LiberationSans-Regular.ttf'
# Look for font file in same directory as this script.
font_path = os.path.join(resource_dir, font_name)
font_timestamp = ImageFont.truetype(font_path, 15)
font_scale = ImageFont.truetype(font_path, 11)

# String templates for external commands.
render_command_template = (
    'ffmpeg -i %s/%%03d.jpg -y '
    '-vcodec libx264 -profile:v main -level 3 -pix_fmt yuv420p -crf 21 '
    '-an %s'
    )
faststart_command_template ='qt-faststart %s %s'


def main(argv):
    if len(argv) == 0:
        process_all()
    elif len(argv) == 1:
        render_well(argv[0])
    else:
        print >> sys.stderr, "Usage: render.py [well_name]"
    return 0


"""Process all wells."""
def process_all():
    # Get number of CPUs and cap it to MAX_PROCESSES.
    processes = min(multiprocessing.cpu_count(), MAX_PROCESSES)
    # Build the pool and some other related objects.
    pool = multiprocessing.Pool(processes)
    manager = multiprocessing.Manager()
    queue = manager.Queue()
    # Get the list of well subdirectories to process.
    well_dirs = os.listdir(INPUT_BASE)
    # Build a list of argument tuples for render_well_worker, one per well.
    map_args = itertools.product(well_dirs, [queue])
    # Begin the work.
    result = pool.map_async(render_well_worker, map_args)
    num_complete = 0
    # Loop until the work is done, printing out progress messages.
    while not result.ready():
        try:
            # See render_well_worker for documentation of the queue "protocol".
            (well, msg) = queue.get(timeout=0.1)
            print '%s: %s' % (well, msg)
            if msg == '<<< END':
                # Compute and display overall progress.
                num_complete += 1
                pct_complete = num_complete * 100 / len(well_dirs)
                print '\n=== TOTAL: %d/%d (%d%%) completed ===\n' % \
                    (num_complete, len(well_dirs), pct_complete)
            # This flush is not strictly necessary, but it helps when piping the
            # output through certain tools (particularly tee).
            sys.stdout.flush()
        except Queue.Empty:
            # This happens if queue.get reaches the timeout. Just ignore it and
            # continue looping.
            pass
        except KeyboardInterrupt:
            # Try to clean up the workers on ctrl-c. Doesn't always work quite
            # right depending on precisely which code is executing when the
            # signal is received, but it's better than nothing.
            pool.terminate()
            raise


"""
Worker function for multiprocessing Pool.map/map_async.

Pool.map only passes a single argument to worker functions, so we need to unpack
our own args tuple. This tuple must contain the following values:

1. The name of the subdirectory to process.
2. A Queue (i.e. a ManagedQueue) for sending messages to the supervisor.

The "protocol" for messages to send through the queue is tuples containing 2
values: The value of well_name (as an identifier) and the message.
"""
def render_well_worker(args):
    well_name, queue = args

    # Convenience log function. Uses queue protocol if queue is defined,
    # otherwise just prints the message.
    def log(*values):
        msg = ' '.join(map(str, values))
        if queue:
            queue.put((well_name, msg))
        else:
            print msg

    log('>>> BEGIN')
    # Build some path strings.
    input_path = os.path.join(INPUT_BASE, well_name)
    processed_path = os.path.join(input_path, PROCESSED_SUBDIR)
    # Create output directories.
    makedirs_exist_ok(processed_path)
    makedirs_exist_ok(OUTPUT_BASE)
    # Get list of JPEG frame images to process.
    jpg_filenames = [p for p in os.listdir(input_path) if p.endswith('.jpg')]
    num_files = len(jpg_filenames)
    # Load list of frame time offsets that was stored by extract.py.
    dt_filename = os.path.join(input_path, 'delta_t.pck')
    delta_t = pickle.load(open(dt_filename))
    # Process frame images.
    for frame, filename in enumerate(sorted(jpg_filenames)):
        # Log progress every 10%.
        if frame % (num_files / 10) == 0:
            log('image processing - %d%%' % (frame * 100 / num_files))
        # Load the image.
        image_in = Image.open(os.path.join(input_path, filename))
        (w, h) = image_in.size
        # Crop and scale a square from the center of the frame.
        crop_box = (w/2-CROP_2, h/2-CROP_2, w/2+CROP_2, h/2+CROP_2)
        image_out = image_in.crop(crop_box).resize(OUTPUT_DIMS, Image.BILINEAR)
        # Get a Draw object for text and graphics rendering on the image.
        draw = ImageDraw.Draw(image_out)
        # Draw an hour:minute timestamp as well as raw minutes.
        dt_minutes = delta_t[frame] / 60
        ts_hours, ts_minutes = divmod(dt_minutes, 60)
        timestamp_text = '%02d:%02d (t=%d)' % (ts_hours, ts_minutes, dt_minutes)
        draw.text((MARGIN, MARGIN), timestamp_text, font=font_timestamp)
        # Calculate scale bar length, which we need for the label position.
        scale_bar_length_pixels = SCALE_BAR_LENGTH_MICRONS / MICRONS_PER_PIXEL
        # Draw the scale bar label.
        scale_text = u"%d\xb5m" % SCALE_BAR_LENGTH_MICRONS
        scale_text_dims = draw.textsize(scale_text, font=font_scale)
        scale_text_left = (OUTPUT_DIMS[0] - MARGIN -
                           scale_bar_length_pixels / 2 - scale_text_dims[0] / 2)
        scale_text_top = MARGIN
        draw.text((scale_text_left, scale_text_top), scale_text, font=font_scale)
        # Draw a scale bar.
        scale_bar_coord_0 = (OUTPUT_DIMS[0] - MARGIN - scale_bar_length_pixels,
                             MARGIN + scale_text_dims[1] + MARGIN)
        scale_bar_coord_1 = (scale_bar_coord_0[0] + scale_bar_length_pixels - 1,
                             scale_bar_coord_0[1] + SCALE_BAR_HEIGHT_PIXELS)
        scale_bar_coords = [scale_bar_coord_0, scale_bar_coord_1]
        draw.rectangle(scale_bar_coords, fill='#ffffff')
        # Save the processed frame image as a high-quality JPEG.
        output_frame_filename = os.path.join(processed_path, filename)
        image_out.save(output_frame_filename, quality=95)
    log('image processing - 100%')
    log('rendering movie')
    # Generate some filenames for the movie rendering process.
    temp_movie_filename = os.path.join(processed_path, 'movie-temp.mp4')
    output_movie_filename = os.path.join(OUTPUT_BASE, '%s.mp4' % well_name)
    # Put the movie filenames into the command templates.
    render_command = (render_command_template %
                      (processed_path, temp_movie_filename)).split(' ')
    faststart_command = (faststart_command_template %
                         (temp_movie_filename, output_movie_filename)).split(' ')
    # Call the commands, silencing all output (but raise an exception on error).
    subprocess.check_call(render_command,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    subprocess.check_call(faststart_command,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    # Clean up the temp file.
    os.unlink(temp_movie_filename)
    log('<<< END')


"""Render a single well outside the multiprocessing framework."""
def render_well(well_name):
    render_well_worker((well_name, None))


"""A version of os.makedirs that doesn't fail if the directory exists."""
def makedirs_exist_ok(name):
    try:
        os.makedirs(name)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
