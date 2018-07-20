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
		
	def updateRecipes(self):
		logger.debug(MCHNS,'MachineManager.updateRecipes()')
		recipesDict = DB.getRecipeStepProgressDict()
		for machinename in recipesDict.keys():
			machine = self._machineDict[machinename]
			recipe = recipesDict[machinename][0]
			if recipe:
				machine.nBlocks = len(DB.getRecipeSteps(recipe))
			machine.updateSchedule(recipesDict[machinename])
			machine.firstStart = True
		
		# l'interfaccia carica la ricetta
		# alla macchina serve lo schedule terra terra
		# grazie alla suddivisione delle ricette in blocchi è possibile fare dei minischedule
		# 
		# la macchina vede quale ricetta gli spetta
		# in realtà non gliene frega niente gli basta sapere quale blocco deve fare
		# se è vergine allora gli viene fornita la fase e basta, niente gestione di programmi interrotti
		# dalla ricetta prende la fase, in termini di
		#			( +secondi dal t0 della fase , blocco, Ttarget )		(e quindi deve registrare un tProgressoFase)
		# dal blocco crea lo schedule in termini di 
		#			( +secondi dal t0 del blocco , m, r )					(e quindi deve registrare un tProgressoBlocco)
		#
		# a meno che non è finita la fase che richiede la ripetizione di un determinato blocco:
		#	ogni tick adegua la macchina allo schedule del blocco, finché non esaurisce lo schedule, quindi ricomincia da capo
		# 
		# deve scrivere sul DB in tempo reale quale fase sta eseguendo, e a che punto sta nella fase 
		#				al resume si creerà un tempo ridotto per la fase, faccio partire direttamente il blocco ... 
		# inoltre bisogna che venga scritto anche a che punto sta nel blocco
		#				si crea un tempo zero fittizio (o una cosa del genere) in modo che il programma riprenda dove era rimasto
		#				all'interno del blocco
		
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
		self.channel = 3#channel
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
		self.block,	self.schedule = None, None
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
		
		self.fStep, self.fBlock = [None]*2

		self.maxHeatTime, self.cooldownTime = 1,2 # Valori di base che verranno modificati in mustCoolDown()
		self.tempAccuracy = 0.05

		## Inizializza il termometro, se è collegato
		try:
			self.thermometer = TemperatureReading(self.chan, self.a0, self.a1, self.a3)
		except:
			self.thermometer = None
			logger.exception(MCHNS,'errore nel creare il termometro')

		## Ferma tutto, ponendo la macchina in attesa
		self.stopEverything()
	
	def updateSchedule(self, recipeDict):
		'''
		Viene creato lo schedule del blocco, a partire dall'array recipeDict tipo
			[ 'recipe', #block, #step, progress ]
		'''
		logger.debug(MCHNS,self.name+'.updateSchedule('+str(recipeDict)+')')
		
		self.recipe, self.block, self.step, self.progress = recipeDict
		if not self.recipe:
			self.schedule = None
		else:
			self.blockDuration = DB.getBlockDuration(self.recipe,self.block)
			self.blockName = DB.getBlockName(self.recipe,self.block)
			self.temperature = DB.getTemperature(self.recipe,self.block)
			self.schedule = DB.getBlockSchedule(self.blockName)
		logger.debug(MCHNS,self.name+'.updateSchedule() ha impostato lo schedule: '+str(self.schedule))
		
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
		currentHeatDuration = currentTime - self.lastTimeResistorOff
		currentCoolDuration = currentTime - self.lastTimeResistorOn
		
		## Ottiene la temperatura e corregge i tempi di cooldown
		currentTemp = self.thermometer.getTemperature()
		targetTemp = self.temperature
		deltaTemp = (targetTemp - currentTemp)/currentTemp
		deltaTemp = deltaTemp if deltaTemp > 0 else 0
		
		heatCorrection = deltaTemp if deltaTemp < 5 else 5
		if deltaTemp > 0.25:
			if deltaTemp < 1:
				coolCorrection = deltaTemp ** -1
			else:
				coolCorrection = 1
		else:
			coolCorrection = 4
		maxHeatTimeCorrected = self.maxHeatTime + heatCorrection
		cooldownTimeCorrected = self.cooldownTime + coolCorrection
		
		## Definisce le booleane che definiscono i casi in cui debba essere spento
		triggerProtection = self.isResistorOn and currentHeatDuration > maxHeatTimeCorrected
		continueProtection = not self.isResistorOn and currentCoolDuration < cooldownTimeCorrected
		
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
		self.recipe, self.block, self.step, self.progress, self.schedule = [None]*5
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

	def updateTimes(self): # cambiare nome? resetTimes?
		'''
		Funzione da chiamare al cambio di blocco, resetta i tempi di controllo
		iniziali e finali
		'''
		t = time.time()
		self.iBlock, self.iStep = t,t
		
		## la fine del blocco viene dalla ricetta
		self.blockDuration = DB.getBlockDuration(self.recipe,self.block)
		self.fBlock = self.blockDuration
		
		## la fine dello step viene dallo schedule
		self.fStep = self.schedule[self.step][0]
		
		logger.info(MCHNS,'ora è '+str(round(t,1))+', la fine è schedulata a '+str(round(self.fStep,1)))
				
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
				## Se è il primo avvio della ricetta, definisci i tempi e azzera gli stati mot e rot
				if self.firstStart:
					self.updateTimes()
					self.mot, self.rot = 0,0
					self.firstStart = False

				## Determina il tempo in cui è stata in pausa e sposta in avanti i tempi iniziali
				dPause = t-self.iPause if not self.iPause == None else 0
				self.iBlock += dPause
				self.iStep += dPause
				self.justToggled = False

			## Controllo a che punto siamo nel block e nello step
			tBlock = t-self.iBlock
			tStep = t-self.iStep
			
			if tBlock > self.fBlock:
				## Abbiamo finito il blocco, passiamo al successivo (ammesso che ce ne sia uno)
				self.block += 1
				
				if self.block > self.nBlocks:
					self.endRecipe()
					return
					
				## Aggiorniamo lo schedule e i tempi
				self.updateSchedule((self.recipe, self.block, self.step, self.progress)) 
				self.updateTimes()
				tBlock = 0
				tStep = 0
				
			if tStep > self.fStep:
				## Abbiamo finito lo step, si passa al successivo o se non c'è si torna al primo
				## metto in conto il tempo che mi sono mangiato
				self.step += 1
				if self.step > list(self.schedule)[-1]:
					self.step = 1
					
				## Compenso il tempo extra passato nello step trascorso accorciando il seguente
				overshoot = tStep-self.fStep
				self.iStep = t-overshoot
				self.fStep = self.schedule[self.step][0]
				
				self.progress = overshoot
				
			else:
				## Lo step non è finito, semplicemente aggiorno il progresso
				self.blockprogress = tBlock
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

			## Sincronizziamo lo stato della macchina con il DB e avvertiamo che c'è da aggiornare l'interfaccia
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
		statkeys = ['block','step','progress']
		statvals = [self.block, self.step, progress]
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

