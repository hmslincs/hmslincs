#!/bin/bash

#SBATCH -c 1                    # Number of cores requested
#SBATCH -t 4:00:00              # run for 4 hours
#SBATCH -p short                # Partition (queue) to submit to
#SBATCH --mem-per-cpu=4G        # 4 GB memory needed (memory PER CORE)
#SBATCH --open-mode=append      # append adds to outfile, truncate deletes first
### In filenames, %j=jobid, %a=index in job array
#SBATCH -o /n/www/dev.lincs.hms.harvard.edu/support/logs/sbatch_deploy_%j.out   # Standard out goes to this file
#SBATCH -e /n/www/dev.lincs.hms.harvard.edu/support/logs/sbatch_deploy_%j.err   # Standard err goes to this file
#SBATCH --mail-type=END         # Mail when the job ends  
#write command-line commands below this line

exec "$@"

