#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time, sys
from threading import Thread

import logger
MDP = 'M----'
logger.info(MDP,'python version: '+str(sys.version_info[0]))

import interface as I
import machines as M

quitTrigger = False
updatemachinesTrigger = False
triggers = {
	'quit':False,
	'checkrunning':False,
	'updatedrecipe':False,
	'panic':False,
	'updateui':False,
	'removedmachine':False
}

class MachineThread(Thread):
	
	def __init__(self):
		super(MachineThread, self).__init__()
		self._keepgoing = True
		
		try:
			M.setup()
		except:
			logger.exception(MDP,'nel setup del motore qualcosa è andato storto!')
			self.stop()
			I.cleanup()
			triggers['quit'] = True			
		
	def run(self):
		global triggers
		while (self._keepgoing):
			try:
				if triggers['panic']:
					M.panic()
					triggers['panic'] = False
				if triggers['checkrunning']:
					M.checkRunning()
					triggers['checkrunning'] = False
				if triggers['updatedrecipe']:
					M.updateRecipes()
					triggers['updatedrecipe'] = False
				if triggers['removedmachine']:
					M.updateInventory()
					triggers['removedmachine'] = False
				M.tick()
				
				if M.triggers['updateui']:
					triggers['updateui'] = True
					M.triggers['updateui'] = False
				time.sleep(0.1)
			except:
				logger.exception(MDP,'nel thread del motore qualcosa è andato storto!')
				self.stop()
				I.cleanup()
				triggers['quit'] = True
				
	def stop(self):
		M.stop()
		self._keepgoing = False
		
class InterfaceThread(Thread):
	
	def __init__(self, timeinterval=0.1):
		super(InterfaceThread, self).__init__()
		self._keepgoing = True
		self.timeinterval = timeinterval
		I.setup(M)
		
	def run(self):
		global triggers
		while (self._keepgoing):
			try:
				if triggers['updateui']:
					triggers['updateui'] = False
					I.updateMachineUI()
				I.tick()
				for trigger in triggers.keys():
					if I.triggers[trigger]:
						logger.warning(MDP,'raccolto trigger \''+trigger+'\'')
						triggers[trigger] = True
						I.triggers[trigger] = False
				time.sleep(self.timeinterval)
			except:
				logger.exception(MDP,'nel thread dell\'interfaccia qualcosa è andato storto!')
				self.stop()
				M.stop()
				triggers['quit'] = True
		
	def stop(self):
		I.cleanup()
		self._keepgoing = False

def setup():
	'''
	Viene aperta la connessione al database, e vengono avviati i thread 
	dell'interfaccia e delle macchine.
	'''
	global interfacethread, machinethread
	
	machinethread = MachineThread()
	interfacethread = InterfaceThread(timeinterval = 0.1)
	
	machinethread.start()
	interfacethread.start()
		
def mainLoop():
	while True:	
		if triggers['quit']:
			return
			
		time.sleep(0.05)
		
def cleanup():
	interfacethread.stop()
	machinethread.stop()
	
if __name__ == '__main__':
	try:
		logger.info(MDP,'Starting logging')
		setup()
		mainLoop()
		cleanup()
	except Exception as e:
		raise e
	except KeyboardInterrupt: 
		pass

