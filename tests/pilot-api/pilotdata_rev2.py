import sys
import os
import time
import logging
#logging.basicConfig(level=logging.DEBUG)

sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))
from pilot import PilotComputeService, PilotDataService, ComputeDataServiceDecentral, State


COORDINATION_URL = "redis://localhost:6379"

if __name__ == "__main__":      
    
    #########################################################################################
    # Resource / Pilot management
    pilot_compute_service = PilotComputeService(coordination_url=COORDINATION_URL)
   
    # create pilot data service (factory for data pilots (physical, distributed storage))
    # and pilot data
    pilot_data_service = PilotDataService(coordination_url=COORDINATION_URL)
    pilot_data_description={
                                "service_url": "ssh://localhost/tmp/pilot-data/",
                            }
    pilot_data_service.create_pilot(pilot_data_description=pilot_data_description)
    
    pilot_compute_description = {
                             "service_url": 'fork://localhost',
                             "number_of_processes": 1,                             
                             "working_directory": "/tmp/pilot-compute/"                              
                            }
    
    pilot_compute_service.create_pilot(pilot_compute_description=pilot_compute_description)
     
    compute_data_service = ComputeDataServiceDecentral()
    compute_data_service.add_pilot_compute_service(pilot_compute_service)
    compute_data_service.add_pilot_data_service(pilot_data_service)
    
    #########################################################################################
    
    data_unit_description = {
                              "file_root_url": "/Users/luckow/Dropbox/SAGA/montage/",
                            }    
      
    
    # submit pilot data to a pilot store    
    data_unit = compute_data_service.submit_data_unit(data_unit_description)
    logging.debug("Submitted Data Unit: " + data_unit.get_url())
    logging.debug("Pilot Data URL: %s Description: \n%s"%(data_unit, str(pilot_data_description)))
    
    
    # create pilot job service and initiate a pilot job
    
      
  
    
    # start compute unit
    compute_unit_description = {
            "executable": "/bin/cat",
            "arguments": ["test.txt"],
            "number_of_processes": 1,
            "output": "stdout.txt",
            "error": "stderr.txt",   
            "input_data" : [data_unit.get_url()], # this stages the content of the data unit to the working directory of the compute unit
            "output_data": [
                            {
                             data_unit.get_url(): 
                             ["std*"]
                            }
                           ],  
    }    
    
    
    
    compute_unit = compute_data_service.submit_compute_unit(compute_unit_description)
    logging.debug("Finished setup of PSS and PDS. Waiting for scheduling of PD")
    compute_data_service.wait()
    
    data_unit.export("/tmp/output")
    logging.debug("Terminate Pilot Compute/Data Service")
    compute_data_service.cancel()
    pilot_data_service.cancel()
    pilot_compute_service.cancel()