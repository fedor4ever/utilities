#!/usr/bin/python
# Copyright (c) 2009 Symbian Foundation.
# All rights reserved.
# This component and the accompanying materials are made available
# under the terms of the License "Eclipse Public License v1.0"
# which accompanies this distribution, and is available
# at the URL "http://www.eclipse.org/legal/epl-v10.html".
#
# Initial Contributors:
# Symbian Foundation - Initial contribution
# 
# Description:
# Script to download and unpack a Symbian PDK - assumes "7z" installed to unzip the files

import socket
import urllib2
import urllib
import os.path
import cookielib
import sys
import getpass
import re
import time
from BeautifulSoup import BeautifulSoup
from optparse import OptionParser
import hashlib
import xml.etree.ElementTree as ET 

version = '0.15'
user_agent = 'downloadkit.py script v' + version
headers = { 'User-Agent' : user_agent }
top_level_url = "https://developer.symbian.org"
passman = urllib2.HTTPPasswordMgrWithDefaultRealm()	# not relevant for live Symbian website
download_list = []
unzip_list = []

def build_opener(debug=False):
	# Create a HTTP and HTTPS handler with the appropriate debug
	# level.  We intentionally create a new one because the
	# OpenerDirector class in urllib2 is smart enough to replace
	# its internal versions with ours if we pass them into the
	# urllib2.build_opener method.  This is much easier than trying
	# to introspect into the OpenerDirector to find the existing
	# handlers.
	http_handler = urllib2.HTTPHandler(debuglevel=debug)
	https_handler = urllib2.HTTPSHandler(debuglevel=debug)
	
	# We want to process cookies, but only in memory so just use
	# a basic memory-only cookie jar instance
	cookie_jar = cookielib.LWPCookieJar()
	cookie_handler = urllib2.HTTPCookieProcessor(cookie_jar)
	
	# add HTTP authentication password handler (only relevant for Symbian staging server)
	authhandler = urllib2.HTTPBasicAuthHandler(passman)
	
	handlers = [authhandler, http_handler, https_handler, cookie_handler]
	opener = urllib2.build_opener(*handlers)
	
	# Save the cookie jar with the opener just in case it's needed
	# later on
	opener.cookie_jar = cookie_jar

	return opener

urlopen = urllib2.urlopen
Request = urllib2.Request

def quick_networking_check():
	global options
	defaulttimeout = socket.getdefaulttimeout()
	socket.setdefaulttimeout(15)
	probesite = top_level_url
	probeurl = probesite + '/main/user_profile/login.php'
	headers = { 'User-Agent' : user_agent }

	req = urllib2.Request(probeurl, None, headers)

	try:
		response = urllib2.urlopen(req)
		doc=response.read()
	except urllib2.URLError, e:
		if hasattr(e, 'code') and e.code == 401:#
			# Needs HTTP basic authentication
			print >> sys.stderr, 'HTTP username: ',
			http_username=sys.stdin.readline().strip()
			http_password=getpass.getpass('HTTP password: ')
			passman.add_password(None, top_level_url, http_username, http_password)
			# now try again...

	try:
		response = urllib2.urlopen(req)
		doc=response.read()
	except urllib2.URLError, e:
		print '*** Problem accessing ' + probesite
		if hasattr(e, 'reason'):
			print '*** Reason: ', e.reason
		elif hasattr(e, 'code'):
			print '*** Error code: ', e.code
		print "Do you need to use a proxy server to access the %s website?" % probesite
		sys.exit(1)
	socket.setdefaulttimeout(defaulttimeout)	# restore the default timeout
	if options.progress:
		print "Confirmed that we can access " + probesite

def login(prompt):
	global options
	loginurl =  top_level_url + '/main/user_profile/login.php'
	
	if prompt:
		if options.username == '':
			print >> sys.stderr, 'username: ',
			options.username=sys.stdin.readline().strip()
		if options.password == '':
			options.password=getpass.getpass()
	
	values = {'username' : options.username,
	          'password' : options.password,
	          'submit': 'Login'}
	          
	headers = { 'User-Agent' : user_agent }
	
	
	data = urllib.urlencode(values)
	req = urllib2.Request(loginurl, data, headers)

	response = urllib2.urlopen(req)
	doc=response.read()      

	if doc.find('Please try again') != -1:
		print >> sys.stderr, 'Login failed'
		return False
	return True

from threading import Thread

class unzipfile(Thread):
	def __init__ (self,filename,levels=1,deletelevels=0):
		Thread.__init__(self)
		self.filename = filename
		self.levels = levels
		self.deletelevels = deletelevels
		self.status = -1
		
	def unzip(self,filename,unziplevel,deletelevel):
		if unziplevel < 1:
			return 0   # do nothing

		print "  Unzipping " + filename
		filelist = os.popen("7z x -y "+self.filename)
		subzips = []
		for line in filelist.readlines():
			# Extracting  src_oss_app_webuis.zip
			match = re.match(r"^Extracting\s+(\S+.zip)$", line)
			if match is None: continue
			subzips.append(match.group(1))
		topstatus = filelist.close()

		if deletelevel > 0:
			print "  Deleting " + filename
			os.remove(filename)
		if unziplevel > 1 and len(subzips) > 0:
			print "  Expanding %d zip files from %s" % (len(subzips), filename)
			for subzip in subzips:
				self.unzip(subzip, unziplevel-1, deletelevel-1)
		return topstatus
	def run(self):
		self.status = self.unzip(self.filename, self.levels, self.deletelevels)

threadlist = []
def schedule_unzip(filename, unziplevel, deletelevel):
	global options
	if options.nounzip :
		return
	if options.nodelete :
		deletelevel = 0
	if options.dryrun :
		global unzip_list
		if unziplevel > 0:
			unzip_list.append("7z x -y %s" % filename)
			if unziplevel > 1:
				unzip_list.append("# unzip recursively %d more times" % unziplevel-1)
		if deletelevel > 0:
			unzip_list.append("# delete %s" % filename)
			if deletelevel > 1:
				unzip_list.append("# delete zip files recursively %d more times" % deletelevel-1)
		return
		
	unzipthread = unzipfile(filename, unziplevel, deletelevel)
	global threadlist
	threadlist.append(unzipthread)
	unzipthread.start()

def complete_outstanding_unzips():
	global options
	if options.dryrun or options.nounzip:
		return
	print "Waiting for outstanding commands to finish..."
	for thread in threadlist:
		thread.join()  

def check_unzip_environment():
	global options
	if options.nounzip:
		return True		# if we aren't unzipping, no need to have 7z installed
	help = os.popen("7z -h")
	for line in help.readlines():
		if re.match('7-Zip', line) :
			help.close()
			return True
	help.close()
	return False

def orderResults(x,y) :
	def ranking(name) :
		# 0th = release_metadata
		if re.match(r"release_metadata", name):
			return 0000;
		# 1st = release_metadata, build_BOM.zip (both small things!)
		if re.match(r"build_BOM", name):
			return 1000;
		# 2nd = tools, binaries (required for execution and compilation)
		elif re.match(r"(binaries_|tools_)", name):
			return 2000;
		# 3rd = rnd binaries, binary patches
		elif re.match(r"(bin_)", name):
			return 3000;
		# 4th = sources
		elif re.match(r"(src_sfl|src_oss)", name):
			return 4000;
		# 5rd = rnd sources, source patches (not sure we'd ever have those)
		elif re.match(r"(src_)", name):
			return 5000;
		# Last, anything else
		return 10000;
	xtitle = x['title']
	ytitle = y['title']
	return cmp(ranking(xtitle)+cmp(xtitle,ytitle), ranking(ytitle))

def md5_checksum(filename):
	MD5_BLOCK_SIZE = 128 * 1024
	md5 = hashlib.md5()
	try:
		file = open(filename,"rb")
	except IOError:
		print "Terminating script: Unable to open %S" % filename
		sys.exit()
	while True:
		data = file.read(MD5_BLOCK_SIZE)
		if not data:
			break
		md5.update(data)
	file.close()
	return md5.hexdigest().upper()

checksums = {}
def parse_release_metadata(filename):
	if os.path.exists(filename):
		tree = ET.parse(filename)
		iter = tree.getiterator('package')
		for element in iter:
			if element.keys():
				file = element.get("name")
				md5 = element.get("md5checksum")
				checksums[file] = md5.upper()

def download_file(filename,url):
	global options
	global checksums
	if os.path.exists(filename):
		if filename in checksums:
			print 'Checking existing ' + filename
			file_checksum = md5_checksum(filename)
			if file_checksum == checksums[filename]:
				if options.progress:
					print '- OK ' + filename
				return True

	if options.dryrun and not re.match(r"release_metadata", filename):
		global download_list
		download_info = "download %s %s" % (filename, url)
		download_list.append(download_info)
		return True

	print 'Downloading ' + filename
	global headers
	req = urllib2.Request(url, None, headers)
	
	CHUNK = 128 * 1024
	size = 0
	filesize = -1
	start_time = time.time()
	last_time = start_time
	last_size = size
	try:
		response = urllib2.urlopen(req)
		chunk = response.read(CHUNK)
		if chunk.find('<div id="sign_in_box">') != -1:
			# our urllib2 cookies have gone awol - login again
			login(False)
			req = urllib2.Request(url, None, headers)
			response = urllib2.urlopen(req)
			chunk = response.read(CHUNK)
			if chunk.find('<div id="sign_in_box">') != -1:
				# still broken - give up on this one
				print "*** ERROR trying to download %s" % (filename)
				return False
		info = response.info()
		if 'Content-Length' in info:
			filesize = int(info['Content-Length'])
		else:
			match = re.search('>([^>]+Licen[^<]+)<', chunk, re.IGNORECASE)
			if match:
				license = match.group(1).replace('&amp;','&')
				print "*** %s is subject to the %s which you have not yet accepted\n" % (filename,license)
				return False
			print "*** HTTP response did not contain 'Content-Length' when expected"
			if options.debug:
				print info
				print chunk
			return False

	except urllib2.URLError, e:
		print '- ERROR: Failed to start downloading ' + filename
		if hasattr(e, 'reason'):
			print 'Reason: ', e.reason
		elif hasattr(e, 'code'):
			print 'Error code: ', e.code
		return False

	# we are now up and running, and chunk contains the start of the download
	
	try:
		fp = open(filename, 'wb')
		md5 = hashlib.md5()
		while True:
			fp.write(chunk)
			md5.update(chunk)
			size += len(chunk)
			now = time.time()
			if options.progress and now-last_time > 20:
				rate = (size-last_size)/(now-last_time)
				estimate = ""
				if filesize > 0 and rate > 0:
					remaining_seconds = (filesize-size)/rate
					if remaining_seconds > 110:
						remaining = "%d minutes" % (remaining_seconds/60)
					else:
						remaining = "%d seconds" % remaining_seconds
					estimate = "- %d%% est. %s" % ((100*size/filesize), remaining)
				print "- %d Kb (%d Kb/s) %s" % (size/1024, (rate/1024)+0.5, estimate)
				last_time = now
				last_size = size
			chunk = response.read(CHUNK)
			if not chunk: break

		fp.close()
		if options.progress:
			now = time.time()
			print "- Completed %s - %d Kb in %d seconds" % (filename, (filesize/1024)+0.5, now-start_time)

	#handle errors
	except urllib2.URLError, e:
		print '- ERROR: Failed while downloading ' + filename
		if hasattr(e, 'reason'):
			print 'Reason: ', e.reason
		elif hasattr(e, 'code'):
			print 'Error code: ', e.code
		return False

	if filename in checksums:
		download_checksum = md5.hexdigest().upper()
		if download_checksum != checksums[filename]:
			print '- WARNING: %s checksum does not match' % filename

	return True

def downloadkit(version):	
	global headers
	global options
	urlbase = top_level_url + '/main/tools_and_kits/downloads/'

	viewid = 5   # default to Symbian^3
	if version[0] == 2:
		viewid= 1  # Symbian^2
	if version[0] == 3:
		viewid= 5  # Symbian^3
	url = urlbase + ('view.php?id=%d'% viewid) + 'vId=' + version

	req = urllib2.Request(url, None, headers)
	response = urllib2.urlopen(req)
	doc=response.read()
	
	# BeatifulSoup chokes on some javascript, so we cut away everything before the <body>
	try:
		bodystart=doc.find('<body>')
		doc = doc[bodystart:]
	except:
		pass

	if options.debug:
		f = open("downloadpage.html","w")
		print >>f, doc 
		f.close()

	soup=BeautifulSoup(doc)

	# check that this is the right version
	match = re.search('Platform Release (\(Public\) )?v(\d\.\d\.[0-9a-z]+)', doc, re.IGNORECASE)
	if match and match.group(2) != version:
		print "*** ERROR: version %s is not available" % version
		print "*** the website is offering version %s instead" % match.group(1)
		return 0
		
	# let's hope the HTML format never changes...
	# <a href='download.php?id=27&cid=60&iid=270' title='src_oss_mw.zip'> ...</a> 
	threadlist = []
	results=soup.findAll('a', href=re.compile("^download"), title=re.compile("\.(zip|xml)$"))
	results.sort(orderResults)
	for result in results:
		downloadurl = urlbase + result['href']
		filename = result['title']

		if options.nosrc and re.match(r"(src_sfl|src_oss)", filename) :
			continue 	# no snapshots of Mercurial source thanks...
		if options.nowinscw and re.search(r"winscw", filename) :
			continue 	# no winscw emulator...
		if options.noarmv5 and re.search(r"armv5", filename) :
			continue 	# no armv5 emulator...
		if options.noarmv5 and options.nowinscw and re.search(r"binaries_epoc.zip|binaries_epoc_sdk", filename) :
			continue 	# skip binaries_epoc and binaries_sdk ...
		if download_file(filename, downloadurl) != True :
			continue # download failed

		# unzip the file (if desired)
		if re.match(r"patch", filename):
			complete_outstanding_unzips()	# ensure that the thing we are patching is completed first
			
		if re.match(r"release_metadata", filename):
			parse_release_metadata(filename)	# read the md5 checksums etc
		elif re.match(r"(bin|tools).*\.zip", filename):
			schedule_unzip(filename, 1, 0)   # unzip once, don't delete
		elif re.match(r"src_.*\.zip", filename):
			schedule_unzip(filename, 1, 1)   # zip of zips, delete top level
		elif re.match(r"build_BOM.zip", filename):
			schedule_unzip(filename, 1, 1)   # unpack then delete zip as it's not needed again

	# wait for the unzipping threads to complete
	complete_outstanding_unzips()  

	return 1

parser = OptionParser(version="%prog "+version, usage="Usage: %prog [options] version")
parser.add_option("-n", "--dryrun", action="store_true", dest="dryrun",
	help="print the files to be downloaded, the 7z commands, and the recommended deletions")
parser.add_option("--nosrc", action="store_true", dest="nosrc",
	help="Don't download any of the source code available directly from Mercurial")
parser.add_option("--nowinscw", action="store_true", dest="nowinscw",
	help="Don't download the winscw emulator")
parser.add_option("--noarmv5", action="store_true", dest="noarmv5",
	help="Don't download the armv5 binaries")
parser.add_option("--nounzip", action="store_true", dest="nounzip",
	help="Just download, don't unzip or delete any files")
parser.add_option("--nodelete", action="store_true", dest="nodelete",
	help="Do not delete files after unzipping")
parser.add_option("--progress", action="store_true", dest="progress",
	help="Report download progress")
parser.add_option("-u", "--username", dest="username", metavar="USER",
	help="login to website as USER")
parser.add_option("-p", "--password", dest="password", metavar="PWD",
	help="specify the account password")
parser.add_option("--debug", action="store_true", dest="debug", 
	help="debug HTML traffic (not recommended!)")
parser.add_option("--webhost", dest="webhost", metavar="SITE",
	help="use alternative website (for testing!)")
parser.set_defaults(
	dryrun=False, 
	nosrc=False, 
	nowinscw=False, 
	noarmv5=False, 
	nounzip=False, 
	nodelete=False, 
	progress=False,
	username='',
	password='',
	webhost = 'developer.symbian.org',
	debug=False
	)

(options, args) = parser.parse_args()
if len(args) != 1:
	parser.error("Must supply a PDK version, e.g. 3.0.f")
if not check_unzip_environment() :
	parser.error("Unable to execute 7z command")

top_level_url = "https://" + options.webhost
opener = build_opener(options.debug)
urllib2.install_opener(opener)

quick_networking_check()
login(True)
downloadkit(args[0])

if options.dryrun:
	print "# instructions for downloading kit " + args[0]
	for download in download_list:
		print download
	for command in unzip_list:
		print command

