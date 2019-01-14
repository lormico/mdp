import logging, os

try:
	os.rename('mdp.debug.log','mdp.debug.0.log')
	os.rename('mdp.info.log','mdp.info.0.log')
except:
	pass

logger = logging.getLogger('log')
logger.setLevel(logging.DEBUG)

dh = logging.FileHandler('mdp.debug.log')
ih = logging.FileHandler('mdp.info.log')
dh.setLevel(logging.DEBUG)
ih.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(message)s')
form2 = logging.Formatter('%(created)f')
dh.setFormatter(formatter)
ih.setFormatter(formatter)
logger.addHandler(dh)
logger.addHandler(ih)

logger.info('Started logging')

def info(environment, string):
	logger.info('(III) ['+environment+'] '+string)

def debug(environment, string):
	logger.debug('(---) ['+environment+'] '+string)
	
def warning(environment, string):
	logger.warning('(WWW) ['+environment+'] '+string)
	
def error(environment, string):
	logger.error('(XXX) ['+environment+'] '+string)

def exception(environment, string):
	logger.exception('(EXC) ['+environment+'] '+string)
