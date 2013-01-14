#!/usr/bin/python3

import urllib.request as req
import urllib.parse as urlparse
from urllib.parse import urlencode
from datetime import date, datetime, timedelta
from collections import defaultdict
from bisect import bisect
import argparse
import sys
import logging
import re
import os
import posixpath
import itertools
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
def follow_javascript_redirections( opener, url ) :
    """ Make requests untill no evident javascript redirection is required """
    while True :
        myreq = opener.open(url) 
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

    # open session 
    opener = req.build_opener( req.HTTPCookieProcessor() )
    opener.open(url_login)

    # extract projects
    projects = opener.open( url_projects )
    html = BeautifulSoup(projects.read())

    # zip names and ID's together in a dict
    return dict( (x.text.strip(), x['value']) for x in  html("option") )

_memo = {} # a var for memoization in get_course_name(...)
def get_course_name(code, ID, opener):

    # use memoization to avoid useless html queries 
    if code in _memo : return _memo[code]

    # When not memoized, request ADE eventInfo page
    data = opener.open(url + "eventInfo.jsp?eventId=%s&noMenu=true" % ID )
    html = BeautifulSoup(data)
    full_name = html("label")[0].text.split("Code:")[1].strip()
    logger.debug( "Full name of %s is %s" % (code, full_name) )

    # Allow user to enter another name for the course.
    # That namewill be memoized instead.
    final = input('Enter name for %s\n[%s] : ' % (code, full_name) ) or full_name

    # Memoize the result
    _memo[code] = final
    return final

def get_full_name( name, ID, opener) :
    """Convert raw courses codes into human-redable name"""
    # separate code and type description.
    if '-' in name :
        code, extra = tuple(name.split('-'))
        extra = " - CM " + extra
    elif '_' in name :
        code, extra = tuple(name.split('_'))
        extra = " - TP " + extra
    elif '=' in name :
        code, extra = tuple(name.split('='))
        if extra == 'E' : extra = 'EXAM'
        extra = " - " + extra
    else :
        code, extra = name, ""

    return get_course_name(code, ID, opener) + extra


# A function to parse html event into a dictionary.
def parse_html_event(ev, opener, full_names=False) : 
    labels = [ "Date", "Name", "Week", "Day", "Hour", "Duration", 
               "Trainees", "Trainers", "Rooms", "Equipment",
               "Course", "Teams", "Category7", "Category8" ]

    event = [ item.text.strip() for item in ev ]
    event = dict( zip(labels,event) )
    
    if full_names :
        href = ev("td")[1].a["href"]
        event["ID"] = re.search(r'\d+', href).group()
        event["FullName"] = get_full_name(event['Name'], event['ID'], opener)
    else :
        event["FullName"] = event['Name'] 
    
    return event

def get_raw_data(codes, pid, weeks, full_names=False) :
    """Extract all events dates from courses codes.
    Use ADE project pid, and restrict to weeks weeks.
    If human-readable names are preffered, use full_names switch."""

    params = {"weeks":weeks, "code":','.join(codes), "login":"etudiant", "password":"student"}
    if pid != None : params["projectId"] = pid

    url_query = ( url + "direct_planning.jsp?" + urlencode(params) )
    url_data = url + "info.jsp?horaire=slot" 
    
    # Create session cookies and obtain data.
    opener = req.build_opener( req.HTTPCookieProcessor() )
    follow_javascript_redirections(opener, url_query)

    raw_data = BeautifulSoup(opener.open(url_data))
    data = raw_data("tr")[2:] # table contains two unusable headers
    if (len(data) > 0 ) :
        logger.debug(data[0])

    # Return a list of converted events.
    return [ parse_html_event( ev, opener, full_names ) for ev in data ]

def ical_datetime( t ) :
    return ("{0.year:0>4}{0.month:0>2}{0.day:0>2}T" +
            "{0.hour:0>2}{0.minute:0>2}{0.second:0>2}").format(t)

def partition(pred, iterable):
    'Use a predicate to partition entries into false entries and true entries'
    # partition(is_odd, range(10)) --> 0 2 4 6 8   and  1 3 5 7 9
    t1, t2 = itertools.tee(iterable)
    return ( filter(pred, t1), itertools.filterfalse(pred, t2) )

def get_RRule( courses ) :
    """ Split courses according to duration """
    # This is needed as RDATE;VALUE=PERIOD;... is not supported by most online calendars.
    if not courses : return []

    ok, others = partition( lambda x: (x["Duration"] == courses[0]["Duration"] ) , courses )
    ok, others = list(ok), list(others)
     
    if others : 
        logger.warning( "Event %s must be split because it contains different durations" % courses[0]["FullName"] )

    return build_RRule( ok ) + get_RRule( others )

def build_RRule( courses ):
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

    # Remove holes after the last RRULE occurence (not really holes then :)
    cut = bisect(holes, inorder[-1])
    weeks = weeks - len( holes[cut:] )
    assert weeks >= 0
    holes = holes[:cut]

    # Declare custom vars to shorten event creation step.
    uid = (courses[0]['Name'].replace(' ', '') + "_" + 
            str(hash(frozenset(courses[0].items())))[:6] )
    start = dates[0]
    desc = courses[0]
    duration = str(start[1]).split(':')

    hole_dates = ",".join( ical_datetime(e[0]) for e in holes )
    if len(holes) > 0 :
        hole_dates = "EXDATE;TZID=\"Bruxelles, Copenhague, Madrid, Paris\":" + hole_dates

    ex_dates = ",".join( ical_datetime(e[0]) for e in exceptions )   
    if len(exceptions) > 0 : 
        ex_dates = 'RDATE;VALUE=DATE;TZID="Bruxelles, Copenhague, Madrid, Paris":' + ex_dates

    logger.debug( '"{}"({}) :\t{:>2} week(s) with {} hole(s) and {} exception(s).'.format(
        desc['FullName'], desc['Name'], weeks, len(holes), len(exceptions) ) )
    

    # build Vevent
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
    if len(holes) > 0 :
        event.append( hole_dates )
    if len(exceptions) > 0 : 
        event.append( ex_dates )
    event.append("END:VEVENT")

    return event


def parse_project( project ) :
    if project.isdigit():
        return project
    else :
        pids = get_projects()
        if project in pids :
            return pids[project]
        else :
            raise argparse.ArgumentTypeError('"' + project + '" is not a valid project.')

def parse_args() :
    parser = argparse.ArgumentParser(description='Extract generic calendar from ADE.')
    parser.add_argument('courses', type=str, nargs="+", metavar="<course code>",
                        help='list of courses codes to import from ADE (e.g. LFSAB1402)')
    parser.add_argument('-p', '--project', type=parse_project,
                        required=False, default=None, dest='pid',
                        help='an ADE project descriptor, <int> or <year>-<year+1>')
    parser.add_argument('-n','--full-names', required=False, dest='full_names', 
                        default=False, action='store_true', 
                        help="use course names instead of codes (slower)")
    parser.add_argument('-o', '--outfile', required=False, type=argparse.FileType('w'),
                        default='ade.ics', help="output file (defaults to 'ade.ics')")
    parser.add_argument('--debug', action='store_true', default=False, required=False,
                        help='enable debugging information')
    parser.add_argument('-q', metavar="quarter", type=int, required=False, 
                        default=0, choices=[-3, -2, -1, 0, 1, 2, 3],
                        help=" ".join(["extract only dates in this quarter",
                        "(any of 1, 2, 3; use -i to exclude i,",
                        "so -3 is equivalent to 1 and 2; defaults to 0 == whole year)"]) )

    args = parser.parse_args()

    # kinda lazy execution ;)
    if args.pid == None :
        args.pid = get_project(get_projects())

    # barbaric, but efficient ;)
    args.courses = ",".join(args.courses).split(',') 

    # TODO : Handle -q argument
    # wekks ranges from 0 (first academic week (a priori ;) )
    # to 51, last week before next year.
    # splitting quadrimesters is hard if some week gets inserted...
    # a priori : 0 -> (14 (cours) + 2 (blocus) + 2 (exams) + 1 (vacances) )
    # la semaine de vacances étant utilisée au cas où il y aurait un shift une année.
    # Q2 = (fin Q1 - 1 pour être sûr) + 14 (cours)+ 2 (vacances) + ? bloc + exams)
    # Q3 = tt le reste, uniquement utile pour les examens.
    #
    # par défault, on met 0-51
    args.weeks = ",".join( map( str, range(52) ) )

    return args

header = '''BEGIN:VCALENDAR
VERSION:2.0
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
END:VTIMEZONE'''

def make_cal(courses, pid, weeks, full_names=False) :
    raw = get_raw_data(courses, pid, weeks, full_names)

    found = dict( (c,0) for c in courses )
    courses = defaultdict(list)
    for l in raw :
        courses[l['FullName']].append( l )
        found[l["Course"]] = found[l["Course"]] + 1

    for course, count in found.items():
        if count == 0:
            logger.warning("No event scheduled for " + course)

    events = 0
    cal = header.split("\n")
    for name, cs in courses.items() :
        cal = cal + get_RRule( cs )
        events = events + 1
    cal.append( "END:VCALENDAR" )

    return (normalize( cal ), events)


if __name__ == "__main__" :

    args = parse_args() 

    if args.debug : logger.setLevel('DEBUG')
    else : logger.setLevel('INFO')
    logger.debug(args)

    cal, events = make_cal(args.courses, args.pid, args.weeks, args.full_names)
    
    if (events == 0):
        logger.error("No event found. Did you misspel some course code ?")
        sys.exit(-1)
    
    logger.info( "Writing calendar to " + args.outfile.name + "." )
    args.outfile.write( cal )
    logger.info( str(events) + " event(s) written." )
    


