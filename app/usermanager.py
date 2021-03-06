# -*- coding: utf-8 -*-	
import sys, json, pylast, os
from datetime import datetime
from secrets import *
from functions import *
from pymongo import MongoClient

reload(sys)
sys.setdefaultencoding("utf-8")
date_format = "%d %b %Y %X"

#returns true if user already exists in the database
def checkExistingUser(userid, version):
	user = getDatabase().users.find_one({"userid": userid, "version": version})
	#if a broken user exists, remove it and insert the new one
	if (user != None):
		if(user['status'] != 'working'):
			getDatabase().removedUsers.insert(user)
			getDatabase().users.remove({'userid': userid, 'version': version}, 'true')
			return False
		else:
			return True
	else:
		return False
		
#checks to see if the user exists on the server
def checkUserValidity(userid, version):
	if version < 22:
		testCookies(['ps'])
	else:
		testCookies(['pw'])
	if(scrapeData(userid, version) == 'ERROR'):
		return False
	return True

#checks to see if the LFM users exists
def validateLFMUser(username):
	network = pylast.LastFMNetwork(api_key = os.environ.get('LFM_APIKEY'), api_secret = os.environ.get('LFM_SECRET'))
	try:
		testuser = network.get_user(username)
		testuser.get_friends()
	except pylast.WSError:
		return False
	else:
		return True

#mark user for later deletion if calls to their PS/PW/last.fm profile don't work
def markUser(user, reason):
	# with open('errorlog.txt', 'a') as errorlog:
	# 	errorlog.write("\nMarked user %s for deletion. Reason: %s" % (user['userid'], reason))
	print 'marking user %s with reason %s' % (user['userid'], reason)
	getDatabase().users.update(
		{'userid': user['userid'], 'version': user['version']},
		{
			'$set':{
					'status': reason
			}
		})
	# if ('LASTFM' in reason):
	# 	shoutUser(user['lfm_username'])
	# else:
	# 	print 'not a lastfm error'


#adds user to database
def createUser(userid, version, lfm_user):
	network = {'21': 'ps', '0': 'ps', '22': 'pw'}
	getDatabase().users.insert(
		{
			"userid": userid,
			"version": version,
			"network": network[version],
			"lfm_username": lfm_user,
			"lastchecked": datetime.now().strftime(date_format),
			"status": "initializeme"
		})

#updates user's 'lastchecked' element, mostly copied from deleteUser
def updateLastChecked(userid, version):
	getDatabase().users.update(
		{'userid': userid, 'version': version},
		{
			'$set':{
					'lastchecked': datetime.now().strftime(date_format)
			}
		})

#initialize MongoClient object and return database
def getDatabase():
	client = MongoClient(os.environ.get('MONGODB_URL'))
	return client.userlist

#initialize last.fm session key for user
def lfmInit(user):
	#initialize lfm objects
	url = user['lfm_url']
	network = pylast.get_lastfm_network(os.environ.get('LFM_APIKEY'), os.environ.get('LFM_SECRET'))
	sg = pylast.SessionKeyGenerator(network)
	sg.web_auth_tokens[url] = url[(url.index('token')+6):]
	sg.api_key = os.environ.get('LFM_APIKEY')
	sg.api_secret = os.environ.get('LFM_SECRET')
	#try to authorize token
	try:
		session_key = sg.get_web_auth_session_key(user['lfm_url'])
		print session_key
	except pylast.WSError:
		print "Error authorizing user for last.fm"
		markUser(user, 'LASTFM INIT ERROR')
	#success, add new session key and remove auth token
	else:
		getDatabase().users.update(
		{'userid': user['userid'], 'version': user['version']},
		{
			'$set':{
				'lfm_session': session_key,
				'status': 'working'
			},
			'$unset':{
				'lfm_url': True
			}
		})

#send LFM user an automated message in case their account fails
def shoutUser(username):
	network = pylast.LastFMNetwork(api_key = os.environ.get('LFM_APIKEY'), api_secret = os.environ.get('LFM_SECRET'), session_key = getMySessionKey())
	try:
		brokenuser = network.get_user(username)
		brokenuser.shout("Hey! This is an automated message from iidx.fm. It looks like there was a problem authenticating your account - please feel free to try and register again. If this was expected, go ahead and delete this message.")
	except pylast.WSError:
		print "Error shouting to user %s" % username

#return my own session key to be used when shouting
def getMySessionKey():
	myuser = getDatabase().users.find_one({'lfm_username': 'benhgreen'})
	return myuser['lfm_session']