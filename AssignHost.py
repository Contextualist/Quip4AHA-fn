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
from html.parser import HTMLParser # for py2, pip install future
import copy
import re
from itertools import chain, tee, starmap, accumulate
from functools import reduce
import operator
from collections import OrderedDict

P_WORD_COUNT_AVG = 468 # weighted word count for an avg portion (350w * 1.336)
fk_weight = lambda sn, wd, sl: 1.0146 ** (100 - (
          206.835 - 1.015*(wd/sn) - 84.6*(sl/wd)
          )) # Flesch reading-ease test

class MyHTMLParser(HTMLParser):
    def __init__(self, keyword, BN):
        HTMLParser.__init__(self)
        self.__KeyWord = keyword
        self.__BN = BN
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


class AssignHost(object):

    def __init__(self):
        # --------------------Block----------------------
        temptxt = [s.replace('**', '') for s in config['block']] # TODO: sanitize other Markdown syntax
        self.KeyWord = [s[:min(16, s.index('\n'))] for s in temptxt]
        self.BN = len(self.KeyWord)
        # --------------------Section----------------------
        self.SWordCount = []
        self.SID = []
        self.SNperB = []     # B[SN]
        # ---------------------Host----------------------
        self.Host = []
        self.HostN = 0
        self.HostWordCount = []
        self.Ans_HostWordCountRange = 1000.00
        # ---------------------Task----------------------
        self.task = config['assign']
        for t in self.task:
            # flatten block range
            t['parsed_range'] = list(chain.from_iterable(
                          range(int(c[0]), int(c[-1])+1)
                           for c in [c.split('-') for c in t['range'].split(',')]))
        # --------------------Portion----------------------
        self.PNperB = []
        self.CutSign = []
        self.PAssign = []
        self.Ans_CutSign = []
        self.Ans_PAssign = []
        # ----------------------DOC----------------------
        self.client = q4a

    def _check_solution(self):
        v = max(self.HostWordCount) - min(self.HostWordCount)
        if v < self.Ans_HostWordCountRange:
            self.Ans_HostWordCountRange = v
            self.Ans_CutSign, self.Ans_PAssign = copy.deepcopy(self.CutSign), copy.deepcopy(self.PAssign)

    def _assign(self, task_b, s, last_assignee, lastp):
        if task_b == self.taskBN:
            self._check_solution()
            return

        b = self.taskBtoB[task_b]
        next1s, wordsum1 = (s+1)%self.SNperB[b], self.SWordCount[b][s]
        nextxs, wordsumx = 0, sum(self.SWordCount[b][s:])
        for h in range(self.HostN):
            if h == last_assignee:
                if s == 0: continue  # cross block, no
                p = lastp
            else:
                p = lastp + 1
                self.CutSign[task_b][p], self.PAssign[task_b][p] = s, h

            if p < self.PNperB[b]-1:
                nexts, wordsum = next1s, wordsum1
            else:  # reach the limit, take the rest
                nexts, wordsum = nextxs, wordsumx
            self.HostWordCount[h] += wordsum
            self._assign(task_b+(nexts==0), nexts, h, -1 if nexts==0 else p)
            self.HostWordCount[h] -= wordsum

    def do(self):
        # ====================DOC CATCHER====================
        doc_id = self.client.latest_script_id
        raw_doc = self.client.get_thread(id=doc_id)["html"]
        '''
        docURL = ... # test doc URL: [a-zA-Z0-9]{12}
        thread = self.client.get_thread(id=docURL)
        doc_id = self.thread['thread']['id'] # test doc id: [a-zA-Z0-9]{11}
        '''

        # ====================DOC PRE-PROCESSOR====================
        if raw_doc.find(r'<i>//') != -1:
            raise InvalidOperation("Redundancy Warning: The script has already been divided and assigned!")
        clean_doc = raw_doc.encode('ascii', 'ignore').decode('ascii')  # clear all non-ascii
        clean_doc = re.sub(r'<h1.+</h1>', '', clean_doc, count=1)  # delete the header

        parser = MyHTMLParser(self.KeyWord, self.BN)
        parser.feed(clean_doc)

        # =====================SETTINGS====================
        text = parser.SText
        sen = [[len(re.findall(r"(^|[\.\?!])[ \"]*[A-Z]", s, re.M)) for s in b] for b in text]
        wrd = [[len(re.findall(r"\b\w+\b", s)) for s in b] for b in text]
        syl = [[len(re.findall(r"[aeiouy]+", s)) for s in b] for b in text]
        fk = [fk_weight(sum(sen[b]), sum(wrd[b]), sum(syl[b])) for b in range(self.BN)] # B[]

        self.SWordCount = [[swc*fk[b] for swc in wrd[b]] for b in range(self.BN)]  # B[S[]], weighted
        self.SID = parser.SID
        self.SNperB = [len(b) for b in self.SWordCount]  # B[SN]
        self.PNperB = [int(sum(swc)/P_WORD_COUNT_AVG+1) for swc in self.SWordCount]
        self.PNperB = [min(self.PNperB[i], self.SNperB[i]) for i in range(self.BN)] # B[PN]

        for t in self.task:
            # task hosts
            self.Host = t['host']
            import random
            random.shuffle(self.Host)
            self.HostN = len(self.Host)
            self.HostWordCount = [0.00] * self.HostN
            self.Ans_HostWordCountRange = 1000.00
            # task blocks
            self.taskBtoB = t['parsed_range']
            self.taskBN = len(self.taskBtoB)
            self.CutSign = [[-1]*self.PNperB[b] for b in self.taskBtoB]
            self.PAssign = [[-1]*self.PNperB[b] for b in self.taskBtoB]
            # ====================DISTRIBUTE(S->P)====================
            self.CutSign[0][0], self.PAssign[0][0] = 0, 0
            self.HostWordCount[0] += self.SWordCount[self.taskBtoB[0]][0]
            if self.PNperB[self.taskBtoB[0]] > 1:
                self._assign(0, 1, 0, 0)
            else:
                self._assign(1, 0, 0, -1)

            # ====================POST DIVISIONS====================
            SIDt = [self.SID[b] for b in self.taskBtoB]
            self.post_assign(SIDt, self.Ans_PAssign, self.Ans_CutSign, self.Host, doc_id, raw_doc)

        return "Done!"

    def post_assign(self, sidt, passign, cutsign, host, doc_id, raw_doc):
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
    AssignAction = AssignHost()
    AssignAction.do()
