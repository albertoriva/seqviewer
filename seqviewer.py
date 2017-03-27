#!/usr/bin/env python

import re
import sys
import math
import random
import os.path
import Tkinter as tk, tkFileDialog, tkFont, tkMessageBox
from Tkinter import StringVar

## Utils

def makeRuler(n):
    """Returns a string containing the ruler for `n' positions."""
    r1 = ""
    r2 = ""
    d1 = 1
    d10 = 0

    for i in range(1, n+1):
        if d1 == 0:
            d10 += 1
            r1 += str(d10)
        else:
            r1 += " "
        r2 += str(d1)
        d1 += 1
        if d1 == 10:
            d1 = 0
    return r1 + "\n" + r2 + "\n"

## Defaults

class Defaults():
    masterTitle = "seqviewer - fasta and fastq file viewer"
    frameWidth = 800
    frameHeight = 600
    rowlen = 60
    fontFamily = "Courier"
    fontSize = 12
    confFile = ""

DEF = Defaults()

## Sequence object

class Sequence():
    name = ""
    seq = ""
    filename = ""
    seqlen = 0                  # Length of sequence
    txtlen = 0                  # Length of text representing sequence
    nlines = 0                  # Number of lines in text representing sequence
    rowlen = 60

    def __init__(self):
        self.rowlen = DEF.rowlen

    def initRandom(self, length):
        self.seqlen = length
        self.seq = "".join([random.choice(['A', 'C', 'G', 'T']) for i in range(length)])
        self.nlines = int(math.ceil(1.0*length/self.rowlen))
        self.txtlen = length + self.nlines

    def initFasta(self, filename):
        self.filename = filename
        with open(filename, "r") as f:
            hdr = f.readline().rstrip("\r\n")
            self.name = hdr[1:]
            for line in f:      # Would this be faster with f.read()?
                if line[0] == ">":
                    break       # Multi-fasta not handled yet
                self.seq += line.rstrip("\r\n")
        self.seqlen = len(self.seq)
        self.nlines = int(math.ceil(1.0*self.seqlen/self.rowlen))

    def indexToSeqpos(self, index):
        (row, col) = index.split(".")
        return (int(row) - 1) * self.rowlen + int(col)

    def seqposToIndex(self, seqpos):
        return "{}.{}".format(1 + int(math.floor(seqpos/self.rowlen)),
                              1 + (seqpos % self.rowlen))

    def translateBase(self, base):
        nucmap = {'A': 'T', 'C': 'G', 'G': 'C', 'T': 'A',
                  'a': 't', 'c': 'g', 'g': 'c', 't': 'a'}
        if base in nucmap:
            return nucmap[base]
        else:
            return base

    def transform(self, operation):
        """Transform this sequence according to `operation', which can be one of
`rc', `c', `r'. These operations do not change the sequence length."""
        
        seq = self.seq
        if operation == "rc":
            ptr = self.seqlen - 1
            newseq = [''] * self.seqlen
            for i in range(self.seqlen):
                newseq[ptr] = self.translateBase(seq[i])
                ptr += -1
        elif operation == "r":
            ptr = self.seqlen - 1
            newseq = [''] * self.seqlen
            for i in range(self.seqlen):
                newseq[ptr] = seq[i]
                ptr += -1
        elif operation == "c":
            newseq = [''] * self.seqlen
            for i in range(self.seqlen):
                newseq[i] = self.translateBase(seq[i])
        self.seq = newseq
        return newseq
            
## Sequence info object

class Seqinfo():
    filename = None
    filetype = None
    seqname = None
    seqlen = None
    search = None
    visiblereg = None
    selected = None

    def __init__(self):
        self.filename = StringVar()
        self.filetype = StringVar()
        self.seqname = StringVar()
        self.seqlen = StringVar()
        self.search = StringVar()
        self.visiblereg = StringVar()
        self.selected = StringVar()

## Region representing highlighted region

class Region():
    mark1 = ""                  # m1
    mark2 = ""
    index1 = ""                 # r.c
    index2 = ""
    seqpos1 = 0                 # 123
    seqpos2 = 0

    def __init__(self, mark1, mark2, index1, index2, seqpos1, seqpos2):
        self.mark1 = mark1
        self.mark2 = mark2
        self.index1 = index1
        self.index2 = index2
        self.seqpos1 = seqpos1
        self.seqpos2 = seqpos2

    def dump(self):
        print "({}, {}) ({}, {}), ({}, {})".format(self.mark1, self.mark2, self.index1, self.index2, self.seqpos1, self.seqpos2)

## Top-level application object 

APP = None

class Application(tk.Frame):
    seqfont = None              # Font used to display sequences in main window
    dummywin = None             # Top-left text area 
    rulerwin = None             # Text area for ruler
    poswin = None          # Text area for positions
    mainwin = None         # Text area for sequences
    uniscrollbar = None    # Common scrollbar
    ruler = ""
    rulerheight = 2
    sequence = None             # Sequence object
    seqinfo = None

    # Marks
    markcnt = 0                 # Counter for mark names
    hilightmarks = []
    nhilights = 0
    visibleHilight = 0

    def __init__(self, master=None):

        # Check for version number
        if os.path.isfile("VERSION"):
            with open("VERSION", "r") as v:
                ver = v.read().rstrip("\r\n")
                self.version = ver

        tk.Frame.__init__(self, master, width=DEF.frameWidth, height=DEF.frameHeight)
        self.grid(sticky=tk.N+tk.S+tk.E+tk.W)
        self.grid()
        self.grid_propagate(0)
        self.createMenus()
        self.createWidgets()
        self.hilightmarks = []
        self.hicoords = []

    def __scrollBoth(self, action, position, type=None):
        self.mainwin.yview_moveto(position)
        self.poswin.yview_moveto(position)

    def __updateScroll(self, first, last, type=None):
        self.mainwin.yview_moveto(first)
        self.poswin.yview_moveto(first)
        self.uniscrollbar.set(first, last)

    def createMenus(self):
        top = self.winfo_toplevel()
        self.MB = tk.Menu(top)

        filemenu = tk.Menu(self.MB, tearoff=0)
        filemenu.add_command(label="Open...", command=self.openFile, underline=0, accelerator="F9")
        filemenu.add_command(label="New random seq", command=self.newRandom, underline=0)
        filemenu.add_command(label="Save as...", underline=0)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.quit, underline=1)
        self.MB.add_cascade(label="File", underline=0, menu=filemenu)

        selmenu = tk.Menu(self.MB, tearoff=0)
        selmenu.add_command(label="Select all", underline=0, command=self.selectAll)
        selmenu.add_command(label="Copy selection", underline=0, command=self.copySelection)
        selmenu.add_command(label="Highlight selection", underline=0, command=self.highlightSelection, accelerator="F8")
        selmenu.add_command(label="Export highlights...", underline=0, command=self.exportHighlights)
        selmenu.add_command(label="Clear highlights", underline=1, command=self.clearHighlights, accelerator="Del")
        self.MB.add_cascade(label="Selection", underline=0, menu=selmenu)

        transmenu = tk.Menu(self.MB, tearoff=0)
        transmenu.add_command(label="ReverseComplement", underline=0, command=self.doReverseComplement)
        transmenu.add_command(label="Reverse", underline=2, command=self.doReverse)
        transmenu.add_command(label="Complement", underline=0, command=self.doComplement)

        seqmenu = tk.Menu(self.MB, tearoff=0)
        seqmenu.add_command(label="Details...", underline=0)
        seqmenu.add_cascade(label="Transform", underline=0, menu=transmenu)
        seqmenu.add_command(label="Translate", underline=0)
        self.MB.add_cascade(label="Sequence", underline=0, menu=seqmenu)
        top.config(menu=self.MB)

    def createWidgets(self):
        self.seqfont = tkFont.Font(family="Courier", size=14)

        top = self.winfo_toplevel()
        top.rowconfigure(0, weight = 1)
        top.columnconfigure(0, weight = 1)
        self.rowconfigure(2, weight = 1)
        self.columnconfigure(1, weight = 1)
        
        self.seqinfo = Seqinfo()
        self.SF = tk.Frame(self, bd=3, relief=tk.GROOVE)
        tk.Label(self.SF, text='Filename:').grid(row=0, column=0, sticky=tk.W)
        tk.Entry(self.SF, state=tk.DISABLED, textvariable=self.seqinfo.filename, disabledbackground='lightyellow', disabledforeground='blue').grid(
            row=0, column=1, columnspan=4, sticky=tk.W+tk.E)

        tk.Label(self.SF, text='Type:').grid(row=0, column=5, sticky=tk.W)
        tk.Entry(self.SF, state=tk.DISABLED, textvariable=self.seqinfo.filetype, disabledbackground='lightyellow', disabledforeground='blue').grid(
            row=0, column=6, sticky=tk.W+tk.E)

        tk.Label(self.SF, text='Name:').grid(row=1, column=0, sticky=tk.W)
        tk.Entry(self.SF, state=tk.DISABLED, textvariable=self.seqinfo.seqname, disabledbackground='lightyellow', disabledforeground='blue').grid(
            row=1, column=1, columnspan=4, sticky=tk.W+tk.E)

        tk.Label(self.SF, text='Length:').grid(row=1, column=5, sticky=tk.W)
        tk.Entry(self.SF, state=tk.DISABLED, textvariable=self.seqinfo.seqlen, disabledbackground='lightyellow', disabledforeground='blue').grid(
            row=1, column=6, sticky=tk.E)

        tk.Label(self.SF, text='Search:').grid(row=2, column=0, sticky=tk.W)
        se = tk.Entry(self.SF, textvariable=self.seqinfo.search, background='lightyellow', foreground='blue')
        se.grid(row=2, column=1, sticky=tk.W+tk.E)
        se.bind("<Return>", self.findMatches)
        tk.Button(self.SF, text="<", command=self.previousMatch).grid(row=2, column=2)
        tk.Entry(self.SF, background='lightyellow', foreground='blue', textvariable=self.seqinfo.visiblereg, justify=tk.CENTER).grid(
            row=2, column=3)
        tk.Button(self.SF, text=">", command=self.nextMatch).grid(row=2, column=4)
        
        tk.Label(self.SF, text='Selection:').grid(row=2, column=5, sticky=tk.W)
        tk.Entry(self.SF, state=tk.DISABLED, textvariable=self.seqinfo.selected, disabledbackground='lightyellow', disabledforeground='blue').grid(
            row=2, column=6, sticky=tk.E)

        self.SF.columnconfigure(1, weight=2)

        self.dummywin = tk.Text(self, width=10, relief=tk.FLAT, bg="#D9D9D9", takefocus=0, padx=0, pady=0)
        self.dummywin.config(font=self.seqfont)
        self.dummywin.config(state=tk.DISABLED)

        self.rulerwin = tk.Text(self, relief=tk.FLAT, bg="#D9D9D9", takefocus=0, padx=0, pady=0, wrap=tk.NONE)
        self.rulerwin.config(font=self.seqfont)

        self.poswin = tk.Text(self, width=10, relief=tk.FLAT, bg="#D9D9D9", takefocus=0, padx=0, pady=0, spacing1=3)
        self.poswin.config(font=self.seqfont)

        self.mainwin = tk.Text(self, relief=tk.FLAT, padx=0, pady=0, wrap=tk.NONE, spacing1=3)
        self.mainwin.config(font=self.seqfont)

        self.uniscrollbar = tk.Scrollbar(self)
        self.uniscrollbar.config(command=self.__scrollBoth)
        self.mainwin.config(yscrollcommand=self.__updateScroll)
        self.poswin.config(yscrollcommand=self.__updateScroll)

        self.SF.grid(row=0, column=0, columnspan=3, sticky=tk.W+tk.E)
        self.dummywin.grid(row=1, column=0, padx=0, pady=0)
        self.rulerwin.grid(row=1, column=1, sticky=tk.W+tk.E, padx=0, pady=0)
        self.poswin.grid(row=2, column=0, sticky=tk.N+tk.S, padx=0, pady=0)
        self.mainwin.grid(row=2, column=1, sticky=tk.N+tk.S+tk.E+tk.W, padx=0, pady=0)
        self.uniscrollbar.grid(row=2, column=2, sticky=tk.N+tk.S, padx=0, pady=0)

        self.L = tk.Label(self, text="(c) 2017, A. Riva, UF ICBR Bioinformatics", justify=tk.LEFT, anchor=tk.W, relief=tk.RIDGE)
        self.L.grid(row=3, column=0, columnspan=3, sticky=tk.W+tk.E)

        # Tags for text window
        tag = "hilight"
        self.mainwin.tag_config(tag, background="yellow")

        # Key bindings
        self.mainwin.bind("<<Selection>>", self.selectionDone)
        top.bind("<Home>", lambda ev: self.scrollTo(0))
        top.bind("<End>", lambda ev: self.scrollTo(1))
        top.bind("<Prior>", lambda ev: self.scrollTo(2))
        top.bind("<Next>", lambda ev: self.scrollTo(3))
        top.bind("<Up>", lambda ev: self.scrollTo(4))
        top.bind("<Down>", lambda ev: self.scrollTo(5))
        top.bind("<F9>", self.openFile)
        top.bind("<F8>", self.highlightSelection)
        top.bind("<Delete>", self.clearHighlights)

        if sys.platform[:5] == 'linux': # These are not available on Mac...
            top.bind("<KP_Home>", lambda ev: self.scrollTo(0))
            top.bind("<KP_End>", lambda ev: self.scrollTo(1))
            top.bind("<KP_Prior>", lambda ev: self.scrollTo(2))
            top.bind("<KP_Next>", lambda ev: self.scrollTo(3))
            top.bind("<KP_Up>", lambda ev: self.scrollTo(4))
            top.bind("<KP_Down>", lambda ev: self.scrollTo(5))

    def scrollTo(self, where):
        if where == 0:
            self.mainwin.see("1.1")
        elif where == 1:
            self.mainwin.see(tk.END)
        elif where == 2:
            self.mainwin.yview_scroll(-1, tk.PAGES)
        elif where == 3:
            self.mainwin.yview_scroll(1, tk.PAGES)
        elif where == 4:
            self.mainwin.yview_scroll(-1, tk.UNITS)
        elif where == 5:
            self.mainwin.yview_scroll(1, tk.UNITS)

    def selectionDone(self, event):
        mw = self.mainwin
        seq = self.sequence
        if mw.tag_ranges("sel"):
            self.seqinfo.selected.set("{} - {}".format(seq.indexToSeqpos(mw.index(tk.SEL_FIRST)) + 1, seq.indexToSeqpos(mw.index(tk.SEL_LAST))))

    def banner(self):
        mw = self.mainwin
        mw.config(state=tk.NORMAL)
        mw.insert(tk.INSERT, """
SeqViewer 1.0

Use File -> Open... to load a sequence file.

(c) 2017, A.Riva, UF ICBR Bioinformatics
""")
        mw.tag_configure("center", justify='center')
        mw.tag_add("center", 1.0, "end")
        mw.config(state=tk.DISABLED)
        
    def initialize(self, seqobj):
        """Initialize the viewer with the sequence contained in `seqobj'."""
        self.sequence = seqobj
        seq = seqobj.seq

        self.ruler = makeRuler(self.sequence.rowlen)

        dw = self.dummywin
        dw.delete(1.0, tk.END)
        dw.config(height=self.rulerheight)
        dw.insert(tk.INSERT, "\n"*self.rulerheight)

        rw = self.rulerwin
        rw.delete(1.0, tk.END)
        rw.config(height=self.rulerheight)
        rw.insert(tk.INSERT, self.ruler)
        rw.tag_configure("center", justify='center')
        rw.tag_add("center", 1.0, "end")
        rw.config(state=tk.DISABLED)

        pw = self.poswin
        mw = self.mainwin

        pw.config(state=tk.NORMAL)
        numbers = "\n".join([str(x*self.sequence.rowlen+1) for x in range(0, self.sequence.nlines)])
        pw.delete(1.0, tk.END)
        pw.insert(tk.INSERT, numbers)
        pw.tag_configure("right", justify='right')
        pw.tag_add("right", 1.0, "end")
        pw.config(state=tk.DISABLED)

        mw.config(state=tk.NORMAL)
        mw.delete(1.0, tk.END)

        i = 0
        for j in range(self.sequence.seqlen):
            mw.insert(tk.INSERT, seq[j])
            i += 1
            if i == seqobj.rowlen:
                mw.insert(tk.INSERT, "\n")
                i = 0
        while i < seqobj.rowlen:
            mw.insert(tk.INSERT, " ")
            i += 1
        mw.tag_configure("center", justify='center')
        mw.tag_add("center", 1.0, "end")
        mw.config(state=tk.DISABLED)

        self.seqinfo.filetype.set("fasta")
        self.seqinfo.seqlen.set("{} bp".format(self.sequence.seqlen))
        self.seqinfo.seqname.set(self.sequence.name)
        self.seqinfo.filename.set(self.sequence.filename)

    ## Commands

    def openFile(self, event=None):
        filename = tkFileDialog.askopenfilename(title="Select file containing sequence", parent=self)
        if filename:
            SO = Sequence()
            SO.initFasta(filename)
            self.initialize(SO)

    def newRandom(self, event=None):
        SO = Sequence()
        SO.initRandom(10000)
        self.initialize(SO)

    def selectAll(self, event=None):
        self.mainwin.tag_add('sel', '1.0', tk.END)

    def copySelection(self, event=None):
        seqobj = self.sequence
        mw = self.mainwin
        start = seqobj.indexToSeqpos(mw.index(tk.SEL_FIRST))
        end = seqobj.indexToSeqpos(mw.index(tk.SEL_LAST))
        frag = seqobj.seq[start:end]
        self.clipboard_clear()
        self.clipboard_append(frag)

    def addHighlight(self, pos1, pos2, seqpos1=None, seqpos2=None):
        mw = self.mainwin
        seqobj = self.sequence
        self.markcnt += 1
        m1 = "m" + str(self.markcnt)
        self.markcnt += 1
        m2 = "m" + str(self.markcnt)
        mw.mark_set(m1, pos1)
        mw.mark_set(m2, pos2)
        idx1 = mw.index(m1)
        idx2 = mw.index(m2)
        if not seqpos1:
            seqpos1 = seqobj.indexToSeqpos(idx1)
        if not seqpos2:
            seqpos2 = seqobj.indexToSeqpos(idx2)
        reg = Region(m1, m2, idx1, idx2, seqpos1, seqpos2)
        self.hilightmarks.append(reg)
        self.nhilights += 1
        mw.tag_add("hilight", idx1, idx2)

    def highlightSelection(self, event=None):
        self.addHighlight(tk.SEL_FIRST, tk.SEL_LAST)
        self.sortHilightRegions()

    def clearHighlights(self, event=None):
        mw = self.mainwin
        for reg in self.hilightmarks:
            mw.mark_unset(reg.mark1)
            mw.mark_unset(reg.mark2)
        self.hilightmarks = []
        self.nhilights = 0
        self.visibleHilight = 0
        mw.tag_remove("hilight", "1.1", tk.END)
        self.seqinfo.visiblereg.set("")
        self.seqinfo.selected.set("")

    def sortHilightRegions(self):
        self.hilightmarks.sort(key=lambda r: r.seqpos1)

    def exportHighlights(self):
        seqobj = self.sequence
        filename = tkFileDialog.asksaveasfilename(title="Choose file...")
        if filename != '':
            with open(filename, "w") as out:
                for reg in self.hilightmarks:
                    p = reg.seqpos1
                    q = reg.seqpos2
                    out.write("{}\t{}\t{}\t{}\n".format(seqobj.name, p+1, q, seqobj.seq[p:q]))

    def findMatches(self, event=None):
        nmatches = 0
        mw = self.mainwin
        sq = self.sequence
        target = self.seqinfo.search.get()
        cp = re.compile(target, flags=re.I)
        matches = re.finditer(cp, sq.seq)
        for m in matches:
            start = sq.seqposToIndex(m.start()-1)
            end   = sq.seqposToIndex(m.end()-1)
            self.addHighlight(start, end, m.start(), m.end())
            nmatches += 1
        self.sortHilightRegions()
        self.locateHilight()

    def locateHilight(self, which=None):
        # print self.nhilights
        # print len(self.hilightmarks)
        if self.nhilights > 0:
            if which and which >= 0 and which < self.nhilights:
                self.visibleHilight = which
            reg = self.hilightmarks[self.visibleHilight]
            self.mainwin.see(reg.index1)
            self.seqinfo.visiblereg.set("match {} / {}".format(self.visibleHilight + 1, self.nhilights))
            self.seqinfo.selected.set("{} - {}".format(reg.seqpos1 + 1, reg.seqpos2))

    def nextMatch(self, event=None):
        self.visibleHilight += 1
        if self.visibleHilight == self.nhilights:
            self.visibleHilight = 0
        self.locateHilight()

    def previousMatch(self, event=None):
        self.visibleHilight += -1
        if self.visibleHilight == -1:
            self.visibleHilight = self.nhilights - 1
        self.locateHilight()

    ## Sequence transformation operations

    def doReverseComplement(self, event=None):
        self.sequence.transform("rc")
        self.initialize(self.sequence)

    def doReverse(self, event=None):
        self.sequence.transform("r")
        self.initialize(self.sequence)

    def doComplement(self, event=None):
        self.sequence.transform("c")
        self.initialize(self.sequence)

def main():
    global APP
    global DEF
    APP = Application()
    APP.defaults = DEF
    APP.master.title(DEF.masterTitle)
    APP.master.geometry("+100+100")

    banner = True
    args = sys.argv[1:]
    if len(args) > 0:
        filename = args[0]
        if os.path.isfile(filename):
            SO = Sequence()
            SO.initFasta(filename)
            APP.initialize(SO)
            banner = False

    if banner:
        APP.banner()
    APP.mainloop()

if __name__ == "__main__":
    main()
