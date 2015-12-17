# -*- coding: utf-8 -*-
"""
	Partition a trajectory into individual events and pass each event 
	to an implementation of eventProcessor

	:Created:	7/17/2012
 	:Author: 	Arvind Balijepalli <arvind.balijepalli@nist.gov>
	:License:	See LICENSE.TXT
	:ChangeLog:
	.. line-block::
		15/12/15	KB	Bug fixes to baseline recalculation
		12/12/15	AB 	Recalculate baseline currents when drift checks are disabled and baseline detection is set to automatic.
		12/11/15 	AB 	Refactor code
		5/17/14		AB  Delete plotting support
		5/17/14		AB  Add metaMDIO support for meta-data and time-series storage
		2/14/14		AB 	Pass absdatidx argument to event processing to track absolute time of 
						event start for capture rate estimation.
		6/22/13		AB 	Use plotting hooks in metaEventPartition to plot blockade depth histogram in 
						real-time using matplotlib.
		4/22/13		AB 	Rewrote this class as an implementation of the base class metaEventPartition.
						Included event processing parallelization using ZMQ.
		9/26/12		AB  Allowed automatic open channel state calculation to be overridden.
						To do this the settings "meanOpenCurr","sdOpenCurr" and "slopeOpenCurr"
						must be set manually. If all three settings are absent or 
						set to 01, they are autuomatically estimated.
						Added "writeEventTS" boolean setting to control whether raw
						events are written to file. Default is ON (1)
		8/24/12		AB 	Settings are now read from a settings file that
						is located either with the data or in the working directory 
						that the program is run from. Each class that relies on the 
						settings file will fallback to default values if the file
						is not found.
		7/17/12		AB	Initial version
"""
import mosaic.utilities.util as util
import mosaic.utilities.mosaicLog as log
from  collections import deque

import metaEventPartition

class eventSegment(metaEventPartition.metaEventPartition):
	"""
		Implement an event partitioning algorithm by sub-classing the metaEventPartition class

		:Settings: In addition to the parameters described in :class:`~mosaic.metaEventPartition`, the following parameters from are read from the settings file (.settings in the data path or current working directory):

			- `blockSizeSec` :	Functions that perform block processing use this value to set the size of 
							their windows in seconds. For example, open channel conductance is processed
							for windows with a size specified by this parameter. (default: 1 second)
			- `eventPad` :		Number of points to include before and after a detected event. (default: 500)
			- `minEventLength` :	Minimum number points in the blocked state to qualify as an event (default: 5)
			- `eventThreshold` :	Threshold, number of SD away from the open channel mean. If the abs(curr) is less
							than 'abs(mean)-(eventThreshold*SD)' a new event is registered (default: 6)
			- `meanOpenCurr` :	Explicitly set mean open channel current. (pA) (default: -1, to 
							calculate automatically)
			- `sdOpenCurr` :		Explicitly set open channel current SD. (pA) (default: -1, to 
							calculate automatically)
			- `slopeOpenCurr` :	Explicitly set open channel current slope. (default: -1, to 
							calculate automatically)
	"""

	def _init(self, trajDataObj, eventProcHnd, eventPartitionSettings, eventProcSettings):
		"""
			Segment a trajectory
		"""
		# parse algorithm specific settings from the settings dict
		try:
			self.blockSizeSec=float(self.settingsDict.pop("blockSizeSec", 1.0))
			self.eventPad=int(self.settingsDict.pop("eventPad", 500))
			self.minEventLength=int(self.settingsDict.pop("minEventLength",5))
			self.eventThreshold=float(self.settingsDict.pop("eventThreshold",6.0))
			self.meanOpenCurr=float(self.settingsDict.pop("meanOpenCurr",-1.))
			self.sdOpenCurr=float(self.settingsDict.pop("sdOpenCurr",-1.))
			self.slopeOpenCurr=float(self.settingsDict.pop("slopeOpenCurr",-1.))
		except ValueError as err:
			raise commonExceptions.SettingsTypeError( err )

		# Calculate the threshold current from eventThreshold.
		self.thrCurr=(abs(self.meanOpenCurr)-self.eventThreshold*abs(self.sdOpenCurr))

		if self.driftThreshold < 0 or self.maxDriftRate < 0:
			self.enableCheckDrift=False
		else:
			self.enableCheckDrift=True


		#### Vars for event partition ####
		self.eventstart=False
		self.eventdat=[]
		self.preeventdat=deque(maxlen=self.eventPad)
		self.eventcount=0
		self.eventprocessedcount=0
	
	def _stop(self):
		pass

	def formatsettings(self):
		"""
			Return a formatted string of settings for display in the output log.
		"""
		logObj=log.mosaicLog()


		logObj.addLogHeader( 'Event segment settings:' )
		logObj.addLogText( 'Window size for block operations = {0} s'.format(self.blockSizeSec) )
		logObj.addLogText( 'Event padding = {0} points'.format(self.eventPad) )
		logObj.addLogText( 'Min. event rejection length = {0} points'.format(self.minEventLength) )
		logObj.addLogText( 'Event trigger threshold = {0:5.2f} * SD'.format(self.eventThreshold) )
		if self.enableCheckDrift:
			logObj.addLogText( 'Drift error threshold = {0} * SD'.format(self.driftThreshold) )
			logObj.addLogText( 'Drift rate error threshold = {0} pA/s'.format(self.maxDriftRate) )
		else:
			logObj.addLogText( 'Drift error threshold = ***disabled***' )
			logObj.addLogText( 'Drift rate error threshold = ***disabled***' )
	
		return str(logObj)

	def formatstats(self):
		"""
			Return a formatted string of statistics for display in the output log.
		"""
		logObj=log.mosaicLog()

		logObj.addLogHeader( 'Baseline open channel conductance:' )
		logObj.addLogText( 'Mean	= {0} pA'.format( round(self.meanOpenCurr,2) ) )
		logObj.addLogText( 'SD	= {0} pA'.format( round(self.sdOpenCurr,2) ) )
		logObj.addLogText( 'Slope 	= {0} pA/s'.format( round(self.slopeOpenCurr,2) ) )
		

		logObj.addLogText( 'Event segment stats:' )
		logObj.addLogText( 'Events detected = {0}'.format(self.eventcount) )

		logObj.addLogText( 'Open channel drift (max) = {0} * SD'.format(abs(round((abs(self.meanOpenCurr)-abs(self.maxDrift))/self.sdOpenCurr,2))) )
		logObj.addLogText( 'Open channel drift rate (min/max) = ({0}/{1}) pA/s'.format(round(self.minDriftR,2), round(self.maxDriftR)) )
		
		return str(logObj)

	def formatoutputfiles(self):
		logObj=log.mosaicLog()


		logObj.addLogSection( '[Output]' )
		logObj.addLogText( 'Output path = {0}'.format(self.trajDataObj.datPath) )
		logObj.addLogText( 'Event characterization data = '+ self.mdioDBHnd.dbFilename )
		if self.writeEventTS:
			logObj.addLogText( 'Event time-series = ***enabled***' )
		else:
			logObj.addLogText( 'Event time-series = ***disabled***' )

		return str(logObj)

	#################################################################
	# Interface functions
	#################################################################
	"""#@profile"""
	def _eventsegment(self):
		"""
			Cut up a trajectory into individual events. This algorithm uses
			simple thresholding. By working with absolute values of currents,
			we handle positive and negative potentials without switches. When the
			current drops below 'thrCurr', mark the start of the event. When the current
			returns to the baseline (obtained by averaging the open channel current
			immediately preceeding the start of the event), mark the event end. Pad 
			the event by 'eventPad' points and hand off to the event processing algorithm.
		"""
		try:
			while(1):
				t=self.currData.popleft()
				self.globalDataIndex+=1

				# store the latest point in a fixed buffer
				if not self.eventstart:
					self.preeventdat.append(t)
				
				# Mark the start of the event
				if abs(t) < self.thrCurr:
					#print "event",
					self.eventstart=True
					self.eventdat=[]
					self.eventdat.append(t)
					self.dataStart=self.globalDataIndex-len(self.preeventdat)-1

				if self.eventstart:
					mean=abs(util.avg(self.preeventdat))
					while(abs(t)<mean):
						t=self.currData.popleft()
						self.eventdat.append(t)
						self.globalDataIndex+=1

					# end of event. Reset the flag
					self.eventstart=False
					
					# Check if there are enough data points to pad the event. If not pop more.
					if len(self.currData) < self.eventPad:
						self.currData.extend(list(self.trajDataObj.popdata(self.nPoints)))

					# Cleanup event pad data before adding it to the event. We look for:
					# 	1. the start of a second event
					#	2. Outliers
					# The threshold for accepting a point is eventThreshold/2.0
					eventpaddat = util.selectS( 
							[ self.currData[i] for i in range(self.eventPad) ],
							self.eventThreshold/2.0,
							self.meanOpenCurr, 
							self.sdOpenCurr
						)
					 
					#print self.trajDataObj.FsHz, self.windowOpenCurrentMean, self.sdOpenCurr, self.slopeOpenCurr
					if len(self.eventdat)>=self.minEventLength:
						self.eventcount+=1
						# print "i=", self.eventcount
						#sys.stderr.write('event mean curr={0:0.2f}, len(preeventdat)={1}\n'.format(sum(self.eventdat)/len(self.eventdat),len(self.preeventdat)))
						#print list(self.preeventdat) + self.eventdat + [ self.currData[i] for i in range(self.eventPad) ]
						#print "ecount=", self.eventcount, self.eventProcHnd
						# print "eventProcSettings", self.eventProcSettingsDict
						self._processEvent(
							 self.eventProcHnd(
								list(self.preeventdat) + self.eventdat + eventpaddat, 
								self.trajDataObj.FsHz,
								eventstart=len(self.preeventdat)+1,						# event start point
								eventend=len(self.preeventdat)+len(self.eventdat)+1,	# event end point
								baselinestats=[ self.meanOpenCurr, self.sdOpenCurr, self.slopeOpenCurr ],
								algosettingsdict=self.eventProcSettingsDict.copy(),
								savets=self.writeEventTS,
								absdatidx=self.dataStart
							)
						)
	
					self.preeventdat.clear()
		except IndexError:
			return

	# def __roundufloat(self, uf):
	# 	u=uncertainties
	# 	return u.ufloat(( round( u.nominal_value(uf), 4), round( u.std_dev(uf), 4) ))
