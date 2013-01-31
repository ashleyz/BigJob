######################
Writing BigJob Scripts
######################

This documentation is to help provide a familiarity with the scripts and the different configurable parameters that will help you get started. It is not comprehensive. For complete API documentation, please see `Section 5 <../library/index.html>`_.

======================
BigJob Jargon
======================

Familiarity with the below terms will help you to understand the overview of BigJob functionality.

#. **Application** - A program that is composed of computation and data elements

#. **Pilot-Job (Pilot)** - An entity that actually gets submitted and scheduled on a resource using the resource management system. A Pilot-Job provides application-level control and management of a set of allocated resources. A container for a set of tasks. Allows the logical grouping of compute units (see below)

#. **Compute Unit** - A self-containing piece of work, e.g. a computational task that potentially operates on a set of input data, also an 'application kernel'

#. **Pilot-Data** - Allows the logical grouping of data units (see below). This collection of files can be associated with an extensible set of properties.

#. **Data Unit** - A container for a logical group of data that is often accessed together or comprises a larger set of data, e.g. data files or chunks

#. **Pilot-Manager (PM)** - Stores the information of the compute units and is responsible for orchestrating the interactions between the Pilots

#. **Pilot-Agent** - For each HPC resource specified, a Pilot-Agent is launched. When a resource becomes available, the Pilot-Agent becomes active and pulls the stored information of the compute unit and executes it on that HPC resource.

#. **Coordination System** - A database used by the Pilot-Manager to store the information of Compute Units and orchestrate Pilot-Agents. Active Pilot-Agents use the coordination system to pull the Compute Unit information in order to execute such Compute Units on HPC resources.

======================
Import Python Modules
======================

You can import any number of Python modules, depending on what you want to do in your script. You must import the pilot module as follows::

	from pilot import PilotComputeService, ComputeDataService, State

======================
Coordination URL
======================

Identify the coordination system to be used. You should have set up a Redis server as part of the `Setting Up a Redis Server <../install/redis.html>`_ section.

Replace the COORDINATION_URL parameter with the path to your Redis server. The following example shows how to do this for localhost and a remote resource, such as cyder::

	COORDINATION_URL = "redis://localhost:6379"   # uses redis database as coordination system.   
::

	COORDINATION_URL = "redis://cyder.cct.lsu.edu:2525"  # uses redis database on cyder.cct.lsu.edu at port 2525 as coordination system. 

======================
NUMBER_JOBS
======================

The number of jobs simply defines how many jobs you wish to run. For instance, 1 Pilot-Job may be submitted to run 100 compute units (sub-jobs). In this case, the NUMBER_JOBS parameter would be set to 100. It should be noted that this is usually at the top of the script for convenience but can be added in a for loop around the Compute Unit Description.

======================
Pilot Compute Description
======================

The next step in creating your script is to define the pilot compute description (PCD). The PCD just defines the resource in which you will be running on and different attributes required for managing jobs on that resource. Recall that a Pilot-Job requests resources required to run all of the jobs (i.e. it's like one big job instead of many small jobs).

The following are the resource specifications that need to be provided:

- :code:`service_url` - Specifies the SAGA-Python job adaptor (often this is based on the batch queuing system) and resource hostname (for instance, lonestar.tacc.utexas.edu) on which jobs can be executed. For remote hosts, password-less login must be enabled. 
- :code:`number_of_processes` - This refers to the number of cores that need to be allocated to run the jobs
- :code:`allocation` - Specifies your allocation, if running on an XSEDE resource. This field must be removed if you are running somewhere that does not require an allocation.
- :code:`queue` - Specifies the job queue to be used. If you are not submitting to a batch queuing system, remove this parameter.
- :code:`working_directory` - Specifies the directory in which the Pilot-Job agent executes.
- :code:`walltime` - Specifies the number of minutes the resources are requested for. ::

	pilot_compute_description = { 	   "service_url": "sge+ssh://localhost",
        	                           "number_of_processes": 12,
                	                   "allocation": "XSEDE12-SAGA",
                        	           "queue": "development",
                                	   "working_directory": os.getenv("HOME")+"/agent",
                                   	   "walltime":10
                                	}

After defining a Pilot Compute Description, we tell the system to create the Pilot-Job by adding the following line::

	pilot_compute_service.create_pilot(pilot_compute_description=pilot_compute_description)


========================
Compute Data Service
========================

The Compute Data Service ::

    compute_data_service = ComputeDataService()
    compute_data_service.add_pilot_compute_service(pilot_compute_service)


========================
Compute Unit Description
========================

Next, we must define the actual compute unit that we want to run. These are what constitute the individual jobs that will run within the Pilot. Oftentimes, this will be an executable, which can have input arguments or environment variables.

- :code:`executable` - Specifies the path to the executable, i.e. NAMD, AMBER, etc.
- :code:`arguments`  - Specifies the list of arguments to be passed to executable. This field may not be necessary if your executable does not require input arguments. 
- :code:`environment` - Specifies the list of environment variables to be set for the successful of job execution. This field may also not be necessary depending on your application.
- :code:`working_directory` - Specifies the directory in which the job has to execute. If not specified, the Pilot-Job creates a default directory.
- :code:`number_of_processes` - Specifies the number of cores to be assigned for the job execution.
- :code:`spmd_variation` - Specifies the type of job. By default, it is single job. It can also be an MPI job.
- :code:`output` - Specifies the file in which the standard output of the job execution to be stored.
- :code:`error` - Specifies the file in which the standard error of the job execution to be stored. :: 

	compute_unit_description = { "executable": "/bin/echo",
        	                     "arguments": ["Hello","$ENV1","$ENV2"],
                	             "environment": ['ENV1=env_arg1','ENV2=env_arg2'],
                        	     "number_of_processes": 4,            
                             	     "spmd_variation":"mpi",
                             	     "output": "stdout.txt",
                             	     "error": "stderr.txt"
                           	   }    

After defining a description for the compute units, you want to submit these compute units. The number of compute units you submit depends on the NUMBER_JOBS you defined at the top of the script. You will need a :code:`for` loop in Python in order to submit the correct number of jobs. ::

	 for i in range(NUMBER_JOBS):
		compute_data_service.submit_compute_unit(compute_unit_description)




======================
Pilot Data Description
======================

::

	pilot_data_description =    {
   					'service_url': "ssh://localhost/tmp/pilotstore/",
   					'size':100,
   					# Affinity
					'affinity_datacenter_label',    # pilot stores sharing the same label are located in the same data center          
					'affinity_machine_label',       # pilot stores sharing the same label are located on the same machine                           
				    }



======================
Data Unit Description
======================