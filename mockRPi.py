from random import randint
import logger

MOCK = '----M'

class _GPIO(object):	 

	def __init__(self):
		logger.info(MOCK,'Caricato modulo mockRPi')
		for i in range(40):
			self._pins[i] = (self.Pin(i))
		
	class PWM():
		def __init__(self, channel=0, frequency=0):
			pass

		def start(self, dc):
			pass

		def stop(self):
			pass

		def ChangeDutyCycle(self, dc):
			pass

		def ChangeFrequency(self, frequency):
			pass

	# Values
	LOW = 0
	HIGH = 1

	# Modes
	BCM = 11
	BOARD = 10

	# Pull
	PUD_OFF = 20
	PUD_DOWN = 21
	PUD_UP = 22

	# Edges
	RISING = 31
	FALLING = 32
	BOTH = 33

	# Functions
	OUT = 0
	IN = 1
	SERIAL = 40
	SPI = 41
	I2C = 42
	HARD_PWM = 43
	UNKNOWN = -1

	# Versioning
	RPI_REVISION = 2
	VERSION = '0.5.6'
	
	# Pins
	class Pin():
		def __init__(self, channel, state=None):
			self.channel = channel
			self.state = state
			
	_pins = {}
	
	def setwarnings(self, a): pass

	def setmode(self, a): pass

	def getmode(self): return GPIO.BCM

	def setup(self, channel, mode, initial=0, pull_up_down=None): 
		self._pins[channel].mode = mode
		
		logger.debug(MOCK,"MOCK: Set pin mode "+str(channel)+"->"+str(mode))

	def input(self, a):
		logger.debug(MOCK,"MOCK: Asked for pin"+str(a)+"<-"+str(self._pins[a].state))
		return self._pins[a].state

	def cleanup(self, a=None): pass

	def output(self, channel, state):
		self._pins[channel].state = state
		logger.debug(MOCK,"MOCK: Set pin "+str(channel)+"->"+str(state))

	def wait_for_edge(self, channel, edge): pass

	def add_event_detect(self, channel, edge, callback=None, bouncetime=None): pass

	def add_event_callback(self, channel, callback=None): pass

	def remove_event_detect(self, channel): pass

	def event_detected(self, channel): return False

	def gpio_function(self, channel): return GPIO.OUT
	
GPIO = _GPIO()

class smbus():
	class SMBus():
		def __init__(self, bus=None, force=False):
			pass
	
		def write_byte_data(self, i2c_addr, register, value):
			pass
	
		def write_byte(self, i2c_addr, value):
			pass
		
		def read_byte_data(self, i2c_addr, register):
			return randint(0, 2**8)
	
		def read_byte(self, i2c_addr):
			return randint(0, 2**8)
	
		def read_word_data(self, i2c_addr, register):
			return [randint(0, 2**8)]*2
	
		def write_word_data(self, i2c_addr, register, value):
			pass
	
		def read_i2c_block_data(self, a, b, c):
			return [randint(0, 2**8)]*c
	
		def write_i2c_block_data(self, i2c_addr, register, data):
			pass
	
		def open(self, bus):
			pass
	
		def close(self):
			pass
