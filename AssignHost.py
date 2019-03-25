"""
Main idea:
  i. group sections into portions
  ii. then distribute the portions to each host, so that the STD of hosts' word counts is minimized
B_   block(column)
S_   section(paragraph)
P_   portion(read by a host)
_N   number, count
For those who are new to Python, remember,
1. The index of a Python list starts with 0.
2. Variables in Python are pointers. So to copy a list but not the
   address of the list, use a=copy.deepcopy(b), instead of a=b.
"""
from quip4aha import q4a, config, InvalidOperation
from html.parser import HTMLParser
import copy
import re
from itertools import chain
from functools import reduce
import operator
from collections import OrderedDict
from dataclasses import make_dataclass

P_WORD_COUNT_AVG = 468 # weighted word count for an avg portion (350w * 1.336)
fk_weight = lambda sn, wd, sl: 1.0146 ** (100 - (
          206.835 - 1.015*(wd/sn) - 84.6*(sl/wd)
          )) # Flesch reading-ease test

class MyHTMLParser(HTMLParser):
    def __init__(self, keyword):
        HTMLParser.__init__(self)
        self.__KeyWord = keyword
        self.__BN = len(keyword)
        self.__BNNow = -1
        self.__SNNow = 0
        self.__newline = 0  # when there are total two <p> and <br/> between two data, new section
        self.__br = 0 # for headless section of two <br/>, sid is not unique identifier
        self.__SIDNow = ''
        self.SText = []
        self.SID = []

    def handle_starttag(self, tag, attrs):
        if tag == "p":
            self.__SIDNow = attrs[0][1]  # extract the ID attr
            self.__newline += 1
            self.__br = 0

    def handle_startendtag(self, tag, attrs):
        if tag == "br":
            self.__newline += 1
            self.__br += 1

    def handle_data(self, data):
        if data.strip() == "": return
        if self.__BNNow+1<=self.__BN-1 and data.find(self.__KeyWord[self.__BNNow+1])!=-1:
            self.__BNNow += 1  # new block
            self.__SNNow = 0
            self.SText += [[""]]
            self.SID += [[(self.__SIDNow, self.__br)]]
        elif self.__newline >= 2:
            self.__SNNow += 1  # new section
            self.SText[self.__BNNow] += [""]
            self.SID[self.__BNNow] += [(self.__SIDNow, self.__br)]
        self.SText[self.__BNNow][self.__SNNow] += data
        self.__newline = 0


def _check_solution(st):
    v = max(st.HostWordCount) - min(st.HostWordCount)
    if v < st.Ans_HostWordCountRange:
        st.Ans_HostWordCountRange = v
        st.Ans_CutSign, st.Ans_PAssign = copy.deepcopy(st.CutSign), copy.deepcopy(st.PAssign)

def AssignHost():
    # ====================DOC CATCHER====================
    doc_id = q4a.latest_script_id
    raw_doc = q4a.get_thread(id=doc_id)["html"]
    '''
    docURL = ... # test doc URL: [a-zA-Z0-9]{12}
    thread = q4a.get_thread(id=docURL)
    doc_id = thread['thread']['id'] # test doc id: [a-zA-Z0-9]{11}
    '''

    # ====================DOC PRE-PROCESSOR====================
    if raw_doc.find(r'<i>//') != -1:
        raise InvalidOperation("Redundancy Warning: The script has already been divided and assigned!")
    clean_doc = raw_doc.encode('ascii', 'ignore').decode('ascii')  # clear all non-ascii
    clean_doc = re.sub(r'<h1.+</h1>', '', clean_doc, count=1)  # delete the header

    temptxt = [s.replace('**', '') for s in config['block']] # TODO: sanitize other Markdown syntax
    keyword = [s[:min(16, s.index('\n'))] for s in temptxt]
    parser = MyHTMLParser(keyword)
    parser.feed(clean_doc)

    # =====================SETTINGS====================
    text = parser.SText
    sen = [[len(re.findall(r"(^|[\.\?!])[ \"]*[A-Z]", s, re.M)) for s in b] for b in text]
    wrd = [[len(re.findall(r"\b\w+\b", s)) for s in b] for b in text]
    syl = [[len(re.findall(r"[aeiouy]+", s)) for s in b] for b in text]
    fk = [fk_weight(sum(s), sum(w), sum(y)) for s,w,y in zip(sen,wrd,syl)] # B[]

    SWordCount = [[swc*f for swc in w] for f,w in zip(fk,wrd)]  # B[S[]], weighted
    SID = parser.SID
    SNperB = [len(b) for b in SWordCount]  # B[SN]
    PNperB = [int(sum(swc)/P_WORD_COUNT_AVG+1) for swc in SWordCount]
    PNperB = [min(pn,sn) for pn,sn in zip(PNperB,SNperB)] # B[PN]

    for t in config['assign']:
        # task hosts
        thost = t['host']
        import random
        random.shuffle(thost)
        # flatten block range
        taskBtoB = list(chain.from_iterable(
                      range(int(c[0]), int(c[-1])+1)
                       for c in [c.split('-') for c in t['range'].split(',')]))

        ans_passign, ans_cutsign = \
            per_task(SNperB, SWordCount, PNperB, len(thost), taskBtoB)

        # ====================POST DIVISIONS====================
        tSID = [SID[b] for b in taskBtoB]
        post_assign(tSID, ans_passign, ans_cutsign, thost, doc_id, raw_doc)

    return "Done!"

def per_task(SNperB, SWordCount, PNperB, hostn, taskBtoB):
    def _assign(st, task_b, s, last_assignee, lastp):
        if task_b == len(taskBtoB):
            _check_solution(st)
            return

        b = taskBtoB[task_b]
        next1s, wordsum1 = (s+1)%SNperB[b], SWordCount[b][s]
        nextxs, wordsumx = 0, sum(SWordCount[b][s:])
        for h in range(hostn):
            if h == last_assignee:
                if s == 0: continue  # cross block, no
                p = lastp
            else:
                p = lastp + 1
                st.CutSign[task_b][p], st.PAssign[task_b][p] = s, h

            if p < PNperB[b]-1:
                nexts, wordsum = next1s, wordsum1
            else:  # reach the limit, take the rest
                nexts, wordsum = nextxs, wordsumx
            st.HostWordCount[h] += wordsum
            _assign(st, task_b+(nexts==0), nexts, h, -1 if nexts==0 else p)
            st.HostWordCount[h] -= wordsum

    st = make_dataclass('state', ['HostWordCount', 'Ans_HostWordCountRange',
                             'CutSign', 'PAssign', 'Ans_PAssign', 'Ans_CutSign'])(
        HostWordCount=[0.00] * hostn,
        Ans_HostWordCountRange=1000.00,
        CutSign=[[-1]*PNperB[b] for b in taskBtoB],
        PAssign=[[-1]*PNperB[b] for b in taskBtoB],
        Ans_PAssign=[],
        Ans_CutSign=[],
    )
    st.CutSign[0][0], st.PAssign[0][0] = 0, 0
    st.HostWordCount[0] += SWordCount[taskBtoB[0]][0]
    if PNperB[taskBtoB[0]] > 1:
        _assign(st, 0, 1, 0, 0)
    else:
        _assign(st, 1, 0, 0, -1)
    return st.Ans_PAssign, st.Ans_CutSign

def post_assign(sidt, passign, cutsign, host, doc_id, raw_doc):
    a = OrderedDict() # {sid: [(br, pa)]}
    for sid_tb, pa_tb, cs_tb in zip(sidt, passign, cutsign):
        for pa, cs in zip(pa_tb, cs_tb):
            if cs == -1:
                break
            sid, br = sid_tb[cs]
            a.setdefault(sid, [])
            a[sid] += [(br, pa)]
    last_pos = 0
    for sid, br_pa in a.items():
        m = re.compile(rf"<p id='{sid}' class='line'>(.+?)</p>").search(raw_doc, last_pos)
        last_pos = m.end()
        para = m.group(1).split('<br/>')
        for br, pa in br_pa[::-1]:
            para.insert(br, f'<i>//{host[pa]}</i>')
        content = '<br/>'.join(para)
        q4a.edit_document(thread_id=doc_id,
                          content=f"<p class='line'>{content}</p>",
                          operation=q4a.REPLACE_SECTION, section_id=sid)

if __name__ == "__main__":
    AssignHost()
