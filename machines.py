#!/usr/bin/python3
# -*- coding: utf-8 -*-

'''
Modifiche: 
	piallare setActive - isRunning - Busy
	rendere coerenti block-step fra DB e qui
'''
import smbus, time, signal, sys, math #quanto di questo mi serve effettivamente?
import RPi.GPIO as GPIO
import logger
import dbhandler# as DB

MCHNS = '--M--'
triggers = {
	'quit':False,
	'checkrunning':False,
	'updatedrecipe':False,
	'panic':False,
	'updateui':False
}

class MachineManager:
	def __init__(self):
		self._machineDict = {}
		self.namesList = []
	
	def updateInventory(self):
		# rivedere per bene
		DBmachinesDict = DB.getTemplatesDict()
		DBNames = DBmachinesDict.keys()
		
		toRemove = [m for m in self.namesList if m not in DBNames]
		for machinename in toRemove:
			self.remove(machinename)
			
		toAdd = [m for m in DBNames if m not in self.namesList]
		for machinename in toAdd:
			template = DBmachinesDict[machinename]
			self.add(machinename,template)	
			
		self.updateRecipes()
	
	def add(self, machinename, templatename):
		machine = BreadMachine(machinename, templatename)
		self._machineDict[machinename] = machine
		self.namesList.append(machinename)
		
	def remove(self,machinename):
		logger.debug(MCHNS,'MachineManager.remove(\''+machinename+'\')')
		del self._machineDict[machinename]
		self.namesList.remove(machinename)
		
	def setRunning(self, machinename, isRunning):
		logger.debug(MCHNS,'MachineManager.setRunning()')
		machine = self._machineDict[machinename]
		machine.setRunning(isRunning)
		
	def updateRecipes(self, keepProgress=False): #togliere l'argomento
		'''
		TODO: rielaborare l'ordine di questa e tutte le funzioni collegate
		'''
		logger.debug(MCHNS,'MachineManager.updateRecipes()')
		
		## Recupera dal DB un dizionario con tutte le informazioni di tutte le macchine
		everyMachineStats = DB.getEveryMachineStats()	# eMS = { machinename: (recipe,block,step,progress,blockprogress) }
		for machinename in everyMachineStats.keys(): 
			try:
				## Estrae l'array con le stats della macchina in questione
				## 		e le applica alla macchina
				machineStats = everyMachineStats[machinename]
				machine = self._machineDict[machinename]
				machine.setMachineStatus(*machineStats)
				
				## Se è presente una ricetta, crea lo schedule relativo e prepara al primo avvio
				recipe = machineStats[0]
				if recipe:
						machine.updateSchedule()
						machine.firstStart = True
						#machine.resetTimes( keepProgress )
			
			except Exception as e:
				logger.exception(MCHNS,'errore caricando la ricetta per la macchina \''+machinename+'\'')
		
	def tick(self):
		#logger.debug(MCHNS,'MachineManager.tick()')
		for machine in self._machineDict.values():
			machine.tick()
			
	def stop(self,doPanic=False):
		# che cambia se è panic o no?
		if doPanic:
			logger.debug(MCHNS,'MachineManager.stop(PANIC!)')
		else:
			logger.debug(MCHNS,'MachineManager.stop()')
			
		for machine in self._machineDict.values():
			machine.setRunning(False)
			machine.syncMachine(withRunning=True)
		triggers['updateui'] = True
			
	def pauseAll(self):
		self.pauseStatuses = {}
		for machine in self._machineDict.values():
			self.pauseStatuses[machine] = machine.isRunning
			machine.setRunning(False)
			machine.syncMachine(withRunning=True)
		triggers['updateui'] = True
			
	def unpauseAll(self, exclude=None):
		excludedMachine = self._machineDict[exclude] if exclude else None
			
		for machine in self._machineDict.values():
			if machine != excludedMachine:
				machine.setRunning(self.pauseStatuses[machine])
				machine.syncMachine(withRunning=True)
		triggers['updateui'] = True
		
	def reset(self, machinename):
		machine = self._machineDict[machinename]
		machine.reset()
	
	def getMachine(self, machinename):
		return self._machineDict[machinename]
			
class TemperatureReading:
	def __init__(self, channel, a0, a1, a3, add=None, bus=None):
		self.resistance = 9850	# Valore misurato con multimetro
		self.zerocelsius = 273.15
		self.coefficients = [a0,a1,a3]
		self.channel = channel
		self.address = add if add else address
		self.bus = bus if bus else PCF8591
		
		self.bus.write_byte(self.address,self.channel)	# set I2C channel
		self.maxVoltage = 3.318 # Valore misurato con multimetro
		self.multiplier = self.maxVoltage / 256
		
	def useThis(self):
		self.bus.write_byte(self.address,self.channel)	# set I2C channel

	def getVoltage(self):
		self.useThis()
		Value8Bit = self.bus.read_byte(self.address)
		ValueReal = Value8Bit * self.multiplier
		return ValueReal
		
	def get8bitValue(self):
		self.useThis()
		return self.bus.read_byte(self.address)
		
	def getResistance(self):
		voltage = self.getVoltage()
		DV1 = self.maxVoltage - voltage
		current = DV1 / self.resistance
		resistance = voltage / current
		return resistance #in Ohm
	
	def getTemperature(self):
		r = self.getResistance()
		r = r if r>0 else 1
		[a0,a1,a3] = self.coefficients
		kelvinTemp = 1 / (a0 + a1 * math.log(r) + a3 * (math.log(r) ** 3))
		celsiusTemp = kelvinTemp - self.zerocelsius
		#logger.debug(MCHNS,'coeff: '+str(a0)+','+str(a1)+','+str(a3)+'; r='+str(r)+', log(r)='+str(math.log(r))+', log(r)^3='+str(math.log(r)**3)+', 1/T='+str((a0 + a1 * math.log(r) + a3 * (math.log(r) ** 3))))
		return celsiusTemp
		
class BreadMachine:
	def __init__(self, name, template):
		'''
		Viene creata la macchina, inizializzando tutti i suoi attributi,
		collegata al termometro e infine messa in attesa
		'''
		logger.debug(MCHNS, 'inizializzando la macchina \''+name+'\'')
		## Informazioni essenziali sulla macchina
		self.name = name
		self.template = DB.getTemplate(template)
		
		self.recipe, self.block, self.step, self.blockprogress, self.progress = [None]*5
		self.temperature, self.schedule = None, None
		self.nBlocks = None
		
		## Definisce i pin e gli array di pin
		self.MOT = self.template['motpin']
		self.ROT = self.template['rotpin']
		self.TH1 = self.template['th1pin']
		self.TH2 = self.template['th2pin']
		
		if self.TH2:
			self.HET = (self.TH1,self.TH2)
		else:
			self.HET = (self.TH1,)
		
		self.pins = []
		for pin in (self.MOT,self.ROT,self.TH1,self.TH2):
			if pin:
				self.pins.append(pin)
				GPIO.setup(pin,GPIO.OUT)
				GPIO.output(pin,0)
		
		## Definisce i parametri del termistore
		self.a0 = self.template['a0']
		self.a1 = self.template['a1']
		self.a3 = self.template['a3']
		self.chan = self.template['chan'] #0x02 ad esempio
		
		## Arresta la macchina se è rimasta accesa
		if DB.getMachineStat(self.name,'running'):
			logger.warning(MCHNS,'la macchina non è stata arrestata correttamente!')
			DB.setMachineStat(self.name,'running',0)

		## Variabili logiche
		self.isRunning = False
		self.justToggled = False
		self.firstStart = True
		
		self.isResistorOn = False
		self.firstResistorStart = True
		
		## Tempi di controllo e costanti di cooldown
		self.lastTimeResistorOff = 0
		self.lastTimeResistorOn = None
		
		self.tZero = 0
		self.tEndSchedule = 0
		self.iPause = None #non 0 altrimenti pare che c'è una pausa dal 1970
		
		self.maxHeatTime, self.cooldownTime = 2,0 # Valori di base che verranno modificati in mustCoolDown()
		self.maxHeatTimeCorrected, self.cooldownTimeCorrected = self.maxHeatTime, self.cooldownTime
		self.tempAccuracy = 0.05

		## Inizializza il termometro, se è collegato
		try:
			self.thermometer = TemperatureReading(self.chan, self.a0, self.a1, self.a3)
		except:
			self.thermometer = None
			logger.exception(MCHNS,'errore nel creare il termometro')

		## Ferma tutto, ponendo la macchina in attesa
		self.stopEverything()
	
	def setMachineStatus(self, recipe=None, block=None, step=None, progress=None, blockprogress=None): # cambiare nome?
		logger.debug(MCHNS,'setMachineStatus(recipe='+str(recipe)+',block='+str(block)+',step='+str(step)+',progress='+str(progress)+',blockprogress='+str(blockprogress)+')')
		if not recipe is None:
			self.recipe = recipe
		if not block is None:
			self.block = block
		if not step is None:
			self.step = step
		if not progress is None:
			self.progress = progress
		if not blockprogress is None:
			self.blockprogress = blockprogress
			
	def updateSchedule(self):
		'''
		Viene creato lo schedule del blocco, a partire dalla ricetta self.recipe
		'''
		logger.debug(MCHNS,self.name+'.updateSchedule()')
		
		if not (self.recipe and self.block):
			logger.error(MCHNS,'updateSchedule(): si sta cercando di creare uno schedule senza i pezzi necessari!')
		
		self.nBlocks = len(DB.getRecipeSteps(self.recipe))
		self.blockDuration = DB.getBlockDuration(self.recipe,self.block)
		self.blockName = DB.getBlockName(self.recipe,self.block)
		self.temperature = DB.getTemperature(self.recipe,self.block)
		
		self.schedule = DB.getBlockSchedule(self.blockName)
		self.stepDuration = self.schedule[self.step][0]

		logger.debug(MCHNS,self.name+'.updateSchedule() ha impostato lo schedule: '+str(self.schedule))
		
	def resetTimes(self, keepProgress=False): 
		'''
		Funzione da chiamare al cambio di blocco, resetta i tempi di controllo
		iniziali e finali
		'''
		t = time.time()
		self.iSync = t
		
		## Se viene chiesto di mantenere il progresso, lo ripristina e inizia a contare
		##		la pausa in attesa dell'inizio del programma
		if keepProgress:
			self.iPause = t
			self.iBlock = t-self.blockprogress
			self.iStep = t-self.progress
		else:
			self.iPause = None
			self.iBlock, self.iStep = t,t
				
		logger.info(MCHNS,'ora è '+str(round(t,1))+', la fine è schedulata a '+str(round(self.stepDuration,1)))
	
	def setMotor(self, out):
		logger.info(MCHNS,self.name+': setMotor('+str(out)+') ['+str(self.MOT)+']')
		GPIO.setup(self.MOT,GPIO.OUT)
		GPIO.output(self.MOT, out)
		self.mot = out
		
	def setRotation(self, out):
		logger.info(MCHNS,self.name+': setRotation('+str(out)+') ['+str(self.ROT)+']')
		if self.ROT:
			GPIO.setup(self.ROT,GPIO.OUT)
			GPIO.output(self.ROT, out)
		self.rot = out
	
	def setResistor(self, out):
		logger.info(MCHNS,self.name+': setResistor('+str(out)+') '+str(self.HET))
		## Se viene richiesta l'accensione, ed è la prima volta dopo un periodo di inattività, segna il tempo di ultimo off
		if out == 1:
			self.firstResistorStart = False
			if self.isResistorOn == False:
				self.lastTimeResistorOff = time.time()
			self.isResistorOn = 1
			self.lastTimeResistorOn = time.time()

		elif out == 0:
			if self.isResistorOn:
				self.lastTimeResistorOn = time.time()
			self.isResistorOn = 0
			self.lastTimeRestistorOff = time.time()

		for pin in self.HET:
			GPIO.setup(pin,GPIO.OUT)
			GPIO.output(pin, out)
					
	def mustCoolDown(self):
		'''
		Controlla se il resistore deve rimanere spento nonostante il 
		programma necessiti che sia acceso
		'''
		## Se è la prima volta che viene acceso, non è definito l'ultimo tempo di off, quindi skippa
		if self.firstResistorStart:
			return False
		
		## Calcola quanto tempo è stato acceso o spento
		currentTime = time.time()
		self.currentHeatDuration = currentTime - self.lastTimeResistorOff
		self.currentCoolDuration = currentTime - self.lastTimeResistorOn
		
		## Ottiene la temperatura e corregge i tempi di cooldown
		currentTemp = self.thermometer.getTemperature()
		targetTemp = self.temperature
		deltaTemp = (targetTemp - currentTemp)/currentTemp
		deltaTemp = deltaTemp if deltaTemp > 0 else 0
		
		heatCorrection = deltaTemp*10 if deltaTemp*10 < 5 else 5
		if deltaTemp > 0.1:
			coolCorrection = (deltaTemp ** -0.3)
		else:
			coolCorrection = 2
		self.maxHeatTimeCorrected = self.maxHeatTime + heatCorrection
		self.cooldownTimeCorrected = self.cooldownTime + coolCorrection
		
		## Definisce le booleane che definiscono i casi in cui debba essere spento
		triggerProtection = self.isResistorOn and self.currentHeatDuration > self.maxHeatTimeCorrected
		continueProtection = not self.isResistorOn and self.currentCoolDuration < self.cooldownTimeCorrected
		
		if triggerProtection or continueProtection:
			return True
		else:
			return False
		
	def getTemperature(self):
		if self.thermometer:
			temp = self.thermometer.getTemperature()
		else:
			temp = 999
		return temp
		
	def stopEverything(self):
		self.setMotor(0)
		self.setRotation(0)
		self.setResistor(0)
		
	def setRunning(self, run):
		'''
		Rende la macchina attiva/disattiva, dando di fatto l'ok
		all'esecuzione dello schedule, oppure determinandone l'arresto
		'''
		logger.debug(MCHNS, 'BreadMachine.setRunning('+str(run)+')')
		
		self.justToggled = True if not self.isRunning == run else False
		self.isRunning = True if run else False

	def reset(self):
		'''
		Cancella tutte le informazioni riguardo alla ricetta ed al progresso
		'''
		self.recipe = None
		self.block, self.step = None,None
		self.progress, self.blockprogress = None,None
		self.temperature, self.schedule = None,None
		self.syncMachine(withRecipe=True)

	def endRecipe(self):
		'''
		Conclude la fase di lavoro, arrestando e resettando la macchina
		'''
		logger.warning(MCHNS,'endRecipe()!')
		
		self.stopEverything()
		self.reset()
		self.setRunning(False)
		self.syncMachine(withRunning=True,withRecipe=True)
		triggers['updateui'] = True
		## altro...
		# triggers['goodjahb'] = True
		
	def getBlockList(self):
		'''
		Restituisce una lista dei blocchi con il loro nome'
		'''
		logger.debug(MCHNS,'getBlockList()')
		
		if self.recipe:
			blockList = DB.getBlockList(self.recipe)
		else:
			logger.error(MCHNS,'chiamato getBlockList() senza	avere una ricetta caricata!')
			blockList = ('')
			
		return blockList
		
	def getStepList(self):
		'''
		Restituisce una lista degli step con il loro nome'
		'''
		logger.debug(MCHNS,'getStepList()')
		
		if self.recipe:
			stepList = DB.getStepList(self.recipe, self.block)
		else:
			logger.error(MCHNS,'chiamato getStepList() senza	avere una ricetta caricata!')
			stepList = ('')
			
		return stepList
		
	def getTask(self):
		'''
		Restituisce l'array (mot,rot) noto, come attributo della macchina 
		stessa, lo stato in cui si trova
		'''
		mot = self.schedule[self.step][1]
		rot = self.schedule[self.step][2]
		return (mot,rot)
		
	def needHeat(self):
		'''
		Controlla se sia necessario fornire calore al forno
		'''
		T = self.getTemperature()
		targetT = self.temperature
		deltaT = (T-targetT)/T
		withinAccuracy = abs(deltaT) < self.tempAccuracy
		tooHot = abs(deltaT) > self.tempAccuracy and deltaT > 0
		
		return 0 if (withinAccuracy or tooHot) else 1

	def tick(self):
		'''
		Insieme di istruzioni da eseguire ad ogni ciclo. 
		Se la macchina è avviata, aggiorna il progresso e attua lo stato target
		Se la macchina è ferma, ed è appena stata fermata, definisce il tempo
		di inizio della pausa
		'''
		#logger.debug(MCHNS, 'BreadMachine.tick() (isRunning='+str(self.isRunning)+', justToggled='+str(self.justToggled)+')')
		t = time.time()

		## Caso in cui la macchina è running
		if self.isRunning:
			## La macchina è appena stata avviata?
			if self.justToggled:
				logger.debug(MCHNS,'tick(): justToggled!')
				## Se è il primo avvio della ricetta, definisci i tempi e azzera gli stati mot e rot
				if self.firstStart:
					self.resetTimes( keepProgress=True )
					#self.mot, self.rot = 0,0 ## ma non viene azzerata all'avvio del programma? ha senso?
					
					self.firstStart = False
					
				## Determina il tempo in cui è stata ifirstStartn pausa e sposta in avanti i tempi iniziali
				dPause = t-self.iPause if not self.iPause is None else 0
				logger.debug(MCHNS,'tick(): dPause='+str(dPause))
				self.iBlock += dPause
				self.iStep += dPause
				self.justToggled = False

			## Controllo a che punto siamo nel block e nello step
			tBlock = t-self.iBlock
			tStep = t-self.iStep
			self.blockprogress = tBlock

			if tBlock > self.blockDuration:
				## Abbiamo finito il blocco, passiamo al successivo (ammesso che ce ne sia uno)
				self.block += 1
				self.step = 1
				
				if self.block > self.nBlocks:
					self.endRecipe()
					return
					
				## Aggiorniamo lo schedule e i tempi
				self.updateSchedule() 
				self.resetTimes()
				tBlock = 0
				tStep = 0
				
			if tStep > self.stepDuration:
				## Abbiamo finito lo step, si passa al successivo o se non c'è si torna al primo
				## metto in conto il tempo che mi sono mangiato
				self.step += 1
				if self.step > list(self.schedule)[-1]:
					self.step = 1
					
				## Compenso il tempo extra passato nello step trascorso accorciando il seguente
				overshoot = tStep-self.stepDuration
				self.iStep = t-overshoot
				self.stepDuration = self.schedule[self.step][0]
				
				self.progress = overshoot
			else:
				## Lo step non è finito, semplicemente aggiorno il progresso
				self.progress = tStep
			
			## Prendo lo stato target e attuo motore e rotazione
			mot,rot = self.getTask()
			if not mot == self.mot:		## Evito di spammare comandi al GPIO se non necessario
				self.setMotor(mot)
			if not rot == self.rot:
				self.setRotation(rot)
			
			## Prendo lo stato target della resistenza e, se non devo spegnerla per cooldown, lo attuo
			heat = self.needHeat()
			if self.mustCoolDown():
				if self.isResistorOn:
					self.setResistor(0)
			else:
				if not heat == self.isResistorOn:
					self.setResistor(heat)

			## Sincronizziamo lo stato della macchina con il DB non più di una
			##		volta al secondo e avvertiamo che c'è da aggiornare l'interfaccia
			dSync = t-self.iSync
			if dSync > 1:
				self.iSync = t
				self.syncMachine()
			triggers['updateui'] = True
		
		## Caso in cui la macchina non è running	
		else:
			## Controllo se è appena stata fermata, e in caso procedo con il mettere in pausa
			if self.justToggled:
				self.justToggled = False
				
				## Definisco il tempo d'inizio della pausa
				self.iPause = t
				
				## Fermo i segnali GPIO
				self.stopEverything()
				
				## Sincronizziamo lo stato della macchina con il DB e avvertiamo che c'è da aggiornare l'interfaccia
				self.syncMachine()
				triggers['updateui'] = True
				
		
	def syncMachine(self, withRunning=False, withRecipe=False):
		'''
		Scrive nel DB le informazioni base sullo stato della macchina
		Se richiesto, scrive anche lo stato di attività e la ricetta
		'''
		progress = round(self.progress,2) if not self.progress == None else None
		blockprogress = round(self.blockprogress,2) if not self.blockprogress == None else None
		statkeys = ['block','step','progress','blockprogress']
		statvals = [self.block, self.step, progress, blockprogress]
		if withRunning:
			statkeys.append('running')
			statvals.append(self.isRunning)
		if withRecipe:
			statkeys.append('recipe')
			statvals.append(self.recipe)

		DB.setMachineStat(self.name, statkeys, statvals)				
		
def setup():
	'''
	Vengono inizializzate le interfacce hardware. Viene creato il manager
	delle macchine e messo all'opera.
	'''
	logger.info(MCHNS,'setup()')
	
	global PCF8591, address, DB
	address = 0x48	# I2C-address of YL-40 PFC8591
	
	PCF8591 = smbus.SMBus(1)	# Create I2C instance and open the bus
	
	GPIO.setmode(GPIO.BCM)
	GPIO.setwarnings(False)
	
	DB = dbhandler.DataBase('mdp.sqlite')
	
	global machineManager
	machineManager = MachineManager()
	machineManager.updateInventory()
	
def checkRunning():
	'''
	Aggiorna lo stato on/pausa delle macchine prendendolo dal DB e applicandolo tramite
	il manager delle macchine.
	'''
	logger.info(MCHNS,'checkRunning()')
	
	runningDict = DB.getRunningDict()
	for machinename in runningDict.keys():
		machineManager.setRunning(machinename, runningDict[machinename])
	triggers['updateui'] = True

def updateRecipes():
	logger.info(MCHNS,'updateRecipes()')
	machineManager.updateRecipes()
	
def updateInventory():
	machineManager.updateInventory()
	
def tick():
	'''
	Raccoglie il tick da main.py e lo riporta al machineManager
	'''
	#logger.debug(MCHNS,'tick()')
	machineManager.tick()

def panic():
	logger.warning(MCHNS,'panic()!')
	machineManager.stop(doPanic = True)

def stop():
	logger.info(MCHNS, 'stop()')
	machineManager.stop()

if __name__ == '__main__':
	try:
		print('This bit of code is not meant to run by itself.')
		
	except KeyboardInterrupt: 
		pass

