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
import itertools


class MyHTMLParser(HTMLParser):
    def __init__(self, keyword, BN):
        HTMLParser.__init__(self)
        self.__KeyWord = keyword
        self.__BN = BN
        self.__BNNow = -1
        self.__SNNow = 0
        self.__newline = 0  # when there are total two <p> and <br/> between two data, new section
        self.__SIDNow = ''
        self.SWordCount = []
        self.SID = []

    def handle_starttag(self, tag, attrs):
        if tag == "p":
            self.__SIDNow = attrs[0][1]  # extract the ID attr
            self.__newline += 1

    def handle_startendtag(self, tag, attrs):
        if tag == "br":
            self.__newline += 1

    def handle_data(self, data):
        wordcount = len(re.findall(r"\b\w+\b", data))
        if wordcount == 0: return 0
        if self.__BNNow+1<=self.__BN-1 and data.find(self.__KeyWord[self.__BNNow+1])!=-1:
            self.__BNNow += 1  # new block
            self.__SNNow = 0
            self.SWordCount += [[0]]
            self.SID += [[self.__SIDNow]]
        elif self.__newline >= 2:
            self.__SNNow += 1  # new section
            self.SWordCount[self.__BNNow] += [0]
            self.SID[self.__BNNow] += [self.__SIDNow]
        self.SWordCount[self.__BNNow][self.__SNNow] += wordcount
        self.__newline = 0


class AssignHost(object):

    def __init__(self):
        # --------------------Block----------------------
        self.KeyWord = [b['keyword'] for b in config['block']]
        self.BN = len(self.KeyWord)
        self.BWeight = [b['weight'] for b in config['block']]  # B[]
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
            t['parsed_range'] = list(itertools.chain.from_iterable(
                          range(int(c[0]), int(c[1] if len(c)==2 else c[0])+1)
                           for c in [c.split('-') for c in t['range'].split(',')]))
        # --------------------Portion----------------------
        self.PNperB = [b['portion'] for b in config['block']] # B[PN]
        self.PWordCount = []
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
        self.SWordCount = parser.SWordCount
        self.SWordCount = [[swc*self.BWeight[b] for swc in self.SWordCount[b]] for b in range(self.BN)]  # B[S[]], weighted
        self.SID = parser.SID
        self.SNperB = [len(b) for b in self.SWordCount]  # B[SN]
        self.PNperB = [min(self.PNperB[i], self.SNperB[i]) for i in range(self.BN)]

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
            self.PWordCount = [[0]*self.PNperB[b] for b in self.taskBtoB]
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
            last_pos = 0
            for tb, b in enumerate(self.taskBtoB):
                for p in range(self.PNperB[b]):
                    if self.Ans_CutSign[tb][p] == -1:
                        break
                    m = re.compile(r"<p id='%s' class='line'>(.+?)</p>" % self.SID[b][self.Ans_CutSign[tb][p]]).search(raw_doc, last_pos)
                    orig_content = m.group(1)
                    last_pos = m.end()
                    self.client.edit_document(thread_id=doc_id,
                                              content=r"<p class='line'><i>//%s</i><br/>%s</p>" % (self.Host[self.Ans_PAssign[tb][p]], orig_content),
                                              operation=self.client.REPLACE_SECTION, section_id=self.SID[b][self.Ans_CutSign[tb][p]])

        return "Done!"

if __name__ == "__main__":
    AssignAction = AssignHost()
    AssignAction.do()
