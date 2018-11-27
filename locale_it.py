from locale_keys import *
from collections import OrderedDict
spaceBar = 'spazio'
MNone = 'Nessuno'
FNone = 'Nessuna'

class welcome:
	welcome = 'Benvenuto!'
	whatdo = 'Usa la tastiera per le azioni riportate in fondo.'

'''
class command:
	machines = 'Macchine'
	leave = 'Esci'
	settings = 'Impostazioni'
	panic = 'Stop!'
	'''

recipes = {
	'recipes':'Ricette',
	'blocks':'Blocchi'
}

machine = {
	'loadedrecipe':'Ricetta caricata',
	'currentblock':'Blocco attuale',
	'currentstep':'Step attuale',
	'nextsteptime':'Tempo al prossimo blocco',
	'steptime':'Tempo nello step',
	'norecipe':'Nessuna',
	'status':'Stato',
	'active':'Attiva',
	'idle':'In attesa',
	'targettemp':'Temperatura target',
	'cooldowntime':'Tempo di cooldown'
}

pageTitles = {
	'machinesMain':'Macchine',
	'machineTemplates':'Template Macchina',
	'welcome':'Benvenuto!',
	'recipes':'Ricette'}
	
dialogs = {
	'quitDialog':'Sicuro di voler uscire?',
	'resetDialog':'Azzerare la macchina?',
	'recipeChooseDialog':'Scegli una ricetta:',
	'remDialog':'Eliminare la macchina?',
	'inputDialog':'Immettere robe:',
	'skiptoDialog':'Quale contatore modificare?',
	'skiptoblockDialog':'Seleziona il blocco:',
	'skiptostepDialog':'Seleziona lo step:',
	'skiptostepprogressDialog':'Immetti un tempo in secondi:',
	'skiptoblockprogressDialog':'Immetti un tempo in secondi:'
}

bspDict = {
	'Blocco':BLOCK,
	'Step':STEP,
	'Progresso del Blocco':BLOCKPROGRESS,
	'Progresso dello Step':STEPPROGRESS
}
	
skiptoDialog = [
	'Blocco',
	'Step',
	'Progresso del Blocco',
	'Progresso dello Step'
]
	
class machinesMain:
	selectPrompt = 'Seleziona una macchina:'
	noneConfigured = 'Nessuna macchina e\' stata configurata!'
	pleaseConfigure = 'Usare i tasti sotto descritti per configurarne una.'
	
commonToolbar = OrderedDict([
	('m',[MACHINES,'Macchine']),
	('r',[RECIPES,'Ricette']),
	(' ',[PANIC,'STOP!']),
	('e',[QUIT,'Esci'])])
	
machinesMainToolbar = {
	'a':[ADD_MACHINE,'Agg. Macchina']}
	
machineToolbar = OrderedDict([
	('c',[LOAD_RECIPE,'Carica Ricetta']),
	('p',[START_STOP_SCHEDULE,'Avvia/Pausa']),
	('z',[RESET,'Azzera']),
	('s',[SKIPTO,'Salta a']),
	('x',[REM_MACHINE,'Rim. Macchina'])]) #brutto nome
	
machineTemplatesToolbar = OrderedDict([
	('n',[NEW_MACHINE,'Nuova']),
	('c',[LOAD_MACHINE,'Carica']),
	('x',[CLR_MACHINE,'Cancella']),
	('d',[EDIT_MACHINE,'Modifica'])])
	
recipesToolbar = OrderedDict([
	('n',[NEW_RECIPE,'Nuova Ricetta']),
	('x',[REM_RECIPE,'Rimuovi Ric.']),
	('i',[INS_TASK,'Ins. Blocco']),
	('l',[REM_TASK,'Elim. Blocco'])])
	
'''	
ynDial = {
	's',
'''	
machineDials = {
	'motor':'Motore',
	'rotation':'Rotazione',
	'heater':'Resistenza',
	'temperature':'Temperatura'}
	
jobsToolbar = {
	'a':'Agg. Lavoro',
	'p':'Pausa/Avvia',
	'x':'Ferma Lavoro'}
	
machineBindings = {
	'a':'addJob',
	'p':'pauseJob',
	'x':'exitJob'}

if __name__ == '__main__':
	try:
		print("This bit of code isn't meant to run by itself.")
	except KeyboardInterrupt: 
		pass
