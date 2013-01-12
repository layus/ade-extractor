#!/usr/bin/python3

import urllib.request as req
import urllib.parse as urlparse
import urllib.urlencode as urlencode
from datetime import date, datetime, timedelta
from collections import defaultdict
from bisect import bisect
import argparse
import sys
import logging
import re
import os
import posixpath
# requires install :
from bs4 import BeautifulSoup

#req.HTTPHandler(debuglevel=1)

### Declare global vars

domain = "http://horaire.sgsi.ucl.ac.be:8080"
url = domain + "/ade/custom/modules/plannings/"


### Create logger object. 

logger = logging.getLogger('ade_extract')
# create console handler (output) 
ch = logging.StreamHandler()
ch.setLevel('DEBUG')
formatter = logging.Formatter('### %(levelname)s : %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


### Helper functions

def select(test, list):
    """Select one elem from list that passes the test function, 
    or None if none matches.""" 
    selected = None
    for item in list:
        if test(item) == True:
           selected = item
           break;
    return selected

def get_project(pid) :
    '''Picks the right ADE project according to the current year.'''

    # Extract canonical project name from current month+year.
    today = date.today()
    year, month = today.year, today.month
    if month <= 7 :
        year = year - 1
    project = str(year) + "-" + str(year+1)

    # Warn user that projects can be selected, 
    # if the default selection does not fit.
    logger.info( "Selected project is "+project )
    logger.info( "Other possible values are :" )
    logger.info( "  Year    : ID" )  
    for key, val in pid.items() :
        logger.info( "{0} : {1}".format(key, val) )
    logger.info( "Please use \"-p <ID>\" to pick another one." )

    # Return corresponding project ID. 
    return pid.get(project)

def extract_date( course ) : 
    """Create a custom (datetime, timedelta) object 
    representing a course schedule"""
    month, day, year = course["Date"].split('/')
    hour, minute = course["Hour"].split('h')
    date = datetime( int(year), int(month), int(day), hour=int(hour), minute=int(minute) )
    hour, minute = course["Duration"].split('h')
    if minute == '' :
        minute = '0'
    else :
        minute = minute.split("min")[0]
    duration = timedelta(hours=int(hour), minutes=int(minute))
    return ( date, duration )

def RepresentsInt(s):
    try: 
        int(s)
        return True
    except ValueError:
        return False

def parse_project( project ) :
    if RepresentsInt( project ) :
        return int( project )
    else :
        pids = get_projects()
        if project in pids :
            return pids[project]
        else :
            raise argparse.ArgumentTypeError('"' + str(project) + '"' + " is not a valid project.")

def normalize( cal ):
    normal = []

    for line in cal :
        newline = [ line[:70] ]
        for i in range(70, len(line), 70) :# 75 is the max, just to be sure...
            newline.append( " "+line[i:i+70])
        normal = normal + newline

    normal = "\r\n".join(normal)
    normal = normal + "\r\n"

    return normal



### Extraction functions
class session_opener():

    def __init__( self, url ):
        self.opener = req.build_opener( req.HTTPCookieProcessor() )
        self.open( url )
    
    def open( url ):
        target_url = follow_js_redir( url )
        return self.opener.open( target_url )

    def follow_js_redir( url ) :
        """ Make requests untill no evident javascript redirection is required """
        while True :
            myreq = self.opener.open(url) 
            html = BeautifulSoup(myreq)
            # search for document.location = <url> in all script tags.
            scripts = "".join( x.text for x in html("script") )
            result = re.search( "document.location *= *'((?:(?:\\.)?[^\\'])*)'", scripts )

            if result == None : 
                break
            
            path = result.group(1)
            url = urlparse.urljoin(myreq.geturl(), path)
            logger.debug( "REDIRECTED : " + url )

        return url

def get_projects() :
    ''' Extract currently active projects from ADE.
    Return a dictionnary mapping names (<YYYY-1>-<YYYY>) to project ID's '''

    url_projects = domain + "/ade/standard/projects.jsp"
    url_login = url + "direct_planning.jsp?login=etudiant&password=student"


    # extract projects
    projects = session_opener().open( url_projects )
    html = BeautifulSoup(projects.read())

    # zip names and ID's together in a map
    return dict( (x.text.strip(), x['value']) for x in  html("option") )

_mem = {} # a var for memoization in get_full_name(...)
class Memoize:
    def __init__(self, f):

class get_course_name():
    def __init__(self):
        self.memo = {}

    def get_course_name(name, ID, opener):

        # use memoization to avoid useless html queries 
        if code in self.memo : return self.memo[code]

        # When not memoized, request ADE eventInfo page
        data = opener.open(url + "eventInfo.jsp?eventId={}&noMenu=true".format(ID))
        html = BeautifulSoup(data)
        full_name = html("label")[0].text.split("Code:")[1]
        logger.debug( "Full name of {} is {}".format( code, full_name) )

        # Allow user to enter another name for the course.
        # That namewill be memoized instead.
        final = input('Enter name for {}\n[{}] : '.format( code, full_name ))
        final = final or full_name

        # Memoize the result
        _mem[code] = final

        # Recurse call now that memoization is active.
        return get_full_name(name, ID, opener)

   

def get_full_name( name, ID, opener) :
    """Convert raw courses codes into human-redable name"""
    # separate code and type description.
    if '-' in name :
        code, extra = tuple(name.split('-'))
        extra = " - CM " + extra
    elif '_' in name :
        code, extra = tuple(name.split('_'))
        extra = " - TP " + extra
    elif '=E' in name :
        code, extra = tuple(name.split('=E'))
        extra = " - EXAMEN " + extra
    else :
        code, extra = name, ""

    return get_course_name(code, ID, opener) + extra

def get_raw_data(codes, pid, weeks, full_names=False) :
    """Extract all events dates from courses codes.
    Use ADE project pid, and restrict to weeks weeks.
    If human-readable names are preffered, use full_names switch."""
    query = ( url + 
        "direct_planning.jsp?" + 
        "weeks={weeks}&code={codes}&login=etudiant&password=student&projectId={pid}" )
    url_query = query.format( weeks = weeks, codes = codes, pid = pid )
    url_query = url_query.replace('&projectId=None', '') # sanitize undefined projects ;)
    logger.debug( "full query : " + url_query )

    url_data = url + "info.jsp?horaire=slot" 
    logger.debug( "data query : " + url_data )

    labels = [ "Date", "Name", "Week", "Day", "Hour", "Duration", 
            "Trainees", "Trainers", "Rooms", "Equipment",
            "Course", "Teams", "Category7", "Category8" ]
    labels_fr = [ "Date", "Nom", "Semaine", "Jour", "Heure", "Durée", 
            "Stagiaires", "Formateurs", "Salles", "Équipements",
            "Cours", "Équipes", "Catégorie7","Catégorie8" ] 

    # Create session cookies and obtain data.
    opener = req.build_opener( req.HTTPCookieProcessor() )
    follow_javascript_redirections(opener, url_query)

    raw_data = BeautifulSoup(opener.open(url_data))
    data = raw_data("tr")[2:]
    logger.debug(data[0])

    # A function to parse html event into a dictionary.
    def conv_ev(ev) : 
        def conv_td(item) : return item.text
        event = dict(zip(labels, map( conv_td, ev)))
        href = ev("td")[1].a["href"]
        event["ID"] = re.search(r'\d+', href).group() 
        if full_names :
            event["FullName"] = get_full_name(event['Name'], event['ID'], opener) 
        else : 
            event["FullName"] = event['Name'] 
        return event

    # Return a list of converted events.
    return list(map( conv_ev, data ))

def ical_datetime( t ) :
    return ("{0.year:0>4}{0.month:0>2}{0.day:0>2}T" +
            "{0.hour:0>2}{0.minute:0>2}{0.second:0>2}Z").format(t)

def get_RRule( courses ) :
    dates = list( map( extract_date, courses) )
    dates.sort()
    
    first = dates[0]
    weeks = (dates[-1][0] - first[0]).days//7 + 1
    
    # Get three lists, one for events matching RRULE,
    # another for the holes in the RRULE,
    # and the last for the remaining exceptions
    ordered = sorted( (first[0]+timedelta(weeks=w), first[1]) for w in range(weeks) )
    exceptions = sorted( list( set(dates) - set(ordered) ))
    holes = sorted( list( set(ordered) - set(dates) ))
    inorder = sorted( list( set(ordered) - set(holes) ))

    # Remove holes afther the last RRULE occurence
    cut = bisect(holes, inorder[-1])
    weeks = weeks - len( holes[cut:] )
    assert weeks >= 0
    holes = holes[:cut]

    # Declare custom vars to shorten event creation afther.
    uid = courses[0]['Name'].replace(' ', '') + "_" + str(hash(frozenset(courses[0].items())))[:4]
    start = dates[0]
    desc = courses[0]
    duration = str(start[1]).split(':')

    hole_dates = ",".join( list(map( lambda x : ical_datetime(x[0]), holes)))   
    if hole_dates != "" :
        hole_dates = "EXDATE;TZID=\"Bruxelles, Copenhague, Madrid, Paris\":" + hole_dates

    ex_dates = ",".join( list(map( lambda x : ical_datetime(x[0]), exceptions)))   
    if ex_dates != "" : 
        ex_dates = "RDATE;VALUE=DATE;TZID=\"Bruxelles, Copenhague, Madrid, Paris\":" + ex_dates

    logger.debug( "\"{}\"({}) :\t{:>2} week(s) with {} hole(s) and {} exception(s).".format(
        desc['FullName'], desc['Name'], weeks, len(holes), len(exceptions) ) )
    

    # build rrule
    event = [
    "BEGIN:VEVENT", 
    "UID:" + uid,
    "SUMMARY:" + desc['FullName'],
    "LOCATION:" + desc['Rooms'],
    "DESCRIPTION:" + "\\n".join( key+" : "+val for key, val in desc.items() ) ,
    "DTSTAMP:" + ical_datetime( datetime.now() ),
    "DTSTART;TZID=\"Bruxelles, Copenhague, Madrid, Paris\":" + ical_datetime( start[0] ),
    "DURATION:PT{0}H{1}M{2}S".format( *duration )]
    if len(dates) > 1 :
        event.append( "RRULE:FREQ=WEEKLY;COUNT=" + str( weeks ) )
    if hole_dates != "" :
        event.append( hole_dates )
    if ex_dates != "" : 
        event.append( ex_dates )
    event.append("END:VEVENT")

    return event


def parse_args() :
    parser = argparse.ArgumentParser(description='Extract generic calendar from ADE.')
    parser.add_argument('courses', type=str, help='list of courses codes to import from ADE (e.g. LFSAB1402)',
                        nargs="+", metavar="<course code>")
    parser.add_argument('-p', '--project', type=parse_project,
                        required=False, default=None, dest='pid',
                        help='an ADE project descriptor, <int> or <year>-<year+1>.')
    parser.add_argument('-n','--full-names', required=False, dest='full_names', 
                        default=False, action='store_true', 
                        help="use course names instead of codes (slower).")
    parser.add_argument('-o', '--outfile', required=False, type=argparse.FileType('w'),
                        default="ade.ics", help="file to write calendar to. Defaults to ade.ics")
    parser.add_argument('-q', '--quadrimestre', type=int, required=False, default=None) 

    args = parser.parse_args()

    # kinda lazy execution ;)
    if args.pid == None :
        args.pid = get_project(get_projects())

    args.courses = ",".join(args.courses)

    return args


if __name__ == "__main__" :

    args = parse_args() 
    logger.debug(args)

    logger.setLevel('DEBUG')

    weeks = ",".join( map( str, range(40)) )
    raw = get_raw_data(args.courses, args.pid, weeks, args.full_names)

    courses = defaultdict(list)
    for l in raw :
        courses[l['FullName']].append( l )

    evs = 0
    cal = '''BEGIN:VCALENDAR
VERSION:2.0" )
PRODID:ADE.PY//1.0
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VTIMEZONE
TZID:Bruxelles\, Copenhague\, Madrid\, Paris
BEGIN:STANDARD
DTSTART:20001029T030000
RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=10
TZNAME:Paris\, Madrid
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:20000326T020000
RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=3
TZNAME:Paris\, Madrid (heure d'été)
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
END:DAYLIGHT
END:VTIMEZONE'''.split("\n")
    for name, cs in courses.items() :
        cal = cal + get_RRule( cs )
        evs = evs + 1
    cal.append( "END:VCALENDAR" )

    cal = normalize( cal )
    
    logger.info( "Writing calendar to " + args.outfile.name + "." )
    args.outfile.write( cal )
    logger.info( str(evs) + " event(s) written." )



