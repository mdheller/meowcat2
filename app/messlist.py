# messlist.py = lists of messages

from typing import *
import abc

from feedgen.feed import FeedGenerator
from flask import request, redirect, Response

import bozen
from bozen.butil import pr, prn, dpr, form, htmlEsc
from bozen import Paginator
from bozen import (MonDoc, FormDoc,
    StrField, TextAreaField, PasswordField,
    ChoiceField, FK, FKeys, MultiChoiceField,
    DateField, DateTimeField,
    IntField, FloatField, BoolField)

import models


MESS_SHOW = 10 # default messages to show
MESS_SHOW_ONE = 100 # default messages to show when one-line
   
#---------------------------------------------------------------------
 
class FormattingOptionsForm(FormDoc):
    oneLine = BoolField(desc="show one line summary",
        widget='toggleSwitch', showTitle = False,
        offText = "Show Message", onText = "1-Line Summary")
    
    headOnly = BoolField(desc="show head posts only",
        widget='toggleSwitch', showTitle = False,
        default = True,
        offText = "All Posts", onText = "Head Posts")
    
    mrf = BoolField(desc="most recent posts first",
        widget='toggleSwitch', showTitle = False,
        default = True,
        offText = "Oldest First", onText = "Most Recent First")
    
    au = BoolField(desc="Auto Update",       
        widget='toggleSwitch', showTitle = False,
        offText = "Static", onText = "Auto Update")
    
    def setFromUrl(self):
        """ Set the values of the fields in the form to that
        from the GET parameters in the URL """
        x = request.args.get('x', "")
        if not x:
            # no form fields, don't change anything
            return
        
        self.oneLine = bool(request.args.get('oneLine', False))
        self.headOnly = bool(request.args.get('headOnly', False))
        self.mrf = bool(request.args.get('mrf', False))
        self.au = bool(request.args.get('au', False))
 
 
#---------------------------------------------------------------------

# something that can be a FormatingOptionsForm or None   
OptFOF = Union[FormattingOptionsForm,None] 
   
class ListFormatter:
    """ formats a list of messages """


    def __init__(self):
        self.q = {}
        self.fof = FormattingOptionsForm()
        self.fof.setFromUrl()
        self.pag = None
 
    def getQuery(self, fof:OptFOF=None) -> dict:
        """ Return the query to use for the MongoDB find() call, 
        including the start query (self.q) and the formatting options
        (in fof or self.fof)
        """
        if fof:
            useFof = fof
        else:
            useFof = self.fof
        q2 = {}
        q2.update(self.q)      
        if useFof.headOnly:
            # only select head posts
            q2.update({'replyTo_id': {'$in': [None, '']}})      
        #dpr("q2=%r", q2)    
        return q2    
        
    def setUpPagination(self):
        """ set up the pagination system """
        # if we are using auto-update, don't paginate
        self.doPagination = not self.fof.au
            
        if self.fof.oneLine:
            self.numShow = MESS_SHOW_ONE
        else:
            self.numShow = MESS_SHOW 
        if not self.doPagination: return
        self.count = models.Message.count(self.getQuery(self.fof))
        self.pag = Paginator(self.count, perPage=self.numShow)
        
    def paginationBefore(self) -> str: 
        """ Return pagination html that goes before the list of messages.  
        """
        if not self.pag: self.setUpPagination()
        if not self.doPagination: return ""
        if self.pag.skip<=0: return ""
        h = form("<p>Displaying messages {fromIx}-{toIx} of {total}.</p>",
            fromIx = self.pag.fromIx,
            toIx = self.pag.toIx,
            total = self.pag.total)
        return h
        
    def paginationAfter(self) -> str:    
        """ Return pagination html that goes after the list of messages.  
        """
        if not self.pag: self.setUpPagination()
        if not self.doPagination: return ""
        h = form("""<br>
<p>Displaying messages {fromIx}-{toIx} of {total}.</p>
<div class='right-pagination'>{links}</div>""",
            fromIx = self.pag.fromIx,
            toIx = self.pag.toIx,
            total = self.pag.total,
            links = self.pag.links)
        return h
    

    def getMessages(self, fof:OptFOF=None) -> Iterable[models.Message]:
        """ return an iterator for the list of messages to be got from
        MongoDB. The formatting options are either those in (fof) or
        if None there, those in (self.fof).
        """
        if not self.pag: self.setUpPagination()
        if fof:
            useFof = fof
        else:
            useFof = self.fof
            
        if useFof.mrf: 
            sortValue = ('published', -1)  
        else:
            sortValue = ('published', 1) 
            
        if self.doPagination:    
            ms = models.Message.find(self.getQuery(fof), 
                sort=sortValue,
                skip=self.pag.skip,
                limit=self.numShow)
        else:      
            ms = models.Message.find(self.getQuery(fof), 
                sort=sortValue,
                limit=self.numShow)
        return ms
        
    def includeAuthorOneLine(self) -> bool:
        """ Should we include the author when printing a one-line
        summary of a message? This is true except for a blog (because
        then all the messages are from trhe same author).
        """
        return True
        
    def getMessagesH(self) -> str:
        """ Return HTML for the list of messages """
        h = ""
        if self.fof.oneLine:
            includeAuthor = self.includeAuthorOneLine()
            h = "".join(m.viewOneLine(showAuthor=includeAuthor) 
                        for m in self.getMessages())
        else:    
            for m in self.getMessages():
                h += m.viewH() + "<p></p>"
            #//for
        return h


    #========== methods to be implemented by subclass
    
    @abc.abstractmethod
    def pageUrl(self) -> str:
        """ Return the url of the page, e.g. "/blog/cabalamat"
        or "/messList"
        """
        
    @abc.abstractmethod
    def getFeedGenerator(self) -> FeedGenerator:
        """ return a feed generator for an RSS feed for this class
        """

    #========== auto-update
        
    def jsForPage(self) -> str:
        """ return appropiate JavaScript for the page 
        """
        js = """
/* created by ListFormatter.jsForPage() */
function foChanged(){
    $("#formatingOptionForm").submit();
}    
$("#id_oneLine").change(foChanged);
$("#id_headOnly").change(foChanged);
$("#id_mrf").change(foChanged);
$("#id_au").change(foChanged);       
        
"""    
        js += self.autoUpdateJS()
        return js
    
    def autoUpdateJS(self) -> str:
        """ return some JavaScript for handling automatic updates. These
        occur when these is a message more recent that the more recent
        timestamp. Timestamps are in the format e.g. '2011-12-31T23:55:20'
        and can therefore be sorted by ascii collating sequence.
        """
        autoUpdate = self.fof.au and self.fof.mrf
        if not autoUpdate: return ""
    
        js = form("""\
var updatePollUrl = "{url}";
var mostRecentTimeStamp = "{timeStamp}";
pollForAutoUpdate(updatePollUrl, mostRecentTimeStamp);
""",
            url = "/au" + request.full_path,
            timeStamp = self.mostRecentTimeStamp())
        return js

    def mostRecentTimeStamp(self) -> str:
        """ Return the timestamp of thev most recent message,
        Take into account the (fof.headOnly) option,
        """
        m = models.Message.find_one(self.getQuery(),
             sort=('published', -1))
        if m:
            ts = m.published
        else:
            ts = "2000-01-01T00:00:00"
        return ts   
    
    #========== RSS methods
    
    def renderRss(self) -> str:
        """ Return RSS for this feed """
        fg = self.getFeedGenerator()
        
        for m in self.getMessages(FormattingOptionsForm()):
            fe = fg.add_entry()
            fe.id(m.fullUrl())
            fe.title(m.title)
            fe.content(m.html)
        #//for  
        
        return fg.rss_str(pretty=True) 


#---------------------------------------------------------------------


#end
