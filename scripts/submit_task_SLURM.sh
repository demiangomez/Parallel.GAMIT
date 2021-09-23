#!/bin/bash
#SBATCH --time=96:00:00
#SBATCH --nodes=4 --ntasks-per-node=48 --partition=gomez
#SBATCH --mem-per-cpu=3500M
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --output=/fs/project/gomez.124/logs/Parallel_GAMIT.o%j
#SBATCH --job-name=Parallel_GAMIT
#SBATCH --mail-type=all --mail-user=%u@osu.edu
#
# Most of the commands in the script are straight forward Linux commands, here is a brief description of the ones that
# aren't:
# module:   Deals with the various tools available on the HPC.
# ----------------------------------------------------------------------------------------------------------------------

# some definitions for the run
PPP_VER=1.10

echo " >> Started at" $(date) "requested by" ${USER}

# activate the virtual environment
source /fs/project/gomez.124/opt/Parallel.GAMIT/venv/bin/activate

module load intel                 # load the intel package for openmpi
module load openmpi/4.0.1         # openmpi
# module load python/3.7-2020.02  # Loads python

# create a var with the location of dispynode
dispynode=/fs/project/gomez.124/opt/Parallel.GAMIT/venv/lib/python3.7/site-packages/dispy/dispynode.py

export DATADIR=/fs/project/gomez.124  # Create a shortcut variable to the project directory.
set -x  # Echo commands
set -e  # Exit script if a command fails

# generate the access to the list of nodes
PBS_NODEFILE=`generate_pbs_nodefile`

# add the .unity to create the FQDM
#cat $PBS_NODEFILE | awk '{print $1".unity"}' > /fs/project/gomez.124/opt/Parallel.GAMIT/scripts/nodes.txt
# PBS_NODEFILE=/fs/project/gomez.124/opt/Parallel.GAMIT/scripts/nodes.txt

# Create a variable containing the name of the headnode, for example u114.unity
headnode=`hostname | awk -F . '{print $1}'`
echo headnode: $headnode

#create the files containing column and row lists of all (head + worker) complete node names and all node numbers 
nodes=($( grep -v $headnode $PBS_NODEFILE | sort | uniq )) # Create a variable with the list of worker nodes. 

# Create a string separated by commas with all the worker nodes.
all_nodes=($( cat $PBS_NODEFILE | sort | uniq ))
all_nodes=$(echo ${all_nodes[@]}  | sed 's/ /.unity,/g')
echo all_nodes: $all_nodes

# replace the node_list element from gnss_data.cfg
sed -i '/node_list/c\node_list='$all_nodes'.unity' gnss_data.cfg

echo " >> Running pre-job tasks on $headnode with workers ${nodes[@]}"

# The number of CPUs after the -c option of dispynode.py has to equal the amount of CPUs available on each node.

for node in ${nodes[*]}
do
	# get the number of CPUs
	cpus=`grep ${node} $PBS_NODEFILE | wc -l`

	# create directories and copy programs (SLURM appears to pre-create the TMP dir, but just in case)
        srun --ntasks=1 --nodes=1 -w ${node} mkdir -p $TMPDIR

        # copy PPP program
        srun --ntasks=1 --nodes=1 -w ${node} cp -r /fs/project/gomez.124/opt/PPP_NRCAN_${PPP_VER} $TMPDIR

	# use the full path to dispynode.py rather than the script to use the correct python version
        echo "#!/usr/bin/bash" > /fs/project/gomez.124/opt/Parallel.GAMIT/scripts/${node}.unity
	echo "python $dispynode -c $cpus -d --daemon --clean --dest_path_prefix $TMPDIR > /fs/project/gomez.124/opt/Parallel.GAMIT/scripts/dispynode_${node}.log 2>&1 &" >> /fs/project/gomez.124/opt/Parallel.GAMIT/scripts/${node}.unity
	echo "wait" >> /fs/project/gomez.124/opt/Parallel.GAMIT/scripts/${node}.unity
	chmod +x /fs/project/gomez.124/opt/Parallel.GAMIT/scripts/${node}.unity
	# pbsdsh -E : passes all environmental vars to the process
        srun --ntasks=1 --nodes=1 --export=ALL -w ${node} /fs/project/gomez.124/opt/Parallel.GAMIT/scripts/${node}.unity & # Start dispynode on the workers.
done

# now repeat for the headnode
mkdir -p $TMPDIR
cp -r /fs/project/gomez.124/opt/PPP_NRCAN_${PPP_VER} $TMPDIR

# start on the head node
cpus=`grep ${headnode} $PBS_NODEFILE | wc -l | awk '{print $1-2}'`

# use the full path to dispynode.py rather than the script to use the correct python version
python $dispynode -c $cpus -d --clean --daemon --dest_path_prefix $TMPDIR > /fs/project/gomez.124/opt/Parallel.GAMIT/scripts/dispynode_${headnode}.log 2>&1 &

sleep 6 # Wait for the worker nodes to finish setting up.
# export PATH=$TMPDIR/PPP_NRCAN_${PPP_VER}/source:$PATH

python $command # Run the archive script.

# delete the temporary scripts
rm /fs/project/gomez.124/opt/Parallel.GAMIT/scripts/*.unity
rm /fs/project/gomez.124/opt/Parallel.GAMIT/scripts/dispynode_*.log


