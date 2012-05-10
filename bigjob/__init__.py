import os
import sys
import logging
import traceback
version = "latest"

#READ config
SAGA_BLISS=False
try:
    import ConfigParser
    _CONFIG_FILE="bigjob.conf"
    _conf_file = os.path.dirname(os.path.abspath( __file__ )) + "/../" + _CONFIG_FILE
    _config = ConfigParser.ConfigParser()
    _config.read(_conf_file)
    default_dict = _config.defaults()
    
    ####################################################
    # logging
    logging_level = logging.FATAL
    BIGJOB_VERBOSE=None
    try: 
        BIGJOB_VERBOSE = int(os.getenv('BIGJOB_VERBOSE'))
        #print("BIGJOB_VERBOSE: %d"%BIGJOB_VERBOSE)
    except Exception:
        pass   
     
    if BIGJOB_VERBOSE==None: # use logging level defined in config file
        print "Read log level from bigjob.conf"
        level = default_dict["logging.level"]
        print("Logging level: %s"%level) 
        if level.startswith("logging."):
            logging_level = eval(level)     
    else:
        # 4 = DEBUG + INFO + WARNING + ERROR
        if BIGJOB_VERBOSE >= 4:
            print "set to DEBUG"
            logging_level = logging.DEBUG
        # 3 = INFO + WARNING + ERROR
        elif BIGJOB_VERBOSE == 3:
            logging_level = logging.INFO
        # 2 = WARNING + ERROR 
        elif BIGJOB_VERBOSE == 2:
            logging_level = logging.WARNING
        # 1 = ERROR ONLY
        elif BIGJOB_VERBOSE == 1:
            logging_level = logging.ERROR
        
      
    #print("Set logging level: %s"%(logging_level))
    logging.basicConfig(level=logging_level, datefmt='%m/%d/%Y %I:%M:%S %p',
               format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(name='bigjob')
    logger.setLevel(logging_level)
    #logging.basicConfig(level=logging_level)        
      
    saga = default_dict["saga"]
    if saga.lower() == "bliss":
        SAGA_BLISS=True    
        
except:
    print("bigjob.conf could not be read") 
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exc(limit=1, file=sys.stdout)
    
import socket
try:
    fn = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", 'VERSION')
    version = open(fn).read().strip()
    logger.info("Loading BigJob version: " + version + " on " + socket.gethostname())
except IOError:
    pass



# define external-facing API
from bigjob.bigjob_manager import bigjob as myBigjob
from bigjob.bigjob_manager import subjob as mySubjob


class subjob(mySubjob):
    pass


class bigjob(myBigjob):
    pass


try:
    from bigjob.bigjob_manager import description as myDescription
    class description(myDescription):
        pass
except:
    pass
