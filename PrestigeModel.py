#!/usr/bin/python -u
# Copyright John Bryden under GPL3 license 
#
# However, don't publish any results generated using this code, or the
# underlying model, without my permission

from pylab import *
from graph_tool.all import *
from collections import namedtuple
import sys
import argparse
import random
import pickle

# We need some Gtk and gobject functions
from gi.repository import Gtk, Gdk, GdkPixbuf, GObject

cm =get_cmap('inferno')
def getColour (amount,maxAmount,font=False):
    val = amount/maxAmount;
    if val>1:
        val = 1;

    color = cm.colors[int(255*val)]

    # If asking for the colour for the font, work out the perceived
    # luminosity of the colour and then choose white or black
    # according to how dark or light it is
    if font:
        a = ( 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]);
        if a>0.5:
            color = (0,0,0)
        else:
            color = (1,1,1)
        
    return color
    
# this is a unidirectional link between two people
class Link:

    def __init__(self, outPerson, inPerson, linkValueToOut, linkValueToIn):
        self.outPerson = outPerson
        self.inPerson = inPerson
        self.linkValueToOut = linkValueToOut
        self.linkValueToIn = linkValueToIn
    
    def output(self):
        print (self.outPerson.personid,"->",self.inPerson.personid,)
        print ("Outval =",self.linkValueToOut,"Inval =",self.linkValueToIn)

# a person (or node) in the network
class Person:
    
    def __init__ (self,personid):

        # this the id of the person
        self.personid = personid

        # the person has a list of its Links to other people
        self.outgoingLinks=list()
        # they also have a dictionary (id -> link) of Links from others
        self.incomingLinks=dict()

        # this is the initial status of the person
        self.status=1.0
        # this is to record the status which is incoming from others
        self.incomingStatus = 0

    def show (self):
        print ("I am person",self.personid)
        print ("I have status",self.status)
        print ("Incoming status is",self.incomingStatus)
        for link in self.outgoingLinks:
            print ("->",link.inPerson.personid)
        print (self.numIncomingLinks,"incoming links")
        print ()

    def getNumLinks(self):
        return len(self.incomingLinks)+len(self.outgoingLinks)
        
    def updateStatus(self):
        status += statusChange
        statusChange = 0

    # This function calculates the outgoing link which is of least
    # value to the individual
    def getWorstLink(self, addIncomingValueIfLinkIsMutual=False):
        worstlink = None
        worstValue= 1e500
        for link in self.outgoingLinks:
            linkvalue = link.linkValueToOut
            if addIncomingValueIfLinkIsMutual:
                if link.inPerson.personid in self.incomingLinks:
                    linkvalue += self.incomingLinks[link.inPerson.personid].linkValueToIn
            if linkvalue < worstValue:
                worstValue = link.linkValueToOut
                worstlink = link

        return worstlink
    
    def output(self):
        print ("Person",self.personid)
        print ("outgoing")
        for link in self.outgoingLinks:
            link.output();

        print ("incoming")
        for link in self.incomingLinks.values():
            link.output();



class Population:
    # Manages a dictionary (id->person) of people and a list of links
    # between them
    

    def __init__(self, numPeople,numLinks,r=0.2,q=0.9,w=1.0,graph=None,maxStatus=-1):

        self.numPeople = numPeople
        self.numLinks  = numLinks
        self.q = q
        self.r = r
        self.w = w
        self.includeMutualLinks=False
        self.noMutualLinks=True
        self.recordLinksVersusStatus = False

        self.graph=graph
        if maxStatus == -1:
            maxStatus = numPeople
        self.maxStatus = maxStatus
        
        self.people = dict()
        self.links = list()

        # to record some data which will later be plotted
        self.numlinksvsstatus=list()

        for i in range (0,self.numPeople):
            self.people[i] = Person(i)

        self.idset = set(self.people.keys())


        # generate a random network
        for pid,person in self.people.items():
            avoidPeople=[person.personid,]
            if self.noMutualLinks:
                for inpersonid in person.incomingLinks.keys():
                    avoidPeople.append(inpersonid)

#            print (avoidPeople)
            if len(avoidPeople) >= self.numPeople:
                raise ("Noone to link to, perhaps too many links for the population?")
            for j in range (0,self.numLinks):
                linkedPerson=self.findIndividualToLinkTo(avoidPeople)
                avoidPeople.append(linkedPerson.personid)
                newlink = Link(outPerson = person, inPerson = linkedPerson, linkValueToOut = 0.1, linkValueToIn = 0.1)
                self.links.append (newlink)
                person.outgoingLinks.append(newlink)
                linkedPerson.incomingLinks[person.personid]=newlink


    # functions for getting random individuals
    def getRandomPerson (self):
        return self.people[random.randint(self.numPeople)]

    def findIndividualToLinkTo (self, avoidPeopleIDs):
        peopleleft = self.idset-set(avoidPeopleIDs)
        newPersonID = random.sample(peopleleft,1)
#        print (avoidPeopleIDs)
#        print (peopleleft)
#        print (newPersonID)
        return self.people[newPersonID[0]]
        

    def showPeople(self):
        for pid,person in self.people.items():
            person.show()

    def updateStatuses(self):
        # reset link values
        for link in self.links:
            link.linkValueToIn = 0.0
            link.linkValueToOut = 0.0
        
        
        for link in self.links:
            outPerson = link.outPerson
            inPerson = link.inPerson

            # Each person takes a proportion r of their status (which
            # will be deducted later) and divides that amongst their
            # links.
            outStatusForLink = self.r*outPerson.status/float(outPerson.getNumLinks())
            inStatusForLInk = self.r*inPerson.status/float(inPerson.getNumLinks())
         
            # The status attributed to each link is divided unevenly
            # between the pair - with a proportion q going to the
            # person who's getting their link
            linkValue = outStatusForLink+inStatusForLInk
            link.linkValueToIn = linkValue*self.q
            link.linkValueToOut = linkValue*(1.0-self.q)

            outPerson.incomingStatus += link.linkValueToOut
            inPerson.incomingStatus += link.linkValueToIn

        for pid,person in self.people.items():
            person.status += person.incomingStatus-self.r*person.status
            person.incomingStatus = 0

        if self.graph:
            for pid,person in self.people.items():
                g.vp.vertex_fill_colors[pid] = getColour(person.status,self.maxStatus)
            for pid,person in self.people.items():
                v = float(person.status)/float(self.maxStatus)
                if v>1:
                    v = 1.0
                g.vp.vertex_size[pid] = 20.0+v*25.0
            for pid,person in self.people.items():
                g.vp.vertex_text_color[pid] = getColour(person.status,self.maxStatus,font=True)
            
    def outputLinksVersusStatus (self):
        # I want to generate a heat map of status / num links
        if self.recordLinksVersusStatus:
            for pid,person in self.people.items():
                numlinks = person.getNumLinks()
                status = person.status
                self.numlinksvsstatus.append((numlinks,status))

#            self.numlinksvsstatus_output.write(str(numlinks)+' '+str(status)+'\n')
    
    def getStatuses (self):
        statuses = []
        for pid,person in self.people.items():
            statuses.append(person.status)
        return statuses

    def rewireLinks (self):

        for pid,person in self.people.items():

            # reWire with random probability w
            if self.w == 1.0 or random.random() < self.w:
            
                #            print ("Person",person.personid,"rewiring from",)

                worstLink = person.getWorstLink(self.includeMutualLinks)
                personBeingRemoved = worstLink.inPerson
                #            print (personBeingRemoved.personid)

                #           personBeingRemoved.output()


                # In this version, it won't rewire to any of those
                # already linked to (including the person being
                # removed)
                avoidPeople = [person.personid,]
                for link in person.outgoingLinks:
                    avoidPeople.append(link.inPerson.personid)

                if self.noMutualLinks:
                    for inpersonid in person.incomingLinks.keys():
                        avoidPeople.append(inpersonid)
                #            print (pid,avoidPeople)
            
                if len(avoidPeople) < self.numPeople:
                    # Remove this link from the old person's links
                    personBeingRemoved.incomingLinks.pop(pid)

                    newPerson = self.findIndividualToLinkTo(avoidPeople)

                    #update the link and give it to the new person
                    worstLink.inPerson = newPerson
                    if self.graph:
                        self.graph.remove_edge(worstLink.gt_edge)
                        worstLink.gt_edge = g.add_edge(worstLink.outPerson.personid, newPerson.personid)
                
                    newPerson.incomingLinks[person.personid]=worstLink

                    # this checks if there is a bug where an invidual has
                    # too many incoming linsk
                    if len(newPerson.incomingLinks) == self.numPeople:
                        print (person.personid)
                        print (avoidPeople)
                        print (newPerson.personid)
                        print (personBeingRemoved.personid)
                        print (worstLink.outPerson.personid, worstLink.inPerson.personid)
                        #               print ("to",newPerson.personid)

    # for debugging purposes
    def findAnomalousIndividual (self):
        for pid,person in self.people.items():
            if person.getNumLinks() > (self.numLinks+self.numPeople-1):
                print ("Person: ",person.personid)
                for link in self.links:
                    if link.outPerson == person or link.inPerson == person:
                        print (link.outPerson.personid,"->",link.inPerson.personid)

    def outputNetwork (self):
        print ("Network")
        for pid,person in self.people.items():
            person.output()
        print ()
        

    def makeGraph (self):
        self.graph.add_vertex (self.numPeople)

        link_penwidths = self.graph.new_edge_property('double')
        maxLinkStatus = 0.0
        for link in self.links:
            maxLinkStatus=max(maxLinkStatus,link.linkValueToIn + link.linkValueToOut)
            
        for link in self.links:
            e = self.graph.add_edge (link.outPerson.personid,link.inPerson.personid)
            link_penwidths[e] = 1.0*maxLinkStatus/(link.linkValueToIn + link.linkValueToOut)
            link.gt_edge = e


#        for link in self.links:
#            print (link.outPerson.personid,link.inPerson.personid,link.linkValueToIn + link.linkValueToOut)
            
        self.graph.ep.edge_pen_widths = link_penwidths
        maxStatus = 0
        for pid,person in population.people.items():
            maxStatus = max(person.status,maxStatus)

        cm =get_cmap('plasma')
        vcols = self.graph.new_vertex_property('vector<double>')
        for i in range (0,self.numPeople):
            vcols[i] = getColour(population.people[i].status,maxStatus)
        self.graph.vp.vertex_fill_colors = vcols

        vtext = self.graph.new_vertex_property('string')
        for i in range (0,self.numPeople):
            vtext[i] = str(i)
        self.graph.vp.vertex_text = vtext

        vtextcols = self.graph.new_vertex_property('vector<double>')
        for i in range (0,self.numPeople):
            vtextcols[i] = (0,0,0)
        self.graph.vp.vertex_text_color = vtextcols

        vsize = self.graph.new_vertex_property('double')
        for i in range (0,self.numPeople):
            vsize[i] = 25.0
            
        self.graph.vp.vertex_size = vsize
            
        return self.graph
        
            

#print (sys.argv)

parser = argparse.ArgumentParser()
parser.add_argument ('-q',type=float,default=0.5, help="q: level of inequality in the model")
parser.add_argument ('-r',type=float,default=0.2, help="r: rate that status is contributed to others")
parser.add_argument ('-n',type=int,default=20, help="n: number of people")
parser.add_argument ('-l',type=int,default=5, help="l: number of links per person")
parser.add_argument ('-w',type=float,default=1, help="w: chance that a link is rewired")
parser.add_argument ('-m',action="store_true", help="add incoming value if link is mutual")
parser.add_argument ('--show',action="store_true", default=False, help="Show graph")
parser.add_argument ('--plot',action="store_true", default=False, help="Plot time trace graph")
parser.add_argument ('--save',type=str, default="", help="Save time trace data")
parser.add_argument ('--tlen',type=int,default=100000, help="Time length")
parser.add_argument ('--seed',type=int,default=-1, help="Random seed")

args = parser.parse_args()

#print (args)

qval = float(args.q)
rval = float(args.r)
nval = int(args.n)
lval = int(args.l)
wval = float(args.w)
offscreen = True
doplot = bool(args.plot)
showgraph = bool(args.show)
seed = int(args.seed)
if seed == -1:
    random.seed()
    td=(datetime.datetime.now()-datetime.datetime(2017,1,1,0,0,0,0))
    seed = td.microseconds
    print ("Generating seed = ",seed)

random.seed(seed)

g = None

step = 0.005       # move step
K = 0.5            # preferred edge length

if showgraph:
    g = Graph(directed=True)


population = Population(nval,lval,rval,qval,wval,graph=g,maxStatus=6)

if showgraph:
    # make the initial graph
    population.makeGraph()

    pos = sfdp_layout(g, K=K)  # initial layout positions

    # This creates a GTK+ window with the initial graph layout
    if not offscreen:
        win = GraphWindow(g, pos, geometry=(800, 600),vertex_size=g.vp.vertex_size,vertex_fill_color=g.vp.vertex_fill_colors,vertex_text=g.vp.vertex_text,vertex_text_color=g.vp.vertex_text_color);
        # edge_pen_width=g.ep.edge_pen_widths
    else:
        win = Gtk.OffscreenWindow()
        win.set_default_size(600, 600)
        win.graph = GraphWidget(g, pos, vertex_size=g.vp.vertex_size,vertex_fill_color=g.vp.vertex_fill_colors,vertex_text=g.vp.vertex_text,vertex_text_color=g.vp.vertex_text_color)
        win.add(win.graph)



if args.m:
    population.includeMutualLinks = True

data=[]

t = 0

initialCentreOfMass = zeros(2)

def update_state():
    global t,data,initialCentreOfMass

    if (showgraph):
        sfdp_layout(g, pos=pos, K=K, init_step=step, max_iter=1)

        centreOfMass = zeros(2)
        for i in range(0,population.numPeople):
            centreOfMass=centreOfMass + pos[i]

        centreOfMass = centreOfMass/float(population.numPeople)

        if (t == 0):
            initialCentreOfMass = centreOfMass
        else:
            adjustment = 0.1*(initialCentreOfMass-centreOfMass)
            for i in range(0,population.numPeople):
                pos[i] = pos[i] + adjustment
        
            
        
#for t in range(0,int(args.tlen)):
#    population.outputNetwork()
    population.updateStatuses()
    population.rewireLinks()

#    if t>0 and t % 1000 == 0:
#        win.graph.fit_to_window(ink=True)

    t += 1

    if showgraph:
        # The following will force the re-drawing of the graph, and issue a
        # re-drawing of the GTK window.
        win.graph.regenerate_surface()
        win.graph.queue_draw()

        # if doing an offscreen animation, dump frame to disk
        if offscreen:
            pixbuf = win.get_pixbuf()
            pixbuf.savev(r'/tmp/frames/powerModel%06d.png' % t, 'png', [], [])
            if t > int(args.tlen):
                sys.exit(0)

            
    #   population.outputLinksVersusStatus()
    #    population.findAnomalousIndividual()
    if doplot:
        statuses=population.getStatuses()
        data.append(statuses)
    if t< int(args.tlen):
        return True
    return False


#print (qval,nval,lval,rval,mean([max(data[i]) for i in range(0,len(data))]))

if showgraph:
    # Bind the function above as an 'idle' callback.
    cid = GObject.idle_add(update_state)

    # We will give the user the ability to stop the program by closing the window.
    win.connect("delete_event", Gtk.main_quit)

    # Actually show the window, and start the main loop.
    win.show_all()
    Gtk.main()
else:
    counter = 0
    while update_state():
        counter += 1

    
if doplot:    
    adata=array(data)
    figure(1,figsize=(20,10))
#    subplot (1,2,1)
    hold(False)
    plot (adata,alpha=0.5)
    xlabel('time')
    ylabel('status')
    if len(args.save) > 0:
        pickle.dump(adata, open(args.save,"wb"))
    
#    subplot (1,2,2)
#    hold(False)
#    lvs=array(population.numlinksvsstatus)
#    plot (lvs[:,0],lvs[:,1],'o',alpha=0.01, markersize=30)
#    xlabel('Number of links')
#    ylabel('Status')
#    savefig('q_'+str(qval)+'_r_'+str(rval)+'_n_'+str(nval)+'_l_'+str(lval)+'_fig.png')

    show()

if False:
    g = Graph()
    population.makeGraph(g)
    graph_draw(g,vertex_size=8,vertex_fill_color=g.vp.vertex_fill_colors,edge_pen_width=g.ep.edge_pen_widths)
