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
import random
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


def precondition():
    doc_id = q4a.latest_script_id
    raw_doc = q4a.get_thread(id=doc_id)["html"]
    '''
    docURL = ... # test doc URL: [a-zA-Z0-9]{12}
    thread = q4a.get_thread(id=docURL)
    doc_id = thread['thread']['id'] # test doc id: [a-zA-Z0-9]{11}
    '''
    if raw_doc.find(r'<i>//') != -1:
        raise InvalidOperation("Redundancy Warning: The script has already been divided and assigned!")
    return doc_id, raw_doc

def parse_doc(raw_doc, template):
    clean_doc = raw_doc.encode('ascii', 'ignore').decode('ascii')  # clear all non-ascii
    clean_doc = clean_doc[clean_doc.find('</h1>')+len('</h1>'):]  # delete the header
    temptxt = [s.replace('**', '') for s in template] # TODO: sanitize other Markdown syntax
    keyword = [s[:min(16, s.index('\n'))] for s in temptxt]
    parser = MyHTMLParser(keyword)
    parser.feed(clean_doc)

    text = parser.SText
    sen = [[len(re.findall(r"(^|[\.\?!])[ \"]*[A-Z]", s, re.M)) for s in b] for b in text]
    wrd = [[len(re.findall(r"\b\w+\b", s)) for s in b] for b in text]
    syl = [[len(re.findall(r"[aeiouy]+", s)) for s in b] for b in text]
    fk = [fk_weight(sum(s), sum(w), sum(y)) for s,w,y in zip(sen,wrd,syl)] # B[]

    SWordCount = [[swc*f for swc in w] for f,w in zip(fk,wrd)]  # B[S[]], weighted
    PNperB = [min(int(sum(swc)/P_WORD_COUNT_AVG+1), len(swc)) for swc in SWordCount] # B[PN]
    return SWordCount, PNperB, parser.SID

def get_host(task, BN):
    host = list(set(chain.from_iterable(t['host'] for t in task)))
    host_per_b = [[]] * BN
    for t in task:
        hn = list(host.index(h) for h in t['host'])
        random.shuffle(hn)
        # flatten block range
        taskB = chain.from_iterable(
                  range(int(c[0]), int(c[-1])+1)
                    for c in [c.split('-') for c in t['range'].split(',')])
        for b in taskB:
            host_per_b[b] = hn
    return host, host_per_b

def _check_solution(st):
    v = max(st.HostWordCount) - min(st.HostWordCount)
    if v < st.Ans_HostWordCountRange:
        st.Ans_HostWordCountRange = v
        st.Ans_HAssign = copy.deepcopy(st.HAssign)

def assign(SWordCount, PNperB, hostn, host_per_b):
    SNperB = [len(b) for b in SWordCount]  # B[SN]
    def _assign(st, b, s, last_assignee, lastp):
        if b == len(PNperB):
            _check_solution(st)
            return

        next1s, wordsum1 = (s+1)%SNperB[b], SWordCount[b][s]
        nextxs, wordsumx = 0, sum(SWordCount[b][s:])
        for h in host_per_b[b]:
            if h == last_assignee:
                if s == 0: continue  # cross block, no
                p = lastp
                st.HAssign[b][s] = -1
            else:
                p = lastp + 1
                st.HAssign[b][s] = h

            if p < PNperB[b]-1:
                nexts, wordsum = next1s, wordsum1
            else:  # reach the limit, take the rest
                nexts, wordsum = nextxs, wordsumx
            st.HostWordCount[h] += wordsum
            _assign(st, b+(nexts==0), nexts, h, -1 if nexts==0 else p)
            st.HostWordCount[h] -= wordsum
        st.HAssign[b][s] = -1

    st = make_dataclass('state', ['HostWordCount', 'Ans_HostWordCountRange',
                                  'HAssign', 'Ans_HAssign'])(
        HostWordCount=[0.00] * hostn,
        Ans_HostWordCountRange=1000.00,
        HAssign=[[-1]*s for s in SNperB],
        Ans_HAssign=[],
    )
    st.HAssign[0][0] = h0 = host_per_b[0][0]
    st.HostWordCount[h0] += SWordCount[0][0]
    if PNperB[0] > 1:
        _assign(st, 0, 1, h0, 0)
    else:
        _assign(st, 1, 0, h0, -1)
    return st.Ans_HAssign

def post_assign(SID, hassign, host, doc_id, raw_doc):
    a = OrderedDict() # {sid: [(br, h)]} "In para {sid}, mark {br}th <br/> with host[{h}]"
    for sid_b, ha_b in zip(SID, hassign):
        for (sid, br), h in zip(sid_b, ha_b):
            if h == -1: continue
            a.setdefault(sid, [])
            a[sid] += [(br, h)]
    last_pos = 0
    for sid, br_h in a.items():
        m = re.compile(rf"<p id='{sid}' class='line'>(.+?)</p>").search(raw_doc, last_pos)
        last_pos = m.end()
        para = m.group(1).split('<br/>')
        for br, h in br_h[::-1]:
            para.insert(br, f'<i>//{host[h]}</i>')
        content = '<br/>'.join(para)
        q4a.edit_document(thread_id=doc_id,
                          content=f"<p class='line'>{content}</p>",
                          operation=q4a.REPLACE_SECTION, section_id=sid)

def AssignHost():
    doc_id, raw_doc = precondition()
    SWordCount, PNperB, SID = parse_doc(raw_doc, config['block'])
    host, host_per_b = get_host(config['assign'], len(SID))
    ans_hassign = assign(SWordCount, PNperB, len(host), host_per_b)
    post_assign(SID, ans_hassign, host, doc_id, raw_doc)
    return "Done!"

if __name__ == "__main__":
    AssignHost()
