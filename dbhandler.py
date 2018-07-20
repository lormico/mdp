#!/usr/bin/python3
# -*- coding: utf-8 -*-
'''
Attenzione! Manca del codice che controlli che una macchina inserita non abbia pin assegnati a più funzioni
'''
'''
deve controllare se :
	è impegnata
	quale programma sta facendo
	a che step è arrivato
	a che punto dello step è arrivato
inoltre deve salvare:
	ultimo programma eseguito con tutte le informazioni di sopra
	potrei semplicemente salvare tutto e smettere di aggiornare se non è impegnata
	gestire i crash:
		all'avvio del programma tutte le macchine devono essere messe in running = 0
		se lo step in cui risultano non è l'ultimo dello schedule allora la macchina è stata fermata prematuramente
'''
import sqlite3 #Import the SQLite3 module
import sys
import time #non dovrebbe servirmi
import logger
DBHDL = '---D-'
connections = []

class DataBase:
	
	def __init__(self, dbfile):
		self.dbfile = dbfile
		
		self.db = sqlite3.connect(self.dbfile,check_same_thread=False)
		self.db.text_factory = str
		self.db.row_factory = sqlite3.Row
		
		global connections
		connections.append(self)

		with self.db:
			cursor = self.db.cursor()
			cursor.execute('''CREATE TABLE IF NOT EXISTS templates(
				id INTEGER PRIMARY KEY, name TEXT unique, motpin INTEGER, rotpin INTEGER, 
				th1pin INTEGER, th2pin INTEGER, chan INTEGER, a0 REAL, a1 REAL, a3 REAL)''')
			cursor.execute('''CREATE TABLE IF NOT EXISTS machines(
				id INTEGER, name TEXT PRIMARY KEY, template TEXT, 
				running INTEGER, recipe TEXT, block INTEGER, step INTEGER, progress REAL)''')
			cursor.execute('''CREATE TABLE IF NOT EXISTS recipes(
				id INTEGER, step INTEGER, duration REAL, block TEXT, 
				temperature REAL, name TEXT unique)''')
			cursor.execute('''CREATE TABLE IF NOT EXISTS blocks(
				id INTEGER, step INTEGER, duration REAL, 
				motor INTEGER, rotation INTEGER, name TEXT)''')
			self.db.commit()
	
	def close(self):
		self.db.close()

	def newTemplate(self, name, motpin, rotpin, th1pin, th2pin, chan, a0, a1, a3):
		logger.debug(DBHDL, 'newTemplate(name=\''+name+'\',motpin=\''+str(motpin)+'\',rotpin=\''+str(rotpin)
						+'\',th1pin=\''+str(th1pin)+'\',th2pin=\''+str(th2pin)+'\',chan=\''+str(chan)
						+'\',a0=\''+str(a0)+'\',a1=\''+str(a1)+'\',a3=\''+str(a3)+'\')')
		with self.db:
			cursor = self.db.cursor()
			cursor.execute('''INSERT INTO templates(name, motpin, rotpin, th1pin, th2pin, chan, a0, a1, a3)
				VALUES(:name, :motpin, :rotpin, :th1pin, :th2pin, :chan, :a0, :a1, :a3)''',
				{'name':name,'motpin':motpin,'rotpin':rotpin,'th1pin':th1pin,'th2pin':th2pin,'chan':chan,'a0':a0,'a1':a1,'a3':a3})
			self.db.commit()

	def getTemplate(self, name):
		logger.debug(DBHDL,'getTemplate(\''+name+'\')')
		with self.db:
			cursor = self.db.cursor()
			cursor.execute('''SELECT id, name, motpin, rotpin, th1pin, th2pin, chan, a0, a1, a3 FROM templates
							   WHERE name=?''', (name,))
			return cursor.fetchone()
	
	def getMachine(self, name):
		#logger.debug(DBHDL, 'getMachine(\''+name+'\')')
		with self.db:
			cursor = self.db.cursor()
			cursor.execute('''SELECT id, name, template, running, recipe, block, step, progress
								FROM machines WHERE name=?''', (name,))
			return cursor.fetchone()
	
	def getMachineStat(self, machine, stat):
		logger.debug(DBHDL, 'getMachineStat(machine=\''+machine+'\',stat=\''+stat+'\')')
		with self.db:
			cursor = self.db.cursor()
			cursor.execute('''SELECT {} FROM machines WHERE name=?'''.format(stat),(machine,))
			return cursor.fetchone()[stat]
	
	def setMachineStat(self, machine,key,value):
		#logger.debug(DBHDL, 'setMachineStat(machine=\''+machine+'\',key=\''+str(key)+'\',value=\''+str(value)+'\')')
		with self.db:
			cursor = self.db.cursor()
			
			## se vengono fornite liste o tuple, gestisci tutto insieme
			if type(key) == list or type(key) == tuple:
				stats = list(zip(key,value))
				for stat in stats:
					key = stat[0]
					value = stat[1]
					if value == None:
						cursor.execute('''UPDATE machines SET {}=null WHERE name=?'''.format(key),((machine,)),)
					else:
						cursor.execute('''UPDATE machines SET {}=? WHERE name=?'''.format(key),((value,machine)),)
			
			## se invece è fornito un solo valore		
			else:
				if value == None:
					cursor.execute('''UPDATE machines SET {}=null WHERE name=?'''.format(key),((machine,)),)
				else:
					cursor.execute('''UPDATE machines SET {}=? WHERE name=?'''.format(key),((value,machine)),)
					
				self.db.commit()
	
	def getAllTemplateNames(self):
		logger.debug(DBHDL, 'getAllTemplateNames()')
		with self.db:
			cursor = self.db.cursor()
			cursor.execute('''SELECT name FROM templates''')
			names = [r[0] for r in cursor.fetchall()]
			return names
	
	def newMachine(self, name, template):
		logger.debug(DBHDL, 'newMachine(name=\''+name+'\',template=\''+template+'\')')
		with self.db:
			cursor = self.db.cursor()
			cursor.execute('''INSERT INTO machines(name, template)
							   VALUES(:name, :template)''',
							   {'name':name,'template':template})
			self.db.commit()
			
	def removeMachine(self, name):
		logger.debug(DBHDL, 'removeMachine(name=\''+name+'\')')
		with self.db:
			cursor = self.db.cursor()
			cursor.execute('''DELETE FROM machines WHERE name = ?''', (name,))

	def getMachines(self):
		logger.debug(DBHDL,'getMachines()')
		with self.db:
			cursor = self.db.cursor()
			cursor.execute('''SELECT name, template FROM machines''')
			return cursor.fetchall()

	def getTemplatesDict(self):
		logger.debug(DBHDL,'getTemplatesDict()')
		with self.db:
			cursor = self.db.cursor()
			cursor.execute('''SELECT name, template FROM machines''')
			rows = cursor.fetchall()
		names = [r['name'] for r in rows]
		templates = [r['template'] for r in rows]
		
		return dict(zip(names,templates))

	def getRunningDict(self):
		logger.debug(DBHDL,'getRunningDict()')
		with self.db:
			cursor = self.db.cursor()
			cursor.execute('''SELECT name, running FROM machines''')
			rows = cursor.fetchall()
		names = [r['name'] for r in rows]
		runnings = [r['running'] for r in rows]
		
		return dict(zip(names,runnings))

	def getRecipeStepProgressDict(self):
		with self.db:
			cursor = self.db.cursor()
			cursor.execute('''SELECT name, recipe, block, step, progress FROM machines''')
			rows = cursor.fetchall()
		names = [r['name'] for r in rows]
		recipes = [r['recipe'] for r in rows]
		blocks = [r['block'] for r in rows]
		steps = [r['step'] for r in rows]
		progresses = [r['progress'] for r in rows]
		dictionary = dict(zip(names,zip(recipes,blocks,steps,progresses)))
		
		logger.debug(DBHDL,'getRecipeStepProgressDict() returns '+str(dict))
		return dictionary

	def getBlockDuration(self, recipename, block):
		ID = self.getRecipeID(recipename)
		with self.db:
			cursor = self.db.cursor()
			cursor.execute('''SELECT duration FROM recipes WHERE id=? and step=?''', (ID,block))
			duration = cursor.fetchone()['duration']
		
		logger.debug(DBHDL,'getBlockDuration(\''+recipename+'\','+str(block)+') returns '+str(duration))
		return duration

	def getTemperature(self, recipename, block):
		ID = self.getRecipeID(recipename)
		with self.db:
			cursor = self.db.cursor()
			cursor.execute('''SELECT temperature FROM recipes WHERE id=? and step=?''', (ID,block))
			temperature = cursor.fetchone()['temperature']
		
		logger.debug(DBHDL,'getTemperature(\''+recipename+'\','+str(block)+') returns '+str(temperature))
		return temperature

	def getBlockName(self, recipename, block):
		ID = self.getRecipeID(recipename)
		with self.db:
			cursor = self.db.cursor()
			cursor.execute('''SELECT block FROM recipes WHERE id=? and step=?''', (ID,block))
		blockName = cursor.fetchone()['block']
		
		logger.debug(DBHDL,'getBlockName(\''+recipename+'\','+str(block)+') returns '+str(blockName))
		return blockName
		
	def getBlockSchedule(self, blockName):
		ID = self.getBlockID(blockName)
		with self.db:
			cursor = self.db.cursor()
			cursor.execute('''SELECT step, duration, motor, rotation FROM blocks WHERE id=? AND step<>0''', (ID,))
			rows = cursor.fetchall()
		steps = [r['step'] for r in rows]
		durations = [r['duration'] for r in rows]
		motors = [r['motor'] for r in rows]
		rotations = [r['rotation'] for r in rows]
		dictionary = dict(zip(steps,zip(durations,motors,rotations)))
		
		logger.debug(DBHDL,'getBlockSchedule(\''+str(blockName)+'\') returns '+str(dictionary))
		return dict(zip(steps,zip(durations,motors,rotations)))
		
	def getRecipeID(self, recipename):
		with self.db:
			cursor = self.db.cursor()
			cursor.execute('''SELECT id FROM recipes WHERE name=?''', (recipename,))
			ID = cursor.fetchone()['id']
		
		logger.debug(DBHDL,'getRecipeID(\''+recipename+'\') returns '+str(ID))
		return ID
		
	def getBlockID(self, blockname):
		with self.db:
			cursor = self.db.cursor()
			cursor.execute('''SELECT id FROM blocks WHERE name=?''', (blockname,))
			ID = cursor.fetchone()['id']
		logger.debug(DBHDL,'getBlockID(\''+blockname+'\') returns '+str(ID))
		return ID
	
	def getRecipeNames(self):
		with self.db:
			cursor = self.db.cursor()
			cursor.execute('''SELECT name FROM recipes WHERE step = 0''')
			names = [r[0] for r in cursor.fetchall()]
		return names
		
	def getRecipeSteps(self, name):
		ID = self.getRecipeID(name)
		with self.db:
			cursor = self.db.cursor()
			cursor.execute('''SELECT step, duration, block, temperature FROM recipes
							WHERE id = ? AND NOT step = 0''', (ID,))
			steps = cursor.fetchall()
		return steps
	
def close():
	for i in connections:
		try:
			i.close()
		except:
			logger.exception(DBHDL,'')
			
if __name__ == '__main__':
	try:
		#print('This bit of code is not meant to run by itself.')
		#newTemplate( name='Princess', motpin=22, rotpin=23, th1pin=17, th2pin=18, a0=0.0, a1=0.0, a3=0.0000257596 )
		#newTemplate( name='Girmi', motpin=22, rotpin=0, th1pin=17, th2pin=0, a0=0.0, a1=0.0, a3=0.0 )
		#setMachineStat('Girmi','recipe','Cottura')
		DB = DataBase('mdp.sqlite')
		print(str(len(DB.getRecipeSteps('Test'))))
	except KeyboardInterrupt: 
		pass
