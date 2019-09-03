#!/usr/bin/python
# -*- coding: utf8 -*-
import os
import sys
import re
import getopt
import posix_ipc as pos #raccourci module
i = 0
while i < 10000:
	try:
		fileVersServeur = pos.MessageQueue("/reponseSup"+str(i))
		fileVersServeur.unlink()
		print 'BIM'
	except pos.ExistentialError:
		A=1
	i = i + 1
