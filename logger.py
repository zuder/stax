# -*- coding: utf-8 -*-
'''Logging module'''
import shared
import logging
logging.raiseExceptions = False
log = None
# set up logging to console
# create logger
def configure():
	log = logging.getLogger('stax')
	log.setLevel(logging.DEBUG)
	log.propagate=0

	# create file handler which logs even debug messages
	fh = logging.FileHandler('stax-%s.log' % shared.PROFILE)
	fh.setLevel(eval('logging.'+shared.LOG_LEVEL))
	# create console handler with a higher log level
	ch = logging.StreamHandler()
	ch.setLevel(logging.INFO)
	# create formatter and add it to the handlers
	fh.setFormatter(logging.Formatter('[%(levelname)s] (%(asctime)s) - %(message)s'))
	ch.setFormatter(logging.Formatter('[%(levelname)s] (%(asctime)s) - %(message)s'))
	# add the handlers to the logger
	log.addHandler(fh)
	log.addHandler(ch)
