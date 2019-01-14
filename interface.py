#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
TODO: spostare tutto ciò che riguarda GPIO in machines.py onde evitare conflitti
'''
import curses, shutil, time, os
import dbhandler, logger

try:
	import RPi.GPIO as GPIO
	SIMULATED = False
except:
	from mockRPi import GPIO
	SIMULATED = True
	
from curses import panel
from math import ceil, floor
from decimal import Decimal

os.environ.setdefault('ESCDELAY', '25')

IFACE = '-I---'
locale = "it"
l10n = __import__("locale_" + locale)
nullMachine = '-'*12

W,H = shutil.get_terminal_size()

pageDict = {}
machinePages = []
activePage = None
previousPage = None
triggers = {
	'quit':False,
	'checkrunning':False,
	'updatedrecipe':False,
	'panic':False,
	'updateui':False,
	'removedmachine':False
}


class Menu:#(object):                                                          

	def __init__(self, menuname, items, page, r, c, width, horposition, maxentries):
		## Proprietà interne del menu
		if len(items) > maxentries:
			logger.error(IFACE,'Menu.__init__(): ho più items di quanti ne posso mettere!') 
		self.menuName = menuname
		self.items = items
		self.hasFocus = 0
		self.position = 0
		self.selectedEntry = self.items[self.position] 
		
		## Geometria e creazione della sottofinestra
		self.nlines = maxentries
		self.ncols = width
		
		self.window = page.derwin(self.nlines, self.ncols, r, c)
		self.window.box() #superfluo         
		
		logger.debug(IFACE+'.Menu', 'creato menu \''+self.menuName+'\'')                 
										
	def update(self):
		self.selectedEntry = self.items[self.position]
		
		self.window.erase()
		self.window.box()
		try:
			for row in range(1,self.nlines-1):
				self.window.addstr(row, 1, '-'*(self.ncols-2), curses.color_pair(1))
		except:
			logger.error(IFACE,'problemi nell\'inserire stringhe:')
			
		for index, item in enumerate(self.items):
			if index == self.position:
				if self.hasFocus:
					mode = curses.color_pair(10)
				else:
					mode = curses.color_pair(11)
			else:
				mode = curses.A_NORMAL
			
			msg = item + ' '*(self.ncols-len(item)-2)
			self.window.addstr(index+1, 1, msg, mode)
	
	def navigate(self, n):                                                   
		self.position += n                                                   
		if self.position < 0:                                                
			self.position = 0                                                
		elif self.position >= len(self.items):                               
			self.position = len(self.items)-1 
		logger.debug(IFACE,'menu position = '+str(self.position))                               
		
	def refresh(self):
		self.update()

class SubMenu(Menu):
	
	def __init__(self, menuname, multiitems, mainmenu, parent, r, c, width, horposition, maxentries):
		## Proprietà interne del menu
		if max([len(items) for items in multiitems.keys()]) > maxentries:
			logger.error(IFACE,'Menu.__init__(): ho più items di quanti ne posso mettere!') 
		self.menuName = menuname
		self.multiitems = multiitems
		self.mainmenu = mainmenu
		
		self.hasFocus = 0
		self.position = 0
		self.updateItems()
		self.selectedEntry = self.items[self.position]
		
		## Geometria e creazione della sottofinestra
		self.nlines = maxentries
		self.ncols = width

		self.window = parent.derwin(self.nlines, self.ncols, r, c)
			
	def updateItems(self):
		self.items = []
		'''
		mainPosition = self.mainMenu.position
		mainItems = self.mainMenu.items
		self.mainEntry = mainItems[mainPosition]
		'''
		steps = self.multiitems[self.mainmenu.selectedEntry]
		## Gestisce l'eventualità che i nuovi step siano meno di quelli di prima
		if self.position >= len(steps):
			self.position = 0

		for step in steps:
			n = str(step['step'])
			dur = time.strftime('%H:%M:%S', time.gmtime(step['duration']))
			block = step['block']
			temp = str(int(step['temperature']))
			
			self.items.append('['+n+'] '+dur+' '+block+' @'+temp+'°C')
					
	def update(self):
		self.updateItems()
		self.selectedEntry = self.items[self.position]

		self.window.erase()
		self.window.box()
		try:
			for row in range(1,self.nlines-1):
				self.window.addstr(row, 1, '-'*(self.ncols-2), curses.color_pair(1))
		except:
			logger.exception(IFACE,'nyehhh')
			
		for index, item in enumerate(self.items):
			if index == self.position:
				if self.hasFocus:
					mode = curses.color_pair(10)
				else:
					mode = curses.color_pair(11)
			else:
				mode = curses.A_NORMAL
			
			msg = item + ' '*(self.ncols-len(item)-2)
			self.window.addstr(index+1, 1, msg, mode)


class TextEntry:
	def __init__(self, parent, r, c, length):
		self.hasFocus = 0
		self.textbox = parent.derwin(1, length, r, c)

	def setValue(self, value):
		self.textbox.erase()
		self.textbox.insstr(0, 0, str(value), curses.color_pair(1))
		
class Page(object):
	def __init__(self, title, associatedToolbar=None, height=None, width=W, prow=1, pcol=0):
		## Inizializzo le variabili per gestire menu, eventualmente multipli
		self.menuDict = {}
		self.textEntries = {}
		self.activeMenu = None
		
		self.menuPosDict = {}
		self.menuposition = 0
		
		## Controllo la toolbar
		self.toolbar = associatedToolbar
		if self.toolbar:
			htool = self.toolbar.h
		else:
			htool = 0
			
		## Geometria
		self.h = height if height else H-2-htool
		self.w = width
		
		## Creo la struttura via Curses
		self.page = curses.newwin(self.h, self.w, prow, pcol)
		self.panel = panel.new_panel(self.page)
		self.page.box()
		
		## Altre proprietà della pagina
		self.isActive = False
		self.title = title
		pageDict[title] = self
		
		logger.debug(IFACE,'creata pagina \''+title+'\' di dimensioni H='+str(self.h)+' righe e W='+str(self.w)+' colonne')
	
	def clear(self):
		self.page.clear()
		self.page.box()
		
	def show(self):
		## Viene gestito l'ordine di visualizzazione
		'''
		if activePage:
			activePage.hide()
		'''
		if self.toolbar:
			self.toolbar.panel.top()
		self.setActive()
		self.panel.top()
		
		## Eventuali menu vengono popolati/aggiornati
		if self.menuDict:
			self.refreshMenus()

	def hide(self): ## sarebbe più corretto chiamarla bottom()
		self.panel.bottom()
		if self.toolbar:
			self.toolbar.panel.bottom()
		
	def redrawwin(self): ## non mi dovrebbe servire più
		self.page.redrawwin()
		if self.toolbar:
			self.toolbar.redrawwin()
	
	def noutrefresh(self): ## non mi dovrebbe servire più
		self.page.noutrefresh()
		
		if self.toolbar:
			self.toolbar.noutrefresh()
		if self.menuDict:
			for menuname in self.menuDict.keys():
				self.menuDict[menuname].refresh()
		
	def addstr(self, r, c, string, mode=None):
		try:
			if mode:
				self.page.addstr(r, c, string, mode)
			else:
				self.page.addstr(r, c, string)
		except:
			logger.exception(IFACE,'Page.addstr(): errore inserendo \''+
							string+'\' alla posizione r'+str(r)+'c'+str(c)+'. Nota che la pagina ha W,H:'+str(self.w)+','+str(self.h))

			
	def subwin(self, nlines, ncols, begin_y, begin_x):
		self.page.subwin(nlines, ncols, begin_y, begin_x)
		
		
	def setActive(self):
		logger.debug(IFACE,self.title+' è stata resa attiva')
		global activePage, previousPage
		if activePage:
			previousPage = activePage
		activePage = self
		
	def addMenu(self, menuname, prow, pcol, items=None, multiitems=None, mainmenu=None, 
				width=15, active=False, horposition=None, maxentries=16):
		if mainmenu:
			menu = SubMenu(menuname, multiitems, mainmenu, self.page, prow, pcol, width, horposition, maxentries)
		else:
			menu = Menu(menuname, items, self.page, prow, pcol, width, horposition, maxentries)
		self.menuDict[menuname] = menu
		if active:
			self.setActiveMenu(menuname)
		if isinstance(horposition,int):
			self.menuPosDict[horposition] = menu
		
	def setActiveMenu(self, menuname):
		if self.activeMenu:
			self.activeMenu.hasFocus = 0
		self.activeMenu = self.menuDict[menuname]
		self.activeMenu.hasFocus = 1
	
	def navigateMenus(self, n):
		self.menuposition += n                                                   
		if self.menuposition < 0:                                                
			self.menuposition = 0                                                
		elif self.menuposition >= max(self.menuPosDict.keys()):                               
			self.menuposition = max(self.menuPosDict.keys()) 
		try:
			self.setActiveMenu(self.menuPosDict[self.menuposition].menuName)
		except:
			logger.exception(IFACE,'Page.navigateMenus()')
		logger.debug(IFACE,'menu number = '+str(self.menuposition))  
		
	def refreshMenus(self):
		logger.debug(IFACE+'.Page','refreshMenus()')
		for menu in self.menuDict.values():
			try:
				menu.refresh()
			except:
				logger.exception(IFACE+'.Page','impossibile refreshare il menu '+menu.menuName)
			
	def addTextEntry(self, textentryname, r, c, length):
		self.textEntries[textentryname] = TextEntry(self.page, r, c, length)

class TemplatePage(Page): 
	def updateValues(self):
		logger.info(IFACE,self.title+' sta eseguendo updateValues(self)')
		menu = self.activeMenu
		stats = {'id':'ID', 'motpin':'MOT', 'rotpin':'ROT', 'th1pin':'TH1', 'th2pin':'TH2', 'a0':'a0', 'a1':'a1', 'a3':'a3'}
		self.selectedTemplateStats = {}
		templatefromDB = {}
		
		if menu.selectedEntry == nullMachine:
			for dbstat in stats.keys():
				templatefromDB[dbstat] = 0
		else:
			templatefromDB = DB.getTemplate(menu.selectedEntry)
		
		for dbstat in stats.keys():
			self.selectedTemplateStats[dbstat] = templatefromDB[dbstat]
			if not (dbstat == 'id' or dbstat == 'name'):
				self.textEntries[stats[dbstat]].setValue(self.selectedTemplateStats[dbstat])


class MachinePage(Page):
	def __init__(self, title, associatedToolbar, machine):
		super(MachinePage, self).__init__(title, associatedToolbar)
		self.machinename = title.replace('machine_','')
		self.machine = machine
		self.template = self.machine.template
		self.thermometer = self.machine.thermometer
		self.gaugesBox = GaugesBox( parent=self )

		self.addstr( 2,3, l10n.machine['loadedrecipe'] )
		self.addstr( 5,3, l10n.machine['currentblock'] )
		self.addstr( 8,3, l10n.machine['currentstep'] )
		self.addstr( 11,3,l10n.machine['targettemp'] )
		self.addstr( 14,3,l10n.machine['cooldowntime'] )
		
		self.addstr( 2,36, l10n.machine['status'] )
		self.updateRecipeStats()
		self.updateStatus()

	def setRecipe(self, recipe):
		logger.debug(IFACE,'setRecipe('+str(recipe)+')')
		try:
			DB.setMachineStat( self.machinename, 'recipe', recipe )
			if recipe:
				DB.setMachineStat( 
					self.machinename,
					('block','step','progress','blockprogress'),
					(1,1,0.0,0.0)
				)
			else:
				DB.setMachineStat( 
					self.machinename,
					('block','step','progress','blockprogress'),
					(None,None,None,None)
				)
		except:
			logger.exception(IFACE,'errore nell\'impostare la ricetta')

	'''
	def reset(self):
		m = self.machinename
		DB.setMachineStat( m, ['recipe','block','step'], [None]*3)
	'''

	def updateStatus(self):
		## Eliminato l'aggiornamento di self.machine, che è stato spostato fuori per evitare sovraccarico
		self.isRunning = self.machine.isRunning
		self.addstr( 3,36, ' '*15)
		
		if self.isRunning:
			self.addstr( 3,36, l10n.machine['active'], curses.color_pair(2) )
		else:
			self.addstr( 3,36, l10n.machine['idle'], curses.color_pair(1) )

	def updateRecipeStats(self):
		## Eliminato l'aggiornamento di self.machine, che è stato spostato fuori per evitare sovraccarico
		self.recipename = self.machine.recipe
		for i in (3,6,9):
			self.addstr( i,3, ' '*22)
		
		## Ricetta caricata
		if self.machine.recipe:
			self.addstr( 3,3, self.machine.recipe, curses.color_pair(2))
		else: 
			self.addstr( 3,3, l10n.machine['norecipe'], curses.color_pair(1))

		## Blocco attuale
		if self.machine.block:
			if not (self.machine.blockprogress is None or self.machine.blockDuration is None):
				blockprogress = str(round(self.machine.blockprogress,1))
				blockDuration = str(round(self.machine.blockDuration,1))
			else:
				blockprogress,blockDuration = '---','---'
			self.addstr( 6,3, 
				str(self.machine.block)+'/'+str(self.machine.nBlocks)+
				'  ('+blockprogress+'/'+blockDuration+')'
				, curses.color_pair(2))
		else:
			self.addstr( 6,3, '----', curses.color_pair(1))
			
		## Step attuale
		if self.machine.step and self.machine.schedule:
			if not (self.machine.progress is None or self.machine.stepDuration is None):
				progress = str(round(self.machine.progress,1))
				stepDuration = str(round(self.machine.stepDuration,1))
			else:
				progress,stepDuration = '---','---'
			self.addstr( 9,3, 
				str(self.machine.step)+'/'+str(len(self.machine.schedule))+
				'  ('+progress+'/'+stepDuration+')'
				, curses.color_pair(2))
		else:
			self.addstr( 9,3, '----', curses.color_pair(1))
			
		## Temperatura target
		if not self.machine.temperature is None:
			self.addstr( 12,3,
				str(round(self.machine.temperature,1))+'°C'
				, curses.color_pair(2))
		else:
			self.addstr( 12,3, '----       ', curses.color_pair(1))
			
		## Cooldown
		try:
			if self.machine.isResistorOn:
				self.addstr( 15,3,
					str(round(self.machine.currentHeatDuration,1))+'/'+
					str(round(self.machine.maxHeatTimeCorrected,1))
					, curses.color_pair(2))
			else:
				self.addstr( 15,3, '----       ', curses.color_pair(1))
		except:
			logger.exception(IFACE,'errore nel codice:')

			
	def toggleActivity(self):
		self.isRunning = self.machine.isRunning
		
		value = False if self.isRunning else True
		DB.setMachineStat( self.machinename, 'running', value )
		self.updateStatus()

	def setActive(self):
		super(MachinePage, self).setActive()
		self.updateRecipeStats()
		
	def tick(self):
		self.gaugesBox.update()
		
		## Aggiorna le informazioni sulla macchina, e con queste popola RecipeStats e Status
		self.updateRecipeStats()
		self.updateStatus()
		
class ConfirmDialog(Page):
	def __init__(self, title, height=6, width=30, prow=None, pcol=None):
		## Se non viene fornita la posizione defaulta al centro
		if not prow:
			prow = (H-height)//2
		if not pcol:
			pcol = (W-width)//2
		
		## Inizializza come da classe madre	
		super(ConfirmDialog, self).__init__(title, height=height, width=width, prow=prow, pcol=pcol)
		self.dialog = l10n.dialogs[title]
		self.build()
		
	def build(self):
		## Costruisci la finestra
		self.page.addstr(1, (self.w-len(self.dialog))//2, self.dialog)
		self.page.addstr(3, (self.w//3-len('Si')//2), 'Si', curses.A_REVERSE)
		self.page.addstr(3, (2*self.w//3-len('No')//2), 'No', curses.A_REVERSE)
		
	def askDialog(self):
		logger.debug(IFACE,'askDialog()')
		stdscr.nodelay(0)
		choice = None
		
		while True:
			key = stdscr.getkey()
			key = 'KEY_ESC' if key == '' else key
			if key == 's':
				stdscr.nodelay(1)
				choice = True
			elif key == 'n':
				stdscr.nodelay(1)
				choice = False
			elif key == 'KEY_ESC':
				stdscr.nodelay(1)
				choice = 'canceled'
			
			if not choice is None:
				logger.debug(IFACE,self.title+' risponde \''+str(choice)+'\'')
				return choice
				
class ChooseDialog(ConfirmDialog):
	def __init__(self, title, items, height=6, width=34, prow=None, pcol=None):
		self.items = items
		super(ChooseDialog, self).__init__(title, height, width, prow, pcol)
	
	def build(self):
		self.page.addstr(1, (self.w-len(self.dialog))//2, self.dialog)
		self.chooser = Chooser(self.page, self.items)
		
	def askDialog(self):
		logger.debug(IFACE,'askDialog()')
		stdscr.nodelay(0)
		choice = None
		
		while True:
			key = stdscr.getkey()
			key = 'KEY_ENTER' if key == '\n' else key
			key = 'KEY_ESC' if key == '' else key
			logger.warning(IFACE,'ChooseDialog: premuto ['+key.upper()+']')
			if key == 'KEY_ENTER':
				stdscr.nodelay(1)
				choice = self.chooser.selectedEntry
			elif key == 'KEY_LEFT':
				self.chooser.navigate(1)
				self.chooser.update()
				refreshSome()
			elif key == 'KEY_RIGHT':
				self.chooser.navigate(-1)
				self.chooser.update()
				refreshSome()
			elif key == 'KEY_ESC':
				stdscr.nodelay(1)
				choice = 'canceled'

			if choice:
				logger.debug(IFACE,self.title+' risponde \''+str(choice)+'\'')
				return choice
				
class Chooser:
	def __init__(self, page, items):
		self.page = page
		self.items = items
		# ATTENZIONE! la scelta 'Nessun@' va deprecata, per la MachinePage c'è la funzione 'azzera'
		#self.items.insert(0, '('+l10n.FNone+')')
		self.position = 0
		self.selectedEntry = self.items[self.position]
		
		ccol = self.page.getmaxyx()[1]//2
		self.w = 22+2+6 #larghezza menu delle ricette + franco + ' < '+' > '
		self.win = self.page.derwin( 1,self.w, 3,ccol-self.w//2 )
		
		self.update()
		
	def navigate(self, n):                                                   
		self.position += n                                                   
		if self.position < 0:                                                
			self.position = len(self.items)-1                                                
		elif self.position >= len(self.items):                               
			self.position = 0
		logger.debug(IFACE,'chooser position = '+str(self.position))  

	def update(self):
		self.selectedEntry = self.items[self.position]

		self.win.erase()
		self.win.addstr( 0,0, ' < ', curses.A_REVERSE)
		self.win.insstr( 0,self.w-3, ' > ', curses.A_REVERSE)
		self.win.addstr( 0,(self.w-len(self.selectedEntry))//2 , self.selectedEntry )
	
class DynamicChooseDialog(ChooseDialog):
	'''
	Dialog particolare che consente di essere aggiornato
	'''
	def __init__(self, title, height=6, width=34, prow=None, pcol=None):
		super(DynamicChooseDialog, self).__init__(title, None, height, width, prow, pcol)
		
	def build(self):
		self.page.addstr(1, (self.w-len(self.dialog))//2, self.dialog)
	
	def update(self, items):
		self.items = items
		self.chooser = Chooser(self.page, self.items)		
		
class InputDialog(ConfirmDialog):
	'''
	Dialog che deve fornire una casella di testo, elemento TextBox
	'''
	def __init__(self, title, height=6, width=34, prow=None, pcol=None):
		super(InputDialog, self).__init__(title, height, width, prow, pcol)
		
	def build(self):
		self.page.addstr(1, (self.w-len(self.dialog))//2, self.dialog)
		self.textbox = TextBox(self.page)

	def askDialog(self):
		logger.debug(IFACE,'askDialog()')
		stdscr.nodelay(0)
		
		while True:
			key = stdscr.getkey()
			key = 'KEY_ENTER' if key == '\n' else key
			key = 'KEY_BACKSPACE' if key == '\b' else key
			key = 'KEY_ESC' if key == '' else key
			logger.warning(IFACE,'InputDialog: premuto ['+key.upper()+']')
			if key == 'KEY_ESC':
				stdscr.nodelay(1)
				logger.debug(IFACE,self.title+' risponde \'canceled\'')
				return 'canceled'
			if key == 'KEY_ENTER':
				stdscr.nodelay(1)
				logger.debug(IFACE,self.title+' risponde \''+self.textbox.string+'\'')
				return self.textbox.string
			elif key == 'KEY_BACKSPACE':
				self.textbox.backspace()
				self.textbox.update()
				refreshSome()
			else:
				self.textbox.add(key)
				self.textbox.update()
				refreshSome()
		
class TextBox:
	def __init__(self, page):
		self.page = page
		self.string = ''

		ccol = self.page.getmaxyx()[1]//2
		self.w = 22+2+6 #larghezza menu delle ricette + franco + ' < '+' > '
		self.win = self.page.derwin( 1,self.w, 3,ccol-self.w//2 )
		
		self.update()
		
	def add(self, key):
		self.string += key
		
	def backspace(self):
		self.string = self.string[:-1]

	def update(self):
		self.win.erase()
		self.win.insstr(0,0, self.string, curses.A_REVERSE)
		
class Gauge:
	def __init__(self, parentwindow, prow, pcol, pins):
		self.pins = pins
		self.win = parentwindow.derwin(1,1,prow,pcol)
		for pin in pins:
			GPIO.setup(pin,GPIO.IN)
		self.update()
		
	def getState(self):
		pinstate = []
		for pin in self.pins:
			pinstate.append(GPIO.input(pin))
		return all(pinstate)
		
	def update(self):
		self.win.erase()
		
		if self.getState():
			self.win.insstr(0,0,'o',curses.color_pair(3))
		else:
			self.win.insstr(0,0,'-',curses.color_pair(2))
		
		self.win.noutrefresh()
		
class TempReading:
	def __init__(self, parentwindow, prow, pcol, thermometer):
		self.win = parentwindow.derwin(1,3,prow,pcol)
		self.thermometer = thermometer
		self.update()
		
	def update(self):
		self.win.erase()
		if self.thermometer:
			temp = str(round(self.thermometer.getTemperature(),0))[:-2]
		else:
			temp = str(999)
		logger.debug(IFACE,'letta temperatura '+temp)
		spaces = ' '*(3-len(temp))
		self.win.insstr(0,0,spaces+temp)
		
		self.win.noutrefresh()
		
class ResistReading:
	def __init__(self, parentwindow, prow, pcol, thermometer):
		self.win = parentwindow.derwin(1,7,prow,pcol)
		self.thermometer = thermometer
		self.update()
		
	def update(self):
		self.win.erase()
		if self.thermometer and not SIMULATED:
			resist = str(round(self.thermometer.getResistance()/1000,4))
		else:
			resist = '--x--'
		self.win.insstr(0,0,resist)
		
		self.win.noutrefresh()
	
class GaugesBox:
	def __init__(self, parent):
		logger.debug(IFACE,'creazione di un GaugesBox')
		self.template = parent.template
		templatename = self.template['name']
		nrows, ncols = 6,19
		prow, pcol = 3,parent.w-ncols-2
		
		if self.template['rotpin']:
			nrows += 1
		try:
			self.win = parent.page.derwin(nrows,ncols,prow,pcol)
			self.win.box()
			self.gaugesDict = {}
			self.addstr(1, 1, l10n.machineDials['motor'])
			self.gaugesDict['MOT'] = Gauge( parentwindow=self.win, prow=1, pcol=ncols-2, 
											pins=[self.template['motpin']])
			last = nrows-2
			self.addstr(last-2, 1, l10n.machineDials['heater'])
			if self.template['th2pin']:
				self.gaugesDict['THM'] = Gauge( parentwindow=self.win, prow=last-2, pcol=ncols-2, 
												pins=[self.template['th1pin'],self.template['th2pin']])
			else:
				self.gaugesDict['THM'] = Gauge( parentwindow=self.win, prow=last-2, pcol=ncols-2, 
												pins=[self.template['th1pin']])
			if self.template['rotpin']:
				self.addstr(2, 1, l10n.machineDials['rotation'])
				self.gaugesDict['ROT'] = Gauge( parentwindow=self.win, prow=2, pcol=ncols-2, 
												pins=[self.template['rotpin']])	
												
			self.addstr(last-1, 1, l10n.machineDials['temperature'])
			self.addstr(last-1, ncols-3, '°C')
			self.tempReading = TempReading( parentwindow=self.win, prow=last-1, pcol=ncols-6, thermometer=parent.thermometer )
			
			self.addstr(last, 1, 'R')
			self.addstr(last, ncols-3, 'kΩ')
			self.resistReading = ResistReading( parentwindow=self.win, prow=last, pcol=ncols-10, thermometer=parent.thermometer )
			
		except Exception as e:
			logger.exception(IFACE,'qualcosa è andato storto:')
			cleanup()
			raise e
		
#		global gauges
#		gauges[templatename] = self.gaugesDict #serve se poi alla fine io aggiorno gaugeswindow in blocco? mi sa proprio di no
		
	def addstr(self, prow, pcol, string):
		self.win.addstr(prow,pcol,string)
		
	def noutrefresh(self):
		self.win.noutrefresh()
		
	def redrawwin(self):
		self.win.redrawwin()
		
	def update(self):
		try:
			for gauge in self.gaugesDict.keys():
				self.gaugesDict[gauge].update()
				
			self.tempReading.update()
			self.resistReading.update()
		except:
			logger.exception(IFACE,'GaugesBox ha fallito update()')
			
		self.win.noutrefresh()

class MachineListPage(Page):
	def setActive(self):
		logger.debug(IFACE,self.title+' è stata resa attiva')
		global activePage
		activePage = self
		
		self.updateList()
		
	def updateList(self):
		logger.debug(IFACE,self.title+' sta eseguendo updateList(self)')
		self.page.erase()
		self.page.box()
		self.addstr(2, 2, l10n.machinesMain.selectPrompt)
		
		i = 1
		try:
			machines = DB.getMachines()
			if machines == []:
				self.addstr(4, 4, l10n.machinesMain.noneConfigured)
				self.addstr(5, 4, l10n.machinesMain.pleaseConfigure)
			else:
				for machine in machines:
					name, template = machine
					self.addstr(3+i, 4, str(i)+'. '+name+' ('+template+')')
					i+=1
		except:
			logger.exception(IFACE,'updateList() di '+self.title+' non è andato a buon fine.')
			
class Toolbar:
	def __init__(self, buttonsDict):
		## Geometria della toolbar
		self.h = int(ceil(len(buttonsDict.keys())/4.0))
		self.w = W
		prow = H-1-self.h

		logger.debug(IFACE,'creazione di una toolbar alta '+str(self.h)+' dalla riga '+str(prow))
		
		## Creo la struttura via Curses
		self.toolbar = curses.newwin(self.h,W,prow,0)
		self.panel = panel.new_panel(self.toolbar)
		self.buildToolbar(buttonsDict)
		
	def buildToolbar(self, buttonsDict):
		i = 0
		for action in buttonsDict.keys():
			key = action
			description = buttonsDict[key][1]
			if key == ' ':
				key = l10n.spaceBar
			r = int(floor(i/4.0))
			logger.debug(IFACE,'[i='+str(i)+',r*W='+str(r*W)+'] inserimento di due stringhe sulla riga '+str(r)+
								' e colonne '+str((i*W//4) - (r*W))+' e '+str((i*W//4) - (r*W) + 3 +len(key)))
			self.toolbar.addstr(r, (i*W//4) - (r*W), '['+key.upper()+']', curses.A_REVERSE)
			self.toolbar.addstr(r, (i*W//4) - (r*W) + 3 +len(key), description)
			i += 1
			
	def redrawwin(self):
		self.toolbar.redrawwin()
	
	def noutrefresh(self):
		self.toolbar.noutrefresh()
		return

class MainToolbar(Toolbar):
	def __init__(self,buttonsDict):
		self.toolbar = curses.newwin(1,W,H-1,0)
		self.panel = panel.new_panel(self.toolbar)
		self.buildToolbar(buttonsDict)

def cmdHdlr(page, key):
	'''
	Redireziona l'input alla funzione di competenza.
	'''
	logger.warning(IFACE,'cmdHdlr: premuto ['+key.upper()+'], siamo in '+page.title)
	
	#####################
	### commonToolbar ###
	if key in l10n.commonToolbar.keys():
		cmdHdlrCommon(key)
	
	####################
	### machinesMain ###
	if page.title == 'machinesMain':
		cmdHdlrMachinesMain(key)
			
	########################
	### machineTemplates ###
	if page.title == 'machineTemplates':
		cmdHdlrMachineTemplates(key)
		
	#################			
	### machine_* ###
	if 'machine_' in page.title:
		cmdHdlrMachinePage(key)
		
	###############			
	### recipes ###
	if page.title == 'recipes':
		cmdHdlrRecipes(key)


def cmdHdlrCommon(key):
	'''
	Comandi della toolbar comune
	'''
	global triggers
	
	command = l10n.commonToolbar[key][0]
	if command == 'quit':
		pauseMachines()
		setActivePage('quitDialog')
		try:
			confirm = activePage.askDialog()
		except:
			logger.exception(IFACE,'')
			
		if confirm == True:
			triggers['quit'] = True
		else:
			setActivePage(previousPage.title)
	elif command == 'machines':
		setActivePage('machinesMain')
	elif command == 'recipes':
		setActivePage('recipes')
	elif command == 'panic':
		triggers['panic'] = True
	
def cmdHdlrMachinesMain(key):
	'''
	Comandi della pagina home delle macchine
	'''
	if key in l10n.machinesMainToolbar.keys():
		command = l10n.machinesMainToolbar[key][0]
		if command == 'addmachine':
			setActivePage('machineTemplates')
	else:
		try:
			key = int(key)
			logger.debug(IFACE,'cmdHdlr: indice = '+str(key-1)+', controllo se in '+str(range(0,len(machinePages))))
			if key-1 in range(0,len(machinePages)):
				setActivePage(machinePages[int(key)-1].title)
		except:
			logger.debug(IFACE,'cmdHdlr: ['+key+'] non era un numero.')

def cmdHdlrMachinePage(key):
	'''
	Comandi della pagina della macchina
	'''
	global triggers
	
	if ( key in l10n.machineToolbar.keys() ) or ( SIMULATED and key in l10n.machineToolbarFakeRPi.keys() ):
		command = l10n.machineToolbarFakeRPi[key][0]	# Include anche i comandi di machineToolbar
		machinePage = activePage
		
		if command == 'loadrecipe':
			setActivePage('recipeChooseDialog')
			try:
				recipe = activePage.askDialog()
			except:
				logger.exception(IFACE,'')
				
			if recipe == 'canceled':
				pass
			else:
				# TODO: controllare se la ricetta è non nulla
				# in caso aprire un confirmDialog "si vuole cambiare ricetta? quella corrente non è ancora terminata!"
				if l10n.FNone in recipe:
					machinePage.setRecipe(None)
				else:
					machinePage.setRecipe(recipe)
				machineManager.updateRecipes()
				updateMachineUI()
			setActivePage(previousPage.title)
			
		elif command == 'startstopschedule':
			if machinePage.recipename:
				machinePage.toggleActivity()
				triggers['checkrunning'] = True
				
		elif command == 'reset':
			pauseMachines()
			setActivePage('resetDialog')
			try:
				confirm = activePage.askDialog()
			except:
				logger.exception(IFACE,'')
			logger.debug(IFACE,'ResetDialog ha detto '+str(confirm))
			
			try:
				if confirm:
					machines.machineManager.reset(machinePage.machinename)
					unpauseMachines(exclude=machinePage.machinename)
				else:
					unpauseMachines()
			except:
				logger.exception(IFACE,'')
				
			setActivePage(machinePage.title)
			updateMachineUI()			
			
		elif command == 'removemachine':
			machinename = activePage.machinename
			setActivePage('remDialog')
			try:
				confirm = activePage.askDialog()
				if confirm:
					removeMachine(machinename)
					triggers['removedmachine'] = True
					setActivePage('machinesMain')
				else:
					setActivePage(previousPage.title)	
			except:
				logger.exception(IFACE,'')			
				
		elif command == 'skipto':
			machine = machinePage.machine
			# TODO: deve essere possibile farlo solo a macchina ferma
			setActivePage('skiptoDialog') # è un ChooseDialog
			try:
				kind = activePage.askDialog()
			except:
				logger.exception(IFACE,'')
				
			## Esci se premuto ESC, altrimenti prosegui
			if kind == 'canceled':
				pass
			else:
				try:
					kind = l10n.bspDict[kind]
					name = 'skipto'+kind+'Dialog'
					hasProgress = False
					
					## Se non è scelto un progresso, popola il Chooser
					if not 'progress' in kind:
						if kind == 'block':
							items = machine.getBlockList()
						elif kind == 'step':
							items = machine.getStepList()
						dialog = pageDict[name]
						dialog.update(items)
						
					## Mostra il dialog relativo alla scelta fatta e registra il valore immesso
					setActivePage(name)
					try:
						value = activePage.askDialog()
					except:
						logger.exception(IFACE,'')
						
					## Esci se premuto ESC
					if value == 'canceled':
						pass
					else:
						if kind == 'block':
							value = int(value.split(' ')[0])
							DB.setMachineStat( 
								machine.name,
								('block','step','blockprogress','progress'),
								(value,1,0,0)
							)						
						elif kind == 'step':
							value = int(value.split(' ')[0])
							DB.setMachineStat( 
								machine.name,
								('step','progress'),
								(value,0)
							)		
						elif kind == 'blockprogress':
							value = float(value)
							hasProgress = True
							DB.setMachineStat( 
								machine.name,
								('blockprogress','progress'),
								(value,0)
							)		
						elif kind == 'stepprogress':
							value = float(value)
							hasProgress = True
							DB.setMachineStat( machine.name, 'progress' , value )
													
						machineManager.updateRecipes(keepProgress=hasProgress)
						updateMachineUI()		
									
				except:
					logger.exception(IFACE,'(temporaneo): ')
			## Torna alla pagina della macchina
			setActivePage(machinePage.title)						
		
		elif command == 'settemperature':
			machine = machinePage.machine
			setActivePage('settempDialog')
			try: 
				temp = activePage.askDialog()
			except:
				logger.exception(IFACE,'???')
			
			if temp == 'canceled':
				pass
			else:
				try:
					temp = float(temp)
					machine.thermometer.setTemperature(temp)
				except:
					logger.exception(IFACE,'impossibile impostare la temperatura ('+temp+'definita')
			## Torna alla pagina della macchina
			setActivePage(machinePage.title)		
	
def cmdHdlrMachineTemplates(key):
	'''
	Comandi della pagina dei template delle macchine
	'''
	if key == 'KEY_UP':
		page.activeMenu.navigate(-1)
		page.refreshMenus()
		page.updateValues()
		refreshSome()
	elif key == 'KEY_DOWN':
		page.activeMenu.navigate(1)
		page.activeMenu.refresh()
		page.updateValues()
		refreshSome()
	elif key in l10n.machineTemplatesToolbar.keys():
		command = l10n.machineTemplatesToolbar[key][0]
		if command == 'loadmachine':
			inputDialog = InputDialog( 'inputDialog' )
			setActivePage('inputDialog')
			try:
				name = activePage.askDialog()
			except:
				logger.exception(IFACE,'problema nella textbox')
				
			try:
				'''
				MANCA IL CONTROLLO DELL'UNIVOCITÀ
				'''
				templatename = previousPage.activeMenu.selectedEntry
				#ID = page.selectedTemplateStats['ID']
				DB.newMachine(name, templatename)
				newMachinePage(name)
				setActivePage('machinesMain')
			except Exception as e:
				logger.exception(IFACE,'errore nell\'aggiungere la macchina:')
	
def cmdHdlrRecipes(key):
	'''
	Controlli della pagina delle ricette
	'''
	if key == 'KEY_UP':
		page.activeMenu.navigate(-1)
		page.refreshMenus()
		refreshSome()
	elif key == 'KEY_DOWN':
		page.activeMenu.navigate(1)
		page.refreshMenus()
		refreshSome()
	elif key == 'KEY_LEFT':
		page.navigateMenus(-1)
		page.refreshMenus()
		refreshSome()
	elif key == 'KEY_RIGHT':
		page.navigateMenus(1)
		page.refreshMenus()
		refreshSome()
	elif key in l10n.recipesToolbar.keys():
		command = l10n.recipesToolbar[key][0]
		if command == 'addtask':
			pass
		elif command == 'removetask':
			pass
		elif command == 'string':
			pass
		elif command == 'recipesave':
			pass	
	
	
def setup(M):
	'''
	Viene inizializzato curses e impostato il GPIO. 
	Vengono costruite le pagine tramite buildPages() e mostrata la schermata di benvenuto
	'''
	logger.info(IFACE,'setup()')
	global machines, machineManager
	machines = M
	machineManager = M.machineManager
	
	global stdscr, DB
	stdscr = curses.initscr()
	h,w = stdscr.getmaxyx()
	if not (H,W) == (h,w):
		logger.warning(IFACE,'curses ha inizializzato una finestra di dimensione diversa rispetto al terminale')
		logger.warning(IFACE,'per riferimento, terminale:'+str(H)+'x'+str(W)+', curses:'+str(h)+'x'+str(w))
	logger.info(IFACE,'inizializzata finestra di H='+str(H)+' righe e W='+str(W)+' colonne')
	curses.noecho()
	curses.cbreak()
	curses.curs_set(0)
	stdscr.nodelay(1)
	stdscr.keypad(True)
	
	curses.start_color()
	curses.use_default_colors()
	try:
		curses.init_pair(1, 245, -1)
		curses.init_pair(2, 51, -1)
		curses.init_pair(3, 214, -1)
		curses.init_pair(10, -1, 39)
		curses.init_pair(11, -1, 245)
	except:
		logger.warning(IFACE,'non sono riuscito a inizializzare i colori')
	
	GPIO.setmode(GPIO.BCM)
	GPIO.setwarnings(False)
	
	DB = dbhandler.DataBase('mdp.sqlite')
		
	try:
		buildPages(M)
	except Exception as e:
		logger.exception(IFACE,'errore nella costruzione delle pagine:')
		quitTrigger = True
		cleanup()
		raise e
	setActivePage('welcome')

def newMachinePage(name, machines):
	'''
	Funzione creata per ridurre l'ingombro in altre parti del codice
	'''
	machine = machines.machineManager.getMachine(name)
	page = MachinePage( title='machine_'+name , associatedToolbar=machineToolbar, machine=machine )
	machinePages.append(page)
	
def removeMachine(name):
	'''
	Cancella la macchina dall'interfaccia e dal DB
	'''
	logger.info(IFACE,'removeMachine(\''+name+'\')')
	DB.removeMachine(name)
	machinePages.remove(name)
	
def buildPages(M):
	'''
	Vengono create le pagine dell'interfaccia (incluse quelle relative
		a macchine e ricette salvate), i menu e le toolbar
	'''	
	logger.info(IFACE,'buildPages()')
	global commonToolbar, machineToolbar
	
	#########################
	### Topbar e toolbars ###
	topbar = Page('topbar', height=1, prow=0)
	commonToolbar = MainToolbar(l10n.commonToolbar)
	machinesMainToolbar = Toolbar(l10n.machinesMainToolbar)
	machineToolbar = Toolbar(l10n.machineToolbarFakeRPi) if SIMULATED else Toolbar(l10n.machineToolbar)
	machineTemplatesToolbar = Toolbar(l10n.machineTemplatesToolbar)
	recipesToolbar = Toolbar(l10n.recipesToolbar)
	
	######################################
	### Pagina generale delle macchine ###
	MachinesMain = MachineListPage('machinesMain', machinesMainToolbar)
	
	###########################
	### Pagina dei template ###
	## Crea l'oggetto curses
	MachineTemplates = TemplatePage('machineTemplates', machineTemplatesToolbar)
	
	## Definisce le entries come [riga, stringa, lunghezza del campo]
	entries = [
		[4,'MOT',2],[4,'ROT',2],[4,'TH1',2],[4,'TH2',2],
		[6,'a0', 6],[6,'a1', 6],[6,'a3', 13]	# da rivedere bene la lunghezza quando dovrò mettere la possibilità di modificare
		]
	c = 20 ## Colonna iniziale, decisa ad libitum invece di vedere la larghezza del menu
	
	for i in range(0,len(entries)):
		entry = entries[i]
		
		## Calcola la geometria dell'entry
		r = entry[0]
		if r > entries[i-1][0]:
			c = 20
		else:
			c += len(entries[i-1][1]) + entries[i-1][2] + 2 if i > 0 else 0
		text = entry[1]
		fieldlength = entry[2]
		
		## Aggiunge il testo e la casella per la modifica
		MachineTemplates.addstr(r,c,text)		    
		MachineTemplates.addTextEntry(text,r,c+len(text)+1,fieldlength)
	
	templates = DB.getAllTemplateNames()
	'''
	manca da gestire cosa succede se non ci sono templates salvati
	'''
	MachineTemplates.addstr( 2,5, 'Templates' )
	MachineTemplates.addMenu( menuname='templatelist',items=templates, prow=3, pcol=2, active=True )
	MachineTemplates.updateValues()
				
	#############################
	### Pagine della macchina ###
	try:
		savedMachines = DB.getMachines()
		if savedMachines:
			for machine in savedMachines:
				newMachinePage(machine[1],M)
	except:
		logger.exception(IFACE,'non è stato possibile caricare le macchine salvate:')
			
	##############################
	### Finestra delle ricette ###	
	recipes = DB.getRecipeNames()
	recipesteps = {}
	for name in recipes:
		recipesteps[name] = DB.getRecipeSteps(name)
	
	maincol, seccol = 2,26
	mainlen, seclen = len(l10n.recipes['recipes']), len(l10n.recipes['blocks'])
	maincen, seccen = maincol+mainlen//2, seccol+seclen//2
	
	Recipes = Page('recipes', recipesToolbar)
	Recipes.addstr( 2,maincen, l10n.recipes['recipes'] )
	Recipes.addstr( 2,seccen, l10n.recipes['blocks'] )
	Recipes.addMenu( menuname='recipelist', items=recipes, prow=3, pcol=2, width=22, active=True, horposition=0 )
	Recipes.addMenu( menuname='tasklist', multiitems=recipesteps, mainmenu=Recipes.menuDict['recipelist'], prow=3, pcol=26, width=34, horposition=1 )
	Recipes.activeMenu = Recipes.menuDict['recipelist']

	############################
	### Pannelli di conferma ###
	QuitDialog = ConfirmDialog( 'quitDialog' )
	ResetDialog = ConfirmDialog( 'resetDialog' )
	RecipeChooseDialog = ChooseDialog( 'recipeChooseDialog' , items=recipes )
	RemoveDialog = ConfirmDialog( 'remDialog' )
	SkipToDialog = ChooseDialog( 'skiptoDialog', items=l10n.skiptoDialog )
	SkipToBlockDialog = DynamicChooseDialog( 'skiptoblockDialog' )
	SkipToStepDialog = DynamicChooseDialog( 'skiptostepDialog' )
	SkipToBlockProgressDialog = InputDialog( 'skiptoblockprogressDialog' )
	SkipToStepProgressDialog = InputDialog( 'skiptostepprogressDialog' )
	SetTempDialog = InputDialog( 'settempDialog' )

	###########################
	### Pagina di benvenuto ###
	Welcome = Page('welcome', None)
	Welcome.page.addstr(2, 2, l10n.welcome.welcome)
	Welcome.page.addstr(3, 2, l10n.welcome.whatdo)
	
def cleanup():
	'''
	Viene riportato il terminale allo stato originario e chiuso il DB.
	'''
	logger.info(IFACE,'cleanup()')
	curses.nocbreak()
	curses.echo()
	curses.endwin()
	
	DB.close()

def setTitle(title):
	'''
	Pulisce la barra superiore e applica il titolo fornito
	'''
	topbar = pageDict['topbar']
	logger.info(IFACE,'setTitle(\''+title+'\')')
	topbar.page.erase()
	topbar.addstr(0,(W-len(title))//2,title)
	topbar.show()
	
def tick():
	'''
	Insieme di comandi da eseguire fra uno sleep e l'altro:
		- se in primo piano, aggiorna lo stato delle macchine
		- passa eventuali tasti premuti al commandHandler
		- TODO: se sono caricate macchine, visualizzare in una trayzone 
			lo stato con un carattere colorato, esempio:
			
			------------------TITOLO--------------ooo
			------------------TITOLO--------------#$&
		- ...
	'''
	## Se è aperta una macchina, aggiorna le stats non collegate al DB
	if 'machine_' in activePage.title:
		activePage.gaugesBox.update()
		refreshSome()
	
	try:
		char = stdscr.getkey() 
		cmdHdlr(activePage,char)
	except:
		pass

def updateMachineUI():
	'''
	Conferma di essere nella pagina della macchina, e aggiorna le statistiche.
	'''
	if 'machine_' in activePage.title:
		activePage.tick()
		refreshSome()
	
def pauseMachines():
	machines.machineManager.pauseAll()
	
def unpauseMachines(exclude=None):
	machines.machineManager.unpauseAll(exclude)
	
def refreshSome():
	'''
	Funzione temporanea, devo capire cosa bisogna fare per aggiornare 
	correttamente, fare una funzione adeguata ed eliminare questa
	'''
	#logger.info(IFACE,'refreshSome()')
	
	activePage.redrawwin()
	activePage.noutrefresh()

	curses.doupdate()
	
def setActivePage(pageName):
	'''
	Aggiorna la topbar con setTitle(), poi trova l'oggetto Page corrispondente
	e lo porta in primo piano. Infine, aggiorna lo schermo.
	'''
	logger.info(IFACE,'setActivePage(\''+pageName+'\')')
	
	## Gestisce correttamente le pagine delle macchine ed esclude i popup
	if 'machine_' in pageName:
		setTitle(pageName.replace('machine_',''))
	elif not 'Dialog' in pageName:
		setTitle(l10n.pageTitles[pageName])
		
	page = pageDict[pageName]
	try:
		page.show()
	except:
		logger.exception(IFACE,'c\'è stato un problema con Page.show():')

	## Mettere questo sotto in una funzione diversa da usare anche quando aggiorno i menu?
	panel.update_panels()
	curses.doupdate()
	logger.debug(IFACE,'finito setActivePage()')	
	
if __name__ == '__main__':
	try:
		print('This bit of code is not meant to run by itself.')
		
	except KeyboardInterrupt: 
		pass
