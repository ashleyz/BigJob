""" B{PilotData Module}: Implementation of L{PilotData}, L{PilotDataService} and L{DataUnit}
""" 
import sys
import os
import logging
import uuid
import random
import threading
import time
import pdb
import Queue
from pilot.api.api import PilotError

sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))
from bigjob import logger
from pilot.api import PilotData, DataUnit, PilotDataService, State


""" Load file management adaptors """
from pilot.filemanagement.ssh_adaptor import SSHFileAdaptor 
try:
    from pilot.filemanagement.webhdfs_adaptor import WebHDFSFileAdaptor
except:
    logger.warn("WebHDFS package not found.") 
try:
    from pilot.filemanagement.globusonline_adaptor import GlobusOnlineFileAdaptor
except:
    logger.warn("Globus Online package not found.") 
    
try:
    from pilot.filemanagement.gs_adaptor import GSFileAdaptor
except:
    logger.warn("Goggle Storage package not found.") 


try:
    from pilot.filemanagement.s3_adaptor import S3FileAdaptor
except:
    logger.warn("Amazon S3 package not found.") 


#from pilot.coordination.advert import AdvertCoordinationAdaptor as CoordinationAdaptor
#from pilot.coordination.nocoord import NoCoordinationAdaptor as CoordinationAdaptor
from pilot.coordination.redis_adaptor import RedisCoordinationAdaptor as CoordinationAdaptor
from bliss.saga import Url as SAGAUrl


# generate global application id for this instance
application_id = "bigdata"


class PilotData(PilotData):
    """ B{PilotData} 
                
        This is the object that is returned by the PilotDataService when a 
        new PilotData is created based on a PilotDataDescription. A PilotData represents
        a finite amount of physical space on a certain resource. It can be populated
        with L{DataUnit}s.

        The PilotData object can be used by the application to keep track 
        of a pilot. A PilotData has state, can be queried, can be cancelled.
        
    """   
    
    PD_ID_PREFIX="pd-"   

        
    def __init__(self, pilot_data_service=None, pilot_data_description=None, pd_url=None):    
        """ 
            Initialize PilotData at given service url::
            
                ssh://<hostname>
                gsissh://<hostname>
                go://<hostname>
                gs://google.com
                s3://aws.amazon.com
            
            In the future more SAGA/Bliss URL schemes/adaptors are supported.        
        """ 
        self.id = None
        self.url = pd_url
        self.pilot_data_description = None
        self.pilot_data_service = pilot_data_service
        self.service_url=None
        self.size = None
        self.data_unit_description = None
        self.data_units={}
        self.security_context = None
        
        if pd_url==None and pilot_data_service!=None:      # new pd          
            self.id = self.PD_ID_PREFIX+str(uuid.uuid1())
            self.pilot_data_description = pilot_data_description
            self.url = CoordinationAdaptor.add_pd(CoordinationAdaptor.get_base_url(application_id)+":"+pilot_data_service.id, self)
        elif pd_url != None:
            logger.warn("Reconnect to PilotData: %s"%pd_url)
            dictionary = CoordinationAdaptor.get_pd(pd_url)
            if dictionary.has_key("security_context"):
                self.security_context=dictionary["security_context"]
            pd_dict = eval(dictionary["pilot_data"])
            for i in pd_dict:
                self.__setattr__(i, pd_dict[i])
            # A Pilot Data does not hold a direct reference to a Data Unit (only URL refs are stored)
            #du_dict = eval(dictionary["data_units"])
            #for i in du_dict:
            #    du_id = DataUnit._get_du_id(i)
            #    self.data_units[du_id] = None # TODO Restore DataUnit
                        
        self.__initialize_pilot_data()
        CoordinationAdaptor.update_pd(self)
    

    def cancel(self):        
        """ Cancel PilotData  """
        #self.__filemanager.delete_pilotdata()
        pass
    
     
    def get_url(self):
        return self.url
       
    
    def url_for_du(self, du):
        return self.service_url + "/" + str(du.id)
        

    def submit_data_unit(self, data_unit_description):
        """ creates a data unit object and initially imports data specified in data_unit_description """
        du = DataUnit(pilot_data=self, 
                      data_unit_description=data_unit_description)
        self.data_units[du.id]=du
        du.add_pilot_data(self)
        return du
   
    
    def list_data_units(self):
        """ List all data units of PD """
        du_urls = CoordinationAdaptor.list_du(self.url)
        return du_urls          
    
    
    def get_state(self):
        """ Return current state of PD """
        return self.__filemanager.get_state()
    
    
    def get_du(self, du_id):
        """ Returns Data Unit if part of Pilot Data """
        du_url = self.url + ":" + du_id
        du = DataUnit(du_url=du_url)
        return du
    
    
    def wait(self):
        """ Wait until PD enters a final state (Done, Canceled or Failed).""" 
        while 1:
            finish_counter=0
            result_map = {}
            dus = self.data_units.values()
            for du in dus: 
                du.wait()
                state = du.get_state()           
                #state = job_detail["state"]                
                if result_map.has_key(state)==False:
                    result_map[state]=1
                else:
                    result_map[state] = result_map[state]+1
                if self.__has_finished(state)==True:
                    finish_counter = finish_counter + 1                   
            logger.debug("PD ID: " + str(self.id) + " Total DUs: %s States: %s"%(len(dus), str(result_map)))
            if finish_counter == len(dus):
                break
            time.sleep(2)

    
    def export_du(self, du, target_url):
        """ Export Data Unit to a local directory """
        self.__filemanager.get_du(du, target_url)
            
                
    def put_du(self, du):
        logger.debug("Put DU: %s to Pilot-Data: %s"%(du.id,self.service_url))
        self.__filemanager.create_du(du.id)
        self.__filemanager.put_du(du)
        self.data_units[du.id] = du
        CoordinationAdaptor.update_pd(self)
        
        
    def remove_du(self, du):
        """ Remove pilot data from pilot data """
        if self.data_units.has_key(du.id):
            self.__filemanager.remove_du(du)
            del self.data_units[du.id]
        CoordinationAdaptor.update_pd(self)
        
    
    def copy_du(self, du, pd_new):
        pd_new.create_du(du)
        self.__filemanager.copy_du(du, pd_new)
        
        # update meta data at pd_new
        pd_new.data_units[du.id] = du
        CoordinationAdaptor.update_pd(pd_new)
        
    
    # END API methods
    ###########################################################################
    # Auxillary Methods

    def create_du(self, du):
        """ Create a new Data Unit within Pilot """
        self.__filemanager.create_du(du.id)
  
  
    def __initialize_pilot_data(self):
        
        if self.pilot_data_description!=None:
            self.service_url=self.pilot_data_description["service_url"]
            self.size = self.pilot_data_description["size"]
            
            # initialize file adaptor
            if self.service_url.startswith("ssh:"):
                logger.debug("Use SSH backend")
                self.__filemanager = SSHFileAdaptor(self.service_url)
            elif self.service_url.startswith("http:"):
                logger.debug("Use WebHDFS backend")
                self.__filemanager = WebHDFSFileAdaptor(self.service_url)
            elif self.service_url.startswith("go:"):
                logger.debug("Use Globus Online backend")
                self.__filemanager = GSFileAdaptor(self.service_url)
            elif self.service_url.startswith("gs:"):
                logger.debug("Use Google Cloud Storage backend")
                self.__filemanager = GSFileAdaptor(self.service_url, self.security_context)
            elif self.service_url.startswith("s3:") \
                or self.service_url.startswith("walrus:") \
                or self.service_url.startswith("swift:"):
                logger.debug("Use Amazon S3/Eucalyptus Walrus/SWIFT Storage backend")
                self.__filemanager = S3FileAdaptor(self.service_url, 
                                                   self.security_context, 
                                                   self.pilot_data_description)
            else:
                raise PilotError("No File Plugin found.")
            
            self.__filemanager.initialize_pilotdata()
            self.__filemanager.get_pilotdata_size()
            
            # Update security context
            self.security_context = self.__filemanager.get_security_context()
            

    def __get_pd_id(self, pd_url):
        start = pd_url.index(self.PD_ID_PREFIX)
        end =pd_url.index("/", start)
        return pd_url[start:end]


    
    def to_dict(self):
        pd_dict = {}
        pd_dict["id"]=self.id
        pd_dict["url"]=self.url
        pd_dict["pilot_data_description"]=self.pilot_data_description
        logger.debug("PS Dictionary: " + str(pd_dict))
        return pd_dict
    
    
    def __repr__(self):
        return self.service_url
    
    
    def __has_finished(self, state):
        state = state.lower()
        if state=="running" or state=="failed" or state=="canceled":
            return True
        else:
            return False
    
    @classmethod
    def create_pilot_data_from_dict(cls, pd_dict):
        pd = PilotData()
        for i in pd_dict.keys():
            pd.__setattr__(i, pd_dict[i])
        pd.__initialize_pilot_data()
        logger.debug("created pd " + str(pd))
        return pd
   
    
###############################################################################
COORDINATION_URL = "redis://localhost"

class PilotDataService(PilotDataService):
    """ B{PilotDataService} (PDS)
    
        Factory for creating pilot data
    
    """
    
    PDS_ID_PREFIX="pds-"

    # Class members
    __slots__ = (
        'id',             # Reference to this PJS
        'url',            # URL for referencing PilotDataService
        'state',          # Status of the PJS
        'input_data_unit'    # List of PJs under this PJS
        'affinity_list'   # List of PS on that are affine to each other
    )

    def __init__(self, coordination_url=COORDINATION_URL, pds_url=None):
        """ Create a PilotDataService

            Keyword arguments:
            pds_id -- restore from pds_id
        """        
        self.pilot_data={}
        CoordinationAdaptor.configure_base_url(coordination_url)
        if pds_url == None:
            self.id = self.PDS_ID_PREFIX + str(uuid.uuid1())
            application_url = CoordinationAdaptor.get_base_url(application_id)
            self.url = CoordinationAdaptor.add_pds(application_url, self)
        else:
            self.id = self.__get_pds_id(pds_url)
       


    def create_pilot(self, pilot_data_description):
        """ Create a PilotData 

            Keyword arguments:
            pilot_data_description -- PilotData Description:: 
            
                {
                    'service_url': "ssh://<hostname>/base-url/",               
                    'size': "1000"
                }
            
            Return value:
            A PilotData object
        """
        pd = PilotData(pilot_data_service=self, 
                       pilot_data_description=pilot_data_description)
        self.pilot_data[pd.id]=pd
        
        # store pilot data in central data space
        CoordinationAdaptor.add_pd(self.url, pd)        
        return pd
    
    
    def get_pilot(self, pd_id):
        """ Reconnect to an existing pilot. """
        if self.pilot_data.has_key(pd_id):
            return self.pilot_data[pd_id]
        return None


    def list_pilots(self):
        """ List all PDs of PDS """
        return self.pilot_data.values()
    

    def cancel(self):
        """ Cancel the PilotDataService.
            
            Keyword arguments:
            None

            Return value:
            Result of operation
        """
        for i in self.pilot_data.values():
            i.cancel()
 
 
    def wait(self):
        """ Wait until all managed PD (of this Pilot Data Service) enter a final state""" 

        for i in self.pilot_data.values():
            i.wait()
 
 
    def get_url(self):
        return self.url
 
    ###########################################################################
    # Non-API methods
    def to_dict(self):
        """ Return a Python dictionary containing the representation of the PDS 
            (internal method not part of Pilot API)        
        """
        pds_dict = self.__dict__
        pds_dict["id"]=self.id
        return pds_dict
 
 
    def __del__(self):
        self.cancel()         
            
    
    def __get_pds_id(self, pds_url):
        start = pds_url.index(self.PDS_ID_PREFIX)
        end =pds_url.index("/", start)
        return pds_url[start:end]

    
    def __restore_pd(self, pds_url):
        pd_list=CoordinationAdaptor.list_pd(pds_url) 
        for i in pd_list:
            pass
        

class DataUnit(DataUnit):
    """ B{DataUnit}
    
        This is the object that is returned by the ComputeDataService when a 
        new DataUnit is created based on a DataUnitDescription.

        The DataUnit object can be used by the application to keep track 
        of a DataUnit.

        A DataUnit has state, can be queried and can be cancelled.
    
        
    
        State model:
            - New: PD object created
            - Pending: PD object is currently updated  
            - Running: At least 1 replica of PD is persistent in a pilot data            
    """
    
    ## TODO
    # Currently, DU are stored in Redis in a hierachical tree structure:
    # <pds>:<pd>:<du>
    # In the future a DU can be possibly bound to multiple PD
    # Thus, it should be a top level entity
    # The lower levels of the hierarchy will only store references to the DU then
    
    
    DU_ID_PREFIX="du-"  

    def __init__(self, pilot_data=None, data_unit_description=None, du_url=None):
        """
            1.) create a new Pilot Data: pilot_data_service and data_unit_description required
            2.) reconnect to an existing Pilot Data: du_url required 
            
        """
        if du_url==None:
            self.id = self.DU_ID_PREFIX + str(uuid.uuid1())
            self.data_unit_description = data_unit_description        
            self.pilot_data=[]
            self.state = State.New
            self.data_unit_items = DataUnitItem.create_data_unit_list(self, self.data_unit_description["file_urls"]) 
            self.url = None

            if pilot_data!=None:
                # Allow data units that are not connected to a resource!
                self.url = CoordinationAdaptor.add_du(pilot_data.url, self)
                CoordinationAdaptor.update_du(self)
        else:
            self.id = DataUnit._get_du_id(du_url)
            self.url = du_url   
            logger.debug("Restore du: %s"%self.id)         
            self.__restore_state()
            
        self.transfer_threads=[]
               
            
    def cancel(self):
        """ Cancel the DU. """
        self.state = State.Done    
        if len(self.pilot_data) > 0: 
            CoordinationAdaptor.update_du(self)

            
    def add_file(self, file_url):
        item_list = DataUnitItem.create_data_unit_from_urls(None, [file_url])
        for i in item_list:
            self.data_unit_items.append(i)    
        if len(self.pilot_data) > 0: 
            for i in self.pilot_data:
                logger.debug("Update Pilot Data %s"%(i.get_url()))
                i.put_du(self)
            CoordinationAdaptor.update_du(self)
        
    def remove_file(self, file_url):
        # TODO
        #self.data_unit_items.remove(input_data_unit)
        if len(self.pilot_data) > 0:
            CoordinationAdaptor.update_du(self)

        
        
    def list(self):
        """ List all items contained in DU 
            {
                "filename" : { 
                                "pilot_data" : [url1, url2],
                                "local" : url
                             }
            }        
        """        
        base_urls = [i.url_for_du(self) for i in self.get_pilot_data()]
        result_dict = {}
        for i in self.data_unit_items:
            logger.debug("Process file: %s"%(i.filename))
            result_dict[i.filename]={
                                    "pilot_data": [os.path.join(j, i.filename) for j in base_urls],
                                    "local": i.local_url
                                    }
        return result_dict
    
   
    
    def get_state(self):
        """ Return current state of DataUnit """        
        return self.state  
    
    
    def wait(self):
        """ Wait until in running state 
            (or failed state)
        """
        logger.debug("DU: %s wait()"%(str(self.id)))
        # Wait for all transfers to finish
        for i in self.transfer_threads:
            i.join()
        
        # Wait for state to change
        while self.state!=State.Running and self.state!=State.Failed:
            logger.debug("State: %s"%self.state)
            time.sleep(2)
    
    
    def add_pilot_data(self, pilot_data):
        """ add DU to a certain pilot data 
            data will be moved into this data
        """
        transfer_thread=threading.Thread(target=self.__add_pilot_data, args=[pilot_data])
        transfer_thread.start()        
        self.transfer_threads.append(transfer_thread)
        
    
    def get_pilot_data(self):
        """ get a list of pilot data that have a copy of this PD """
        return self.pilot_data
    
    
    def export(self, target_url):
        """ simple implementation of export: 
                copies file from first pilot data to local machine
        """
        if len(self.pilot_data) > 0:
            self.pilot_data[0].export_du(self, target_url)
        else:
            logger.error("No Pilot Data for PD found")
    
    
    def get_url(self):
        """ Return URL that can be used to reconnect to Data Unit """
        return self.url
    
    ###########################################################################
    # BigData Internal Methods
    
    def to_dict(self):
        du_dict = self.__dict__
        du_dict["id"]=self.id
        return du_dict        
    
    
    def update_state(self, state):
        self.state=state
        
        if len(self.pilot_data) > 0: 
            CoordinationAdaptor.update_du(self)

    
    def __add_pilot_data(self, pilot_data):
        logger.debug("add du to pilot data")
        if len(self.pilot_data) > 0: # copy files from other pilot data
            self.pilot_data[0].copy_du(self, pilot_data)
        else: # copy files from original location
            pilot_data.put_du(self)
        self.pilot_data.append(pilot_data)
        self.state = State.Running
        
        self.url = CoordinationAdaptor.add_du(pilot_data.url, self)
        CoordinationAdaptor.update_du(self)
            
        
    @classmethod    
    def _get_du_id(cls, du_url):
        try:
            start = du_url.index(cls.DU_ID_PREFIX)
            end = du_url.find("/", start)
            if end==-1:
                end = du_url.find("?", start)
            if end==-1:
                end = len(du_url)
            return du_url[start:end]
        except:
            logger.error("No valid PD URL")
        return None
    

    def __restore_state(self):
        du_dict = CoordinationAdaptor.get_du(self.url)
        # Restore Data Unit
        self.data_unit_description = eval(du_dict["data_unit_description"])
        self.state = du_dict["state"]
        
        # Restore DataUnitItems
        data_unit_dict_list = eval(du_dict["data_unit_items"])
        self.data_unit_items = [DataUnitItem.create_data_unit_from_dict(i) for i in data_unit_dict_list]
        
        # restore Pilot Data
        pd_list = eval(du_dict["pilot_data"])
        self.pilot_data = [] 
        for i in pd_list:
            logger.debug("PD: "+str(i)) 
            pd = PilotData(pd_url=str(i))
            self.pilot_data.append(pd) 


    def __repr__(self):        
        return "PD: " + str(self.url) 
        + " \nData Units: " + str(self.data_unit_items)
        + " \nPilot Stores: " + str(self.pilot_data)
    
    

class DataUnitItem(object):
    """ DataUnitItem """
    DUI_ID_PREFIX="dui-"  
   
    def __init__(self, pd=None, local_url=None):        
        if local_url!=None:
            self.id = self.DUI_ID_PREFIX + str(uuid.uuid1())
            self.local_url = local_url   
            self.filename =  os.path.basename(local_url)    
            #if pd != None:
            #    self.url = pd.url + "/" + self.filename
        
        
    @classmethod    
    def __exists_file(cls, url):   
        """ return True if file at url exists. Otherwise False """
        file_url = SAGAUrl(url)
        if file_url.host == "":
            if os.path.exists(str(file_url)):
                return True
            else:
                return False            
        elif file_url.host=="localhost":
            if os.path.exists(file_url.path):
                return True
            else:
                return False
        else:            
            return True
        
    
    def __repr__(self):
        return str(self.__dict__) 
        
        
    ###########################################################################
    # Auxiliary Methods
    @classmethod
    def create_data_unit_list(cls, pd=None, urls=None):
        """ Creates a list of DUs from URL list
        """    
        du_list = []    
        for i in urls:            
            if cls.__exists_file(i):
                du = DataUnitItem(pd, i)
                du_list.append(du)
    
        return du_list
    
    @classmethod
    def create_data_unit_from_urls(cls, pd=None, urls=None):
        """ Creates a list of DUs from URL list
        """    
        du_item_list = []    
        for i in urls:            
            if cls.__exists_file(i):
                du = DataUnitItem(pd, i)
                du_item_list.append(du)
    
        return du_item_list
    
    
    @classmethod
    def create_data_unit_from_dict(cls, du_dict):
        du = DataUnitItem()
        logger.debug("Restore DU: " + str(du_dict))
        for i in du_dict.keys():
            logger.debug("Set attribute: %s", i)
            du.__setattr__(i, du_dict[i])
        return du
    
    
    def to_dict(self):
        du_dict = self.__dict__
        du_dict["id"]=self.id
        return du_dict
    
###################################################################################################    
# Tests
# Auxilliary testing methods
def __get_pd_url(du_url):
    url = du_url[:du_url.index(":du-")]
    return url

def __get_du_id(du_url):
    du_id = du_url[du_url.index("du-"):]
    return du_id

# Tests
def test_reconnect():
    du_url = "redis://localhost/bigdata:pds-f31a670c-e3f6-11e1-afaf-705681b3df0f:pd-f31c47b8-e3f6-11e1-af44-705681b3df0f:du-f4debce8-e3f6-11e1-8399-705681b3df0f"
    pd_url = __get_pd_url(du_url)
    du_id = __get_du_id(du_url)
    pd = PilotData(pd_url=pd_url)
    print str(pd.list_data_units())
    du = pd.get_du(du_id)
    
    #du = DataUnit(du_url="redis://localhost/bigdata:pds-32d63b2e-df05-11e1-a329-705681b3df0f:pd-37674138-df05-11e1-80d0-705681b3df0f:du-3b8d428c-df05-11e1-af2a-705681b3df0f")
    logger.debug(str(du.list()))

def test_data_unit_add_file():
    pilot_data_service = PilotDataService(coordination_url="redis://localhost/")
    pilot_data_description = {
                                "service_url": "ssh://localhost/tmp/pilot-" + str(uuid.uuid1()),
                                "size": 100                                   
                             }
    pd = pilot_data_service.create_pilot(pilot_data_description=pilot_data_description)
    
    # create data unit for output data
    output_data_unit_description = {
         "file_urls": [], 
         "file_url_patterns": ["test.txt"]                             
    }
    output_data_unit = pd.submit_data_unit(output_data_unit_description)
    output_data_unit.wait()
    logger.debug("Output DU: " + output_data_unit.get_url())
    pd_reconnect_url = __get_pd_url(output_data_unit.get_url())
    du_id = __get_du_id(output_data_unit.get_url())
    pd_reconnect = PilotData(pd_url=pd_reconnect_url)
    du_reconnect = pd_reconnect.get_du(du_id)
    du_reconnect.add_file("test.txt")
    
    
    

if __name__ == "__main__":
    test_data_unit_add_file()
    