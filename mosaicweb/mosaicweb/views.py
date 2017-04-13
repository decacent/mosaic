from mosaicweb import app
from flask import send_file, make_response, jsonify, request

import mosaic
from mosaic.utilities.sqlQuery import query, rawQuery
from mosaic.utilities.analysis import caprate
from mosaic.utilities.resource_path import resource_path
from mosaic.trajio.metaTrajIO import EmptyDataPipeError, FileNotFoundError
import mosaic.settings as settings

from mosaicweb.mosaicAnalysis import mosaicAnalysis, analysisStatistics, analysisTimeSeries
from mosaicweb.sessionManager import sessionManager
from mosaicweb.utils.utils import gzipped

import pprint
import time
import random
import json
import glob
import os
import logging
import numpy as np

class InvalidPOSTRequest(Exception):
	pass


logger=logging.getLogger()

gAnalysisSessions=sessionManager.sessionManager()
gStartTime=time.time()

@app.route("/")
def index():
    return send_file("templates/index.html")

@app.route('/about', methods=['POST'])
def about():
	return jsonify(ver=mosaic.__version__, build=mosaic.__build__, uiver='1.0.0', uibuild='58cbed0'), 200

@app.route('/validate-settings', methods=['POST'])
def validateSettings():
	try:
		params = dict(request.get_json())

		analysisSettings = params.get('analysisSettings', "")

		jsonSettings = json.loads(analysisSettings)

		return jsonify( respondingURL="validate-settings", status="OK" ), 200
	except ValueError, err:
		return jsonify( respondingURL="validate-settings", errType='ValueError', errSummary="Parse error", errText=str(err) ), 500

@app.route('/processing-algorithm', methods=['POST'])
def processingAlgorithm():
	try:
			defaultSettings=eval(settings.__settings__)
			params = dict(request.get_json())

			procAlgorithmSectionName=params["procAlgorithm"]

			return jsonify(
					respondingURL='processing-algorithm',
					procAlgorithmSectionName=procAlgorithmSectionName,
					procAlgorithm=defaultSettings[procAlgorithmSectionName]
				), 200
	except:
		return jsonify( respondingURL='processing-algorithm', errType='UnknownAlgorithmError', errSummary="Data Processing Algorithm not found.", errText="Data Processing Algorithm not found." ), 500

@app.route('/new-analysis', methods=['POST'])
@gzipped
def newAnalysis():
	global gAnalysisSessions

	try:
		defaultSettings=False
		params = dict(request.get_json())

		dataPath = params.get('dataPath', None)
		settingsString = params.get('settingsString', None)
		sessionID=params.get('sessionID', None)

		if dataPath and not settingsString:		# brand new session
			# print "brand new session: ", dataPath, settingsString, sessionID	
			sessionID=gAnalysisSessions.newSession()
			ma=mosaicAnalysis.mosaicAnalysis( resource_path(mosaic.WebServerDataLocation+'/'+dataPath), sessionID) 

			gAnalysisSessions.addDataPath(sessionID, resource_path(mosaic.WebServerDataLocation+'/'+dataPath) )
			gAnalysisSessions.addMOSAICAnalysisObject(sessionID, ma)
		elif sessionID and settingsString:	# update settings
			# print "update settings: ", dataPath, settingsString, sessionID
			ma=gAnalysisSessions.getSessionAttribute(sessionID, 'mosaicAnalysisObject')
			ma.updateSettings(settingsString)

			gAnalysisSessions.addSettingsString(sessionID, ma.analysisSettingsDict)
		elif sessionID and not settingsString:  # a session ID loaded from a route
			# print "session id from route: ", dataPath, settingsString, sessionID
			ma=gAnalysisSessions.getSessionAttribute(sessionID, 'mosaicAnalysisObject')
		else:
			raise InvalidPOSTRequest('An invalid POST request was received.')
		
		# print params
		# print 
		# print 


		return jsonify(respondingURL='new-analysis', sessionID=sessionID, **ma.setupAnalysis() ), 200
	except EmptyDataPipeError, err:
		return jsonify( respondingURL='new-analysis', errType='EmptyDataPipeError', errSummary="End of data.", errText=str(err) ), 500
	except FileNotFoundError, err:
		return jsonify( respondingURL='new-analysis', errType='FileNotFoundError', errSummary="Files not found.", errText=str(err) ), 500
	except InvalidPOSTRequest, err:
		return jsonify( respondingURL='new-analysis', errType='InvalidPOSTRequest', errSummary="An invalid POST request was received.", errText=str(err) ), 500

@app.route('/start-analysis', methods=['POST'])
def startAnalysis():
	global gAnalysisSessions

	try:
		params = dict(request.get_json())
		sessionID=params['sessionID']
		session=gAnalysisSessions[sessionID]

		try:
			settingsString=params['settingsString'] 
			gAnalysisSessions.addSettingsString(sessionID, settingsString)
		except KeyError:
			pass

		ma=gAnalysisSessions.getSessionAttribute(sessionID, 'mosaicAnalysisObject')
		ma.updateSettings(settingsString)
		ma.runAnalysis()

		gAnalysisSessions.addDatabaseFile(sessionID, ma.dbFile)
		gAnalysisSessions.addAnalysisRunningFlag(sessionID, ma.analysisRunning)
		

		return jsonify( respondingURL="start-analysis", analysisRunning=ma.analysisRunning), 200
	except (sessionManager.SessionNotFoundError, KeyError):
		return jsonify( respondingURL='start-analysis', errType='MissingSIDError', errSummary="A valid session ID was not found.", errText="A valid session ID was not found." ), 500

@app.route('/stop-analysis', methods=['POST'])
def stopAnalysis():
	global gAnalysisSessions

	try:
		params = dict(request.get_json())
		sessionID=params['sessionID']
		session=gAnalysisSessions[sessionID]

		ma=gAnalysisSessions.getSessionAttribute(sessionID, 'mosaicAnalysisObject')
		ma.stopAnalysis()

		gAnalysisSessions.addAnalysisRunningFlag(sessionID, ma.analysisRunning)

		return jsonify( respondingURL="stop-analysis", analysisRunning=ma.analysisRunning, newDataAvailable=True ), 200
	except (sessionManager.SessionNotFoundError, KeyError):
		return jsonify( respondingURL='stop-analysis', errType='MissingSIDError', errSummary="A valid session ID was not found.", errText="A valid session ID was not found." ), 500

@app.route('/analysis-results', methods=['POST'])
@gzipped
def analysisResults():
	global gAnalysisSessions

	try:
		params = dict(request.get_json())
		sessionID=params['sessionID']
		qstr=params['query']
		bins=params['nBins']
		dbfile=gAnalysisSessions.getSessionAttribute(sessionID, 'databaseFile')

		ma=gAnalysisSessions.getSessionAttribute(sessionID, 'mosaicAnalysisObject')
		gAnalysisSessions.addAnalysisRunningFlag(sessionID, ma.analysisRunning)

		return jsonify( respondingURL="analysis-results", analysisRunning=ma.analysisRunning, **_histPlot(dbfile, qstr, bins) ), 200
	except sessionManager.SessionNotFoundError:
		return jsonify( respondingURL='analysis-results', errType='MissingSIDError', errSummary="A valid session ID was not found.", errText="A valid session ID was not found." ), 500
	except KeyError, err:
		return jsonify( respondingURL='analysis-results', errType='KeyError', errSummary="The key {0} was not found.".format(str(err)), errText="The key {0} was not found.".format(str(err)) ), 500


@app.route('/analysis-statistics', methods=['POST'])
def analysisStats():
	global gAnalysisSessions

	try:
		params = dict(request.get_json())
		
		sessionID=params['sessionID']
		dbfile=gAnalysisSessions.getSessionAttribute(sessionID, 'databaseFile')

		a=analysisStatistics.analysisStatistics(dbfile)

		return jsonify(respondingURL='analysis-statistics', **a.analysisStatistics()), 200
	except (sessionManager.SessionNotFoundError, KeyError):
		return jsonify( respondingURL='analysis-statistics', errType='MissingSIDError', errSummary="A valid session ID was not found.", errText="A valid session ID was not found." ), 500

@app.route('/analysis-log', methods=['POST'])
def analysisLog():
	global gAnalysisSessions

	try:
		params = dict(request.get_json())
		
		sessionID=params['sessionID']
		dbfile=gAnalysisSessions.getSessionAttribute(sessionID, 'databaseFile')

		logstr=(rawQuery(dbfile, "select logstring from analysislog")[0][0]).replace(str(mosaic.WebServerDataLocation), "<Data Root>")

		return jsonify(respondingURL='analysis-log', logText=logstr), 200
	except (sessionManager.SessionNotFoundError, KeyError):
		return jsonify( respondingURL='analysis-statistics', errType='MissingSIDError', errSummary="A valid session ID was not found.", errText="A valid session ID was not found." ), 500

@app.route('/event-view', methods=['POST'])
# @gzipped
def eventView():
	global gAnalysisSessions

	try:
		params = dict(request.get_json())

		sessionID=params['sessionID']
		eventNumber=params['eventNumber']
		dbfile=gAnalysisSessions.getSessionAttribute(sessionID, 'databaseFile')

		a=analysisTimeSeries.analysisTimeSeries(dbfile, eventNumber)

		return jsonify(respondingURL='event-view', **a.timeSeries()), 200
	except (sessionManager.SessionNotFoundError, KeyError), err:
		print err
		return jsonify( respondingURL='event-view', errType='MissingSIDError', errSummary="A valid session ID was not found.", errText="A valid session ID was not found." ), 500


@app.route('/poll-analysis-status', methods=['POST'])
def pollAnalysisStatus():
	global gStartTime

	if (time.time()-gStartTime)%10 < 5.0:
		return jsonify( respondingURL="poll-analysis-status", newDataAvailable=True ), 200
	else:
		return jsonify( respondingURL="poll-analysis-status", newDataAvailable=False ), 200

@app.route('/list-data-folders', methods=['POST'])
def listDataFolders():
	params = dict(request.get_json())

	level=params.get('level', 'Data Root')
	if level == 'Data Root':
		folder=mosaic.WebServerDataLocation
	else:
		folder=resource_path(mosaic.WebServerDataLocation+'/'+level+'/')

	folderList=[]

	for item in sorted(glob.glob(folder+'/*')):
		itemAttr={}
		if os.path.isdir(item):
			itemAttr['name']=os.path.relpath(item, folder)
			itemAttr['relpath']=os.path.relpath(item, resource_path(mosaic.WebServerDataLocation) )
			itemAttr['desc']=_folderDesc(item)
			itemAttr['modified']=time.strftime('%Y-%m-%d', time.localtime(os.path.getmtime(item)))

			folderList.append(itemAttr)

	return jsonify( respondingURL='list-data-folders', level=level+'/', dataFolders=folderList )

def _folderDesc(item):
	nqdf = len(glob.glob(item+'/*.qdf'))
	nbin = len(glob.glob(item+'/*.bin'))+len(glob.glob(item+'/*.dat'))
	nabf = len(glob.glob(item+'/*.abf'))
	nfolders = len( [i for i in os.listdir(item) if os.path.isdir(item+'/'+i) ] )

	if nqdf > 0:
		return "{0} QDF files".format(nqdf)
	elif nbin > 0:
		return "{0} BIN files".format(nbin)
	elif nabf > 0:
		return "{0} ABF files".format(nabf)
	elif nfolders==0:
		return "No data files."
	else:
		return "{0} sub-folders".format(nfolders) 

def _histPlot(dbFile, qstr, bins):
	xlabel={
		"BlockDepth"	: "i/i<sub>0</sub>",
		"ResTime"		: "t (ms)"
	}[qstr.split('from')[0].split('select')[1].split()[0]]

	q=query(
		dbFile,
		qstr
	)
	x=np.hstack( np.hstack( np.array( q ) ) )
	c,b=np.array(np.histogram(x, bins=bins))

	dat={}

	trace1={};
	trace1['x']=list(b)
	trace1['y']=list(c)
	trace1['mode']='lines'
	trace1['line']= { 'color': 'rgb(40, 53, 147)', 'width': '1.5' }
	trace1['name']= 'blockade depth'

	layout={}
	# layout['title']='Blockade Depth Histogram'
	layout['xaxis']= { 'title': xlabel, 'type': 'linear' }
	layout['yaxis']= { 'title': 'counts', 'type': 'linear' }
	layout['paper_bgcolor']='rgba(0,0,0,0)'
	layout['plot_bgcolor']='rgba(0,0,0,0)'
	layout['margin']={'l':'50', 'r':'50', 't':'0', 'b':'50'}
	layout['showlegend']=False
	layout['autosize']=True
	# layout['height']=250

	# normalEvents, totalEvents=_eventStats()
	# stats={}
	# stats['eventsProcessed']=totalEvents
	# stats['errorRate']=round(100.*(1-(normalEvents/float(totalEvents))), 1)
	# stats['captureRate']=_caprate()

	dat['data']=[trace1]
	dat['layout']=layout
	dat['options']={'displayLogo': False}
	# dat['stats']=stats

	return dat


# def _eventStats():
# 	normalEvents=len(query(
# 		mosaic.WebServerDataLocation+"/m40_0916_RbClPEG/eventMD-20161208-130302.sqlite",
# 		"select AbsEventStart from metadata where ProcessingStatus='normal' order by AbsEventStart ASC"
# 	))
# 	totalEvents=len(query(
# 		mosaic.WebServerDataLocation+"/m40_0916_RbClPEG/eventMD-20161208-130302.sqlite",
# 		"select ProcessingStatus from metadata"
# 	))

# 	return normalEvents, totalEvents
	