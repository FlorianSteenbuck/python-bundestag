# -*- coding: utf-8 -*-
import requests
from requests.compat import unquote, quote
from md5 import md5
import re
import json
from re import sub as rereplace
from re import split as resplit
from lxml.etree import _Element
from lxml.html import fromstring
from datetime import datetime

def stringify_children(node):
    from lxml.etree import tostring
    from itertools import chain
    parts = ([node.text] +
            list(chain(*([c.text, tostring(c), c.tail] for c in node.getchildren()))) +
            [node.tail])
    # filter removes possible Nones in texts and tails
    return ''.join(filter(None, parts))

def escape(_str):
    return quote(unicode(_str).encode('utf8'))

def unescape(_str):
    return unicode(unquote(_str)).encode('utf8')

SAVE_FUNC_END = 0
SAVE_FUNC_START = 1
SAVE_POINTS = [SAVE_FUNC_END, SAVE_FUNC_START]

TO_SAVE = []

HISTORY_FILE_PREFIX = "history"
HISTORY_FILE_MIME = ".json"
HISTORY_DATE = "%Y-%m-%d_%H:%M:%S-%f"
URL_HISTORY = {}
USE_LAST_HISTORY = True

VOTE_YES = "yes"
VOTE_NO = "no"
VOTE_OUTSTANDING = "outstanding"
NO_VOTE = "no_vote"

def get(url, **kwargs):
    save_history = False
    if "save_history" in kwargs.keys() and type(kwargs["save_history"]) == bool:
        save_history = kwargs["save_history"]

    if USE_LAST_HISTORY:
        if url in URL_HISTORY.keys():
            last_date = None
            last_resp = {}

            for date in URL_HISTORY[url].keys():
                date_obj = datetime.strptime(date, HISTORY_DATE) 
                if last_date == None or date_obj > last_date:
                    last_date = date_obj
                    last_resp = URL_HISTORY[url][date]
            
            return last_resp

    date = datetime.now().strftime(HISTORY_DATE)    
    resp = requests.get(url, **kwargs)
    if not url in URL_HISTORY.keys():
        URL_HISTORY[url] = {}

    URL_HISTORY[url][date] = {
        "headers":resp.headers,
        "content":resp.content 
    }

    if save_history:
        fh = open(HISTORY_FILE_PREFIX+"_"+date+HISTORY_FILE_MIME, "w+")
        fh.write(json.dumps(URL_HISTORY))
        fh.close()

    return {
        "headers":resp.headers,
        "content":resp.content 
    }

def sp_get(url, **kwargs):
    save_history = False
    if "save_point" in kwargs.keys() and kwargs["save_point"] in SAVE_POINTS:
        save_history = kwargs["save_point"] in TO_SAVE
    kwargs["save_history"] = save_history

    return get(url,**kwargs)

OPTIONS = {
    "limit": 10,
    "noFilterSet": True
}
VOTING_YEAR = 2017
ROOT = "https://www.bundestag.de"
PATH = "abstimmung"
DATALOADER_URLS = []

def config(py, dataloader_urls=None, now=None, voting_year=VOTING_YEAR, root=ROOT, path=PATH, options=OPTIONS):
    if type(dataloader_urls) == list:
        DATALOADER_URLS = dataloader_url
    else:
        DATALOADER_URLS = get_dataloader_urls(root+"/"+path)
    if now != None:
        VOTING_YEAR = last_voting_year(now)
    else:
        VOTING_YEAR = voting_year
    OPTIONS = options

    global OPTIONS
    global VOTING_YEAR
    global ROOT
    global PATH
    global DATALOADER_URLS

def get_dataloader_urls(url):
    dataloader_urls = []
    doc = fromstring(get(url)["content"])
    for slider in doc.cssselect("*[data-dataloader-url]"):
        if "data-limit" in slider.attrib.keys() and slider.attrib["data-limit"] < OPTIONS["limit"]:
            OPTIONS["limit"] = slider.attrib["data-limit"]
        dataloader_urls.append(slider.attrib["data-dataloader-url"])
    return dataloader_urls

voting_place_metas = None
def load_voting_place_metas():
    global voting_place_metas
    if not voting_place_metas == None:
        return voting_place_metas

    
def append_all(src, dest):
    for item in src:
        dest.append(item)
    return dest

def compare(a, b):
    return a == b

def append_set(src, dest, deep=False, soft_compare=compare):
    for item in src:
        is_in = False
        for dest_item in dest:
            if soft_compare(dest_item, item):
                is_in = True
                break 
            if deep and type(item) == dict and type(item) == type(dest_item):
                item = merge(src, dest)
        if is_in:
            continue
        dest.append(item)
    return dest

def merge(source, destination, soft_compare=compare):
    if type(source) == dict:
        for key in source.keys():
            value = source[key]
            if type(source) == dict or type(source) == list:
                node = destination.setdefault(key, {})
                merge(value, node, soft_compare=soft_compare)
            else:
                destination[key] = value
    elif type(source) == list:
        return append_set(source, destination, deep=True, soft_compare=soft_compare)
    return destination

def compare_id(a, b):
    return type(a) == dict and type(b) == dict and "id" in b.keys() and "id" in a.keys() and a["id"] == b["id"]

def merge_id(src, dest):
    return merge(src, dest, soft_compare=compare_id)

def js_str(value):
    if value == True:
        return "true"
    elif value == False:
        return "false"
    elif value == None:
        return "null"
    return str(value)

def href_resolve(root, path, href):
    protocol_split = resplit("(\\:\\/\\/|\\:)", href, maxsplit=1)
    if len(protocol_split) > 1:
        return href
    if href.startswith("/"):
        return root+href
    return root+"/"+path+"/"+href

def get_hash(options):
    raw = ""
    opkeys = options.keys()
    opkeys.sort()
    for key in opkeys:
        value = options[key]
        raw += key + js_str(value)
    return "h_"+md5(rereplace("/[^a-zA-Z0-9]*/g", "", raw)).hexdigest()

def get_voter_id(href):
    _id = ""
    join = False
    for part in href.split("/"):
        part = resplit("(\\?|\\#)", part)[0]
        if not join:
            if part == "biografien":
                join = True
            continue
        _id += part+"/"
    return _id[:len(_id)-1]

def get_images(root, path, el):
    images = {}
    for img in el.cssselect(".img-responsive"):
        for img_key in img.attrib.keys():
            if not img_key.startswith("data-img-"):
                continue
            images[img_key[9:]] = href_resolve(root, path, img.attrib[img_key])
    return images

def get_voting_place_id(el):
    links = el.cssselect("a[href]")
    if not len(links) > 0:
        return None
    href = [0].attrib["href"]
    querys = href.split("?")
    if not len(querys) > 0:
        return None
    query = querys[len(querys)-1].split("#")[0]
    for entry in query.split("&"):
        key_value_split = entry.split("=",1)
        if not len(key_value_split) > 0:
            continue
        key = unescape(key_value_split[0])
        value = unescape(key_value_split[1])
        if key == "wknr":
            return value
    return None

ALL_CHANGE_VOTINGS = [1969,1972,1983,2005]
VOTING_YEAR_MIN = 1949
VOTING_YEAR_MAX = -1
VOTING_ROTA = 4
VOTING_UNIT = "year"

def voting_unit(now):
    return getattr(now, VOTING_UNIT)

def last_voting_unit(now):
    last = ALL_CHANGE_VOTINGS[0]
    for may_last in ALL_CHANGE_VOTINGS:
        if voting_unit(now) >= may_last:
            last = may_last
    if voting_unit(now) < last:
        while voting_unit(now) < last:
            last-=VOTING_ROTA
        return last
    if voting_unit(now) > last:
        while voting_unit(now) >= last:
            last+=VOTING_ROTA
        return last-VOTING_ROTA
    return last

def get_voting_place(_id, el, voter_id):
    if VOTING_YEAR != 2017:
        raise Error("Their is no voting place datasource for the year"+VOTING_YEAR)
    a = "https://www.bundestag.de/static/appdata/includes/datasources/wahlkreisergebnisse/btwahl"+VOTING_YEAR+"/wahlkreise.json"
    return {}

def get_voter(_id, gender, el):
    root = "https://www.bundestag.de"
    path = "abgeordnete/biografien/"+_id

    print path

    voter = {
        "gender":gender
    }
    images = get_images(root, path, el)
    contacts = {}
    
    voting_places = {}
    places = {}
    party = {}

    parties = el.cssselect(".bt-person-fraktion")
    if len(parties) > 0:
        party["id"] = parties[0].text_content().strip()

    doc = fromstring(get(root+"/"+path)["content"])
    profiles = doc.cssselect(".bt-profil")
    if len(profiles) > 0:
        profile = profiles[0]
        jobs = []
        
        for potrait in profile.cssselect(".bt-profil-potrait"):
            images = merge_id(get_images(root, path, potrait), images)

        for job in profile.cssselect(".bt-biografie-name .bt-biografie-beruf p"):
            jobs.append(job.text_content())
        
        for contact in profile.cssselect(".bt-kontakt-collapse .row div"):
            keys = contact.cssselect("h5")
            if not len(keys) > 0:
                continue
            key = keys[0]
            links = {}
            blocks = []

            for block in contact.cssselect("p"):
                link_els = block.cssselect("a[href]")
                for link in link_els:
                    links[href_resolve(root,path,link.attrib["href"])] = link.text_content()
                
                if len(link_els) > 0:
                    continue

                blocks.append(block.text_content())

            for link in contact.cssselect(".bt-linkliste a[href]"):
                links[href_resolve(root,path,link.attrib["href"])] = link.text_content()

            contacts[key] = {
                "links":links,
                "blocks":blocks
            }

        mandats = []
        for landlist in profile.cssselect("#bt-landesliste-collapse"):
            mandat_headlines = landlist.getprev().cssselect("h4")
            if not len(mandat_headlines) > 0:
                continue

            mandat_headline = mandat_headlines[0].text_content().strip()
            mandat_type = mandat_headline
            if mandat_headline == "Gewählt über Landesliste":
                mandat_type = "landlist"
            elif mandat_headline == "Direkt gewählt":
                mandat_type = "direct"

            for voting_place_el in landlist.cssselect(".bt-wk-map"):
                vp_id = get_voting_place_id(voting_place_el)
                get_voting_place(vp_id, voting_place_el, _id)
            
            for name in landlist.cssselect("h5"):
                places[name.text_content().strip()] = [_id]

    voter["images"] = images

    return voter, party, {}, {}

def get_results(doc, _id):
    places = {}
    voting_places = {}
    parties = {}
    voters = {}
    results = {}
    
    genders = []
    for gender_el in doc.cssselect("select[name=geschlecht] option[value]"):
        genders.append(gender_el.attrib["value"])
    for gender in genders:
        gender_url = "https://www.bundestag.de/apps/na/na/namensliste.form?id="+escape(str(_id))+"&ajax=true&letter=&fraktion=&bundesland=&plz=&geschlecht="+escape(gender)+"&alter="
        print gender_url
        doc = fromstring(get(gender_url)["content"])
        for person in doc.cssselect("a[href] .bt-teaser-person"):
            voter = person.getparent()
            while not (isinstance(voter, _Element) and voter.tag == "a"):
                voter = person.getparent()
            voter_id = get_voter_id(voter.attrib["href"])
            
            voter_result =
            voter_results = voter.cssselect(".bt-person-abstimmung")
            if len(voter_results)
            
            voter, party, place, voting_place = get_voter(voter_id, gender, voter)
            party_id = "without party"
            if "id" in party:
                party_id = party["id"]
            place_id = "without place"
            if "id" in place:
                place_id = place["id"]
            voting_place_id = "without voting place"
            if "id" in voting_place:
                voting_place_id = voting_place["id"]
            
            if not party_id in parties.keys(): 
                parties[party_id] = []
            if not voting_place_id in voting_places.keys(): 
                voting_places[voting_place_id] = []
            if not place_id in places.keys(): 
                places[place_id] = []

            voters[voter_id] = voter

    return results, places, voting_places, parties, voters

def get_debates(doc):
    return {}

def inner_text(el):
    text = el.text
    for child in el.iterchildren():
        if not isinstance(child, _Element):
            continue
        text += child.tostring()
    return text

HEADS = ["h1","h2","h3","h4","h5","h6"]
BUNDES_DATUM_REGEX = "/^([0-9]|[0-9][0-9])\\.((\\ )+|)([äÄa-zA-Z]+)((\\ )+|)([0-9][0-9][0-9][0-9])$/"
BUNDES_DATUM = re.compile(BUNDES_DATUM_REGEX)
def get_articles(doc):
    articles = []
    desc_article = doc.cssselect("#bt-namentliche-abstimmungen .bt-module-content article")[0]
    for headline in desc_article.cssselect(",".join(HEADS)):
        headline_text = headline.text_content()
        article_text = ""
        tags = []
        changes = []
        
        for headlineSibling in headline.cssselect(".bt-dachzeile"):
            tag_text = headlineSibling.text_content().strip("\n ")
            print BUNDES_DATUM_REGEX
            print tag_text
            if BUNDES_DATUM.match(tag_text):
                changes.append(tag_text)
                continue
            headline_text = headline_text.replace(tag_text,"", 1)
            tags.append(tag_text)
        
        headline_text = headline_text.strip("\n ")

        nextToHeadline = headline.getnext()
        firstNextToHeadline = nextToHeadline
        while nextToHeadline != None and ((not isinstance(nextToHeadline, _Element)) or (not nextToHeadline.tag in HEADS)):
            if not isinstance(nextToHeadline, _Element):
                continue
            if nextToHeadline.tag == "br":
                article_text += "\n"
                continue
            article_text += nextToHeadline.text_content()
            nextToHeadline = headline.getnext()
            if nextToHeadline == firstNextToHeadline:
                break

        articles.append({
            "headline":headline_text,
            "text":article_text,
            "tags":tags,
            "changes":changes
        })
    print articles
    return articles

def get_voting_id(href):
    querys = href.split("?")
    params = querys[len(querys)-1].split("&")
    for param in params:
        key, value = param.split("=", 1)
        key = unescape(key)
        value = unescape(value)
        if key == "id":
            return value
    return None 

def get_voting(el):
    return get_voting_by_id(get_voting_id(el.attrib["href"]))

def get_voting_by_id(_id):
    voting = {}
    places = {}
    voting_places = {}
    parties = {}
    voters = {}


    voting_url = "https://www.bundestag.de/parlament/plenum/abstimmung/abstimmung?id="+str(_id)
    print voting_url
    doc = fromstring(get(voting_url)["content"])
    
    voting["articles"] = get_articles(doc)
    voting["debates"] = get_debates(doc)

    results, n_places, n_voting_places, n_parties, n_voters = get_results(doc, _id)

    places = merge_id(places, n_places)
    voting_places = merge_id(voting_places, n_voting_places)
    parties = merge_id(parties, n_parties)
    voters = merge_id(voters, n_voters)
    
    voting["results"] = results
    
    return voting, voters, parties, places, voting_places

def get_votings(dataloader_url, options):
    votings = []
    places = {}
    voting_places = {}
    voters = {}
    parties = {}
    url = dataloader_url+"/"+get_hash(options)+"?"
    opkeys = options.keys()
    opkeys.sort()
    for key in opkeys:
        value = options[key]
        url += escape(key) + "=" + escape(js_str(value))+"&"
    url = href_resolve("https://www.bundestag.de","/",url[:len(url)-1])
    doc = fromstring(get(url)["content"])
    for voting_el in doc.cssselect("a[href]"):
        voting, n_voters, n_parties, n_places, n_voting_places = get_voting(voting_el)  
        votings.append(voting)

        places = merge_id(places, n_places)
        voting_places = merge_id(voting_places, n_voting_places)
        parties = merge_id(parties, n_parties)
        voters = merge_id(voters, n_voters)
    return votings, voters, parties, places, voting_places

def get_all_votings(dataloader_url, options, chunk_count=None):
    votings = []
    places = {}
    voting_places = {}
    voters = {}
    parties = {}
    n_votings, n_voters, n_parties, n_places, n_voting_places = get_votings(dataloader_url, options)
    votings = append_all(n_votings, votings)
    
    places = merge_id(places, n_places)
    voting_places = merge_id(voting_places, n_voting_places)
    parties = merge_id(parties, n_parties)
    voters = merge_id(voters, n_voters)
    
    options["offset"] = options["limit"]
    i = 0
    while (len(n_votings) > 0 and chunk_count == None) or (chunk_count != None and i < chunk_count):
        n_votings, n_voters, n_parties, n_places, n_voting_places = get_votings(dataloader_url, options)
        votings = append_all(n_votings, votings)

        places = merge_id(places, n_places)
        voting_places = merge_id(voting_places, n_voting_places)
        parties = merge_id(parties, n_parties)
        voters = merge_id(voters, n_voters)
        
        options["offset"] += options["limit"]
        i+=1
    return votings, voters

config(1)

fh = open("result.json", "w+")
fh.write(json.dumps(get_votings(DATALOADER_URLS[0], OPTIONS)))
fh.close()